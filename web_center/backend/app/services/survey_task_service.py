from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys
from uuid import uuid4
import zipfile

from fastapi import UploadFile

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.project import Project, SurveyBatch
from app.models.survey_task import SurveyTask
from app.schemas.survey_task import SurveyTaskCreate
from app.services.master_data_service import REPOSITORY_ROOT, get_snapshot


BACKEND_ROOT = Path(__file__).resolve().parents[2]
TASK_STORAGE_ROOT = BACKEND_ROOT / "storage" / "tasks"
TASK_INCOMING_ROOT = BACKEND_ROOT / "storage" / "incoming_tasks"
FORM_CONTRACT_PATH = REPOSITORY_ROOT / "shared" / "forms" / "engineering_form_contract.json"
TASK_SCHEMA_VERSION = "3.0"
PACKAGE_FORMAT_VERSION = "1.0"
PACKAGE_KIND = "survey_task"
APP_VERSION = "1.2.0"
APP_VERSION_LABEL = "V1.2.0"
MAX_TASK_UPLOAD_BYTES = 512 * 1024 * 1024
MAX_DESKTOP_DATABASE_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024


class TaskNotFoundError(ValueError):
    pass


class TaskFileMissingError(FileNotFoundError):
    pass


class TaskStateError(ValueError):
    pass


class TaskUploadTooLargeError(ValueError):
    pass


class TaskPackageConflictError(ValueError):
    pass


def _encode_json(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


@lru_cache(maxsize=1)
def load_form_contract() -> tuple[list[dict], str, str]:
    try:
        raw = FORM_CONTRACT_PATH.read_bytes()
        document = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("正式附表契约读取失败。") from exc
    if not isinstance(document, dict) or document.get("contract_schema_version") != "1.0":
        raise RuntimeError("正式附表契约版本不受支持。")
    items = document.get("items")
    if not isinstance(items, list) or len(items) != 14 or not all(isinstance(v, dict) for v in items):
        raise RuntimeError("正式附表契约必须完整包含附表2.1～2.14。")
    codes = [item.get("form_code") for item in items]
    if any(not isinstance(code, str) or not code for code in codes) or len(codes) != len(set(codes)):
        raise RuntimeError("正式附表契约包含无效或重复 form_code。")
    return items, str(document["form_contract_version"]), sha256(raw).hexdigest()


def _build_context(payload: SurveyTaskCreate) -> dict:
    snapshot = get_snapshot()
    departments = {item.master_key: item for item in snapshot.departments}
    offices = {item.master_key: item for item in snapshot.offices}
    canals = {item.master_key: item for item in snapshot.canals}
    scopes = {item.stable_uid: item for item in snapshot.management_scopes}

    if payload.target_unit_type == "department":
        target = departments.get(payload.target_master_key)
        if target is None:
            raise ValueError("任务目标管理处不存在于当前正式主数据。")
        if target.status != "active":
            raise ValueError("已停用的管理处不能接收新调查任务。")
        department = target
        eligible_office_keys = {
            office.master_key for office in offices.values()
            if office.parent_master_key == department.master_key
            and office.status == "active"
        }
    else:
        target = offices.get(payload.target_master_key)
        if target is None:
            raise ValueError("任务目标水管所不存在于当前正式主数据。")
        if target.status != "active":
            raise ValueError("已停用的管理所不能接收新调查任务。")
        department = departments.get(target.parent_master_key)
        if department is None:
            raise RuntimeError("目标水管所缺少有效所属管理处。")
        if department.status != "active":
            raise ValueError("目标管理所所属管理处已停用。")
        eligible_office_keys = {target.master_key}

    selected = []
    for uid in payload.selected_management_scope_uids:
        scope = scopes.get(uid)
        if scope is None:
            raise ValueError(f"所选分管范围不存在：{uid}。")
        if scope.organization_master_key not in eligible_office_keys:
            raise ValueError("所选分管范围不属于任务目标单位。")
        if scope.status != "active":
            raise ValueError("调查任务不能包含停用的分管范围。")
        selected.append(scope)

    reference_canal_keys: set[str] = set()
    for scope in selected:
        current = canals.get(scope.canal_master_key)
        visited: set[str] = set()
        while current is not None:
            if current.status != "active":
                raise ValueError("调查任务不能包含已停用的渠道。")
            if current.master_key in visited:
                raise RuntimeError("正式渠系层级存在循环引用。")
            visited.add(current.master_key)
            reference_canal_keys.add(current.master_key)
            current = canals.get(current.parent_master_key) if current.parent_master_key else None

    selected_owner_keys = {scope.organization_master_key for scope in selected}
    reference_offices = sorted(
        (offices[key] for key in selected_owner_keys), key=lambda item: item.sort_order
    )
    reference_canals = [
        item for item in snapshot.canals if item.master_key in reference_canal_keys
    ]
    return {
        "snapshot": snapshot,
        "department": department,
        "target": target,
        "selected_scopes": selected,
        "reference_offices": reference_offices,
        "reference_canals": reference_canals,
        "offices": offices,
        "canals": canals,
    }


def _build_documents(
    *,
    project: Project,
    batch: SurveyBatch,
    payload: SurveyTaskCreate,
    task_uid: str,
    package_uid: str,
    created_at: str,
) -> tuple[dict, dict[str, bytes], dict]:
    context = _build_context(payload)
    snapshot = context["snapshot"]
    department = context["department"]
    target = context["target"]
    offices = context["offices"]
    canals = context["canals"]
    selected_scopes = context["selected_scopes"]
    form_items, form_version, form_hash = load_form_contract()

    organization_reference = [
        {
            "organization_uid": department.stable_uid,
            "parent_organization_uid": None,
            "name": department.name,
            "unit_type": "department",
            "business_code": department.business_code,
            "status": "active",
            "description": department.description,
            "sort_order": department.sort_order,
        }
    ]
    organization_reference.extend(
        {
            "organization_uid": office.stable_uid,
            "parent_organization_uid": department.stable_uid,
            "name": office.name,
            "unit_type": "water_office",
            "business_code": office.business_code,
            "status": "active",
            "description": office.description,
            "sort_order": office.sort_order,
        }
        for office in context["reference_offices"]
    )
    canal_reference = [
        {
            "canal_uid": canal.stable_uid,
            "parent_canal_uid": (
                canals[canal.parent_master_key].stable_uid
                if canal.parent_master_key else None
            ),
            "name": canal.name,
            "canal_level": canal.canal_level,
            "status": "active",
            "description": canal.description,
            "sort_order": canal.sort_order,
        }
        for canal in context["reference_canals"]
    ]
    scope_reference = [
        {
            "management_scope_uid": scope.stable_uid,
            "canal_uid": canals[scope.canal_master_key].stable_uid,
            "organization_unit_uid": offices[scope.organization_master_key].stable_uid,
            "range_mode": scope.range_mode,
            "start_stake_text": scope.start_stake_text,
            "start_stake_value": scope.start_stake_value,
            "end_stake_text": scope.end_stake_text,
            "end_stake_value": scope.end_stake_value,
            "sort_order": scope.sort_order,
            "status": scope.status,
            "description": scope.description,
        }
        for scope in selected_scopes
    ]
    task_document = {
        "task_schema_version": TASK_SCHEMA_VERSION,
        "task_uid": task_uid,
        "lineage": {"parent_task_uid": None, "root_task_uid": task_uid, "depth": 0},
        "task_name": payload.task_name,
        "notes": payload.notes,
        "project": {
            "project_uid": project.project_uid,
            "name": project.name,
            "short_name": project.short_name,
        },
        "survey_batch": {
            "survey_batch_uid": batch.survey_batch_uid,
            "batch_name": batch.batch_name,
            "batch_code": batch.batch_code,
            "start_date": batch.start_date.isoformat() if batch.start_date else None,
            "end_date": batch.end_date.isoformat() if batch.end_date else None,
        },
        "assignment": {
            "target_unit_type": payload.target_unit_type,
            "department_uid": department.stable_uid,
            "department_name": department.name,
            "organization_unit_uid": target.stable_uid,
            "organization_name": target.name,
        },
        "scope": {
            "selected_management_scope_uids": [item.stable_uid for item in selected_scopes],
            "selected_management_scope_count": len(selected_scopes),
        },
        "created_at": created_at,
    }
    payload_files = {
        "task.json": _encode_json(task_document),
        "reference/organization_units.json": _encode_json({"items": organization_reference}),
        "reference/canal_units.json": _encode_json({"items": canal_reference}),
        "reference/canal_management_scopes.json": _encode_json({"items": scope_reference}),
        "reference/forms.json": _encode_json({"items": form_items}),
    }
    manifest = {
        "package_kind": PACKAGE_KIND,
        "task_schema_version": TASK_SCHEMA_VERSION,
        "created_at": created_at,
        "app_version": APP_VERSION,
        "app_version_label": APP_VERSION_LABEL,
        "task_uid": task_uid,
        "parent_task_uid": None,
        "root_task_uid": task_uid,
        "task_depth": 0,
        "project_uid": project.project_uid,
        "survey_batch_uid": batch.survey_batch_uid,
    }
    frozen = {
        "task": task_document,
        "organizations": organization_reference,
        "canals": canal_reference,
        "management_scopes": [
            {
                **item,
                "canal_name": canals[scope.canal_master_key].name,
                "organization_name": offices[scope.organization_master_key].name,
            }
            for item, scope in zip(scope_reference, selected_scopes, strict=True)
        ],
        "forms": form_items,
        "master_data_version": snapshot.summary.master_data_version,
        "master_contract_sha256": snapshot.summary.contract_sha256,
        "form_contract_version": form_version,
        "form_contract_sha256": form_hash,
    }
    return manifest, payload_files, frozen


def _write_package(path: Path, package_uid: str, manifest: dict, payload_files: dict[str, bytes]) -> None:
    entries = [
        {"path": name, "sha256": sha256(content).hexdigest(), "size": len(content)}
        for name, content in sorted(payload_files.items())
    ]
    manifest_bytes = _encode_json(
        {**manifest, "package_uid": package_uid, "package_format_version": PACKAGE_FORMAT_VERSION, "files": entries}
    )
    path.parent.mkdir(parents=True, exist_ok=False)
    temporary = path.with_suffix(".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in sorted(payload_files.items()):
                archive.writestr(name, content)
            archive.writestr("manifest.json", manifest_bytes)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        shutil.rmtree(path.parent, ignore_errors=True)
        raise


def create_task(db: Session, payload: SurveyTaskCreate, creator: User) -> SurveyTask:
    project = db.scalar(select(Project).where(Project.project_uid == payload.project_uid))
    batch = db.scalar(select(SurveyBatch).where(SurveyBatch.survey_batch_uid == payload.survey_batch_uid))
    if project is None:
        raise ValueError("指定项目不存在。")
    if batch is None or batch.project_id != project.id:
        raise ValueError("指定调查批次不存在或不属于当前项目。")
    if project.status != "active" or batch.status != "active":
        raise ValueError("只能为启用项目中的进行中调查批次创建任务。")

    task_uid = uuid4().hex
    package_uid = uuid4().hex
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest, payload_files, frozen = _build_documents(
        project=project,
        batch=batch,
        payload=payload,
        task_uid=task_uid,
        package_uid=package_uid,
        created_at=created_at,
    )
    now = datetime.now().astimezone()
    final_path = TASK_STORAGE_ROOT / f"{now.year:04d}" / f"{now.month:02d}" / task_uid / "package.ydtask"
    _write_package(final_path, package_uid, manifest, payload_files)
    file_bytes = final_path.read_bytes()
    assignment = frozen["task"]["assignment"]
    row = SurveyTask(
        task_uid=task_uid,
        package_uid=package_uid,
        project_id=project.id,
        survey_batch_id=batch.id,
        task_name=payload.task_name,
        notes=payload.notes,
        target_unit_type=payload.target_unit_type,
        department_uid=assignment["department_uid"],
        department_name=assignment["department_name"],
        organization_unit_uid=assignment["organization_unit_uid"],
        organization_name=assignment["organization_name"],
        parent_task_uid=None,
        root_task_uid=task_uid,
        task_depth=0,
        selected_scope_uids=frozen["task"]["scope"]["selected_management_scope_uids"],
        frozen_snapshot_json=frozen,
        selected_scope_count=len(frozen["management_scopes"]),
        reference_canal_count=len(frozen["canals"]),
        reference_organization_count=len(frozen["organizations"]),
        form_count=len(frozen["forms"]),
        stored_relative_path=final_path.relative_to(BACKEND_ROOT).as_posix(),
        file_sha256=sha256(file_bytes).hexdigest(),
        file_size=len(file_bytes),
        status="issued",
        created_by_user_uid=creator.user_uid,
        created_by_username=creator.username,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        shutil.rmtree(final_path.parent, ignore_errors=True)
        raise
    return row


def _parse_package_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


async def _save_task_upload(upload: UploadFile, target: Path) -> tuple[str, int]:
    digest = sha256()
    size = 0
    with target.open("wb") as output:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_TASK_UPLOAD_BYTES:
                raise TaskUploadTooLargeError("任务文件超过当前 512 MiB 安全上限。")
            digest.update(chunk)
            output.write(chunk)
    return digest.hexdigest(), size


async def _save_desktop_database_upload(upload: UploadFile, target: Path) -> tuple[str, int]:
    digest = sha256()
    size = 0
    with target.open("wb") as output:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_DESKTOP_DATABASE_UPLOAD_BYTES:
                raise TaskUploadTooLargeError("数据库备份超过当前 4 GiB 安全上限。")
            digest.update(chunk)
            output.write(chunk)
    return digest.hexdigest(), size


def _task_package_reader(path: Path):
    desktop_src = REPOSITORY_ROOT / "src"
    desktop_src_text = str(desktop_src)
    if desktop_src_text not in sys.path:
        sys.path.insert(0, desktop_src_text)
    from services.survey_task_package_reader import load_survey_task_package

    return load_survey_task_package(path)


def _legacy_frozen_snapshot(contents, *, filename: str) -> dict:
    task = dict(contents.task)
    organizations = [dict(item) for item in contents.organizations]
    canals = [dict(item) for item in contents.canals]
    scopes = [dict(item) for item in contents.management_scopes]
    forms = [dict(item) for item in contents.forms]
    organization_names = {
        str(item.get("organization_uid") or ""): str(item.get("name") or "")
        for item in organizations
    }
    canal_names = {
        str(item.get("canal_uid") or ""): str(item.get("name") or "")
        for item in canals
    }
    for item in scopes:
        item["organization_name"] = organization_names.get(
            str(item.get("organization_unit_uid") or ""), ""
        )
        item["canal_name"] = canal_names.get(str(item.get("canal_uid") or ""), "")
    form_versions = {
        str(item.get("version_code") or "") for item in forms if item.get("version_code")
    }
    return {
        "task": task,
        "organizations": organizations,
        "canals": canals,
        "management_scopes": scopes,
        "forms": forms,
        "master_data_version": "任务下发时桌面端快照",
        "master_contract_sha256": "",
        "form_contract_version": "、".join(sorted(form_versions)) or "桌面端任务包快照",
        "form_contract_sha256": "",
        "handover": {
            "source": "desktop_existing_task",
            "original_filename": filename,
            "registered_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
    }


async def import_existing_task_package(
    db: Session,
    *,
    upload: UploadFile,
    importer: User,
) -> tuple[SurveyTask, bool]:
    """Register a task already issued by the production desktop system.

    The original package and every stable UID are preserved.  This gives the
    Web center the immutable issued-task evidence it needs to accept the
    corresponding historical or still-outstanding result packages.
    """
    filename = Path(upload.filename or "desktop-task.ydtask").name.strip()
    if not filename.lower().endswith(".ydtask"):
        raise ValueError("请选择由桌面端生成的调查任务文件（.ydtask）。")
    TASK_INCOMING_ROOT.mkdir(parents=True, exist_ok=True)
    incoming_uid = uuid4().hex
    temp_path = TASK_INCOMING_ROOT / f"{incoming_uid}.part"
    try:
        file_sha256, file_size = await _save_task_upload(upload, temp_path)
        try:
            contents = _task_package_reader(temp_path)
        except ValueError as exc:
            raise ValueError("任务文件检查未通过，请使用桌面端原始任务文件。") from exc

        manifest = dict(contents.manifest)
        task = dict(contents.task)
        task_uid = str(task["task_uid"])
        package_uid = str(manifest.get("package_uid") or "")
        if len(package_uid) != 32:
            raise ValueError("任务文件缺少有效的文件身份信息。")

        existing = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid))
        if existing is not None:
            if existing.file_sha256 == file_sha256:
                return existing, True
            raise TaskPackageConflictError("相同任务已经登记，但文件内容不同，请核对原始任务文件。")
        package_owner = db.scalar(select(SurveyTask).where(SurveyTask.package_uid == package_uid))
        if package_owner is not None:
            raise TaskPackageConflictError("该任务文件身份已经被其他任务占用，请核对原始文件。")

        project_doc = task.get("project") if isinstance(task.get("project"), dict) else {}
        batch_doc = task.get("survey_batch") if isinstance(task.get("survey_batch"), dict) else {}
        project_uid = str(project_doc.get("project_uid") or "")
        batch_uid = str(batch_doc.get("survey_batch_uid") or "")
        project = db.scalar(select(Project).where(Project.project_uid == project_uid))
        if project is None:
            project = Project(
                project_uid=project_uid,
                name=str(project_doc.get("name") or "桌面端历史调查项目")[:200],
                short_name=(str(project_doc.get("short_name") or "").strip()[:100] or None),
                status="active",
            )
            db.add(project)
            db.flush()
        batch = db.scalar(select(SurveyBatch).where(SurveyBatch.survey_batch_uid == batch_uid))
        if batch is None:
            batch = SurveyBatch(
                survey_batch_uid=batch_uid,
                project_id=project.id,
                batch_name=str(batch_doc.get("batch_name") or "桌面端历史调查批次")[:200],
                batch_code=str(batch_doc.get("batch_code") or f"HISTORY-{batch_uid[:8]}")[:50],
                start_date=_parse_package_date(batch_doc.get("start_date")),
                end_date=_parse_package_date(batch_doc.get("end_date")),
                status="active",
            )
            db.add(batch)
            db.flush()
        elif batch.project_id != project.id:
            raise TaskPackageConflictError("任务文件中的项目与调查批次归属不一致。")

        frozen = _legacy_frozen_snapshot(contents, filename=filename)
        assignment = task.get("assignment") if isinstance(task.get("assignment"), dict) else {}
        scope = task.get("scope") if isinstance(task.get("scope"), dict) else {}
        lineage = task.get("lineage") if isinstance(task.get("lineage"), dict) else {}
        selected_uids = [str(value) for value in scope.get("selected_management_scope_uids", [])]
        target_type = str(assignment.get("target_unit_type") or "water_office")
        parent_task_uid = lineage.get("parent_task_uid")
        root_task_uid = str(lineage.get("root_task_uid") or task_uid)
        task_depth = int(lineage.get("depth") or 0)

        now = datetime.now().astimezone()
        final_dir = TASK_STORAGE_ROOT / "handover" / f"{now.year:04d}" / f"{now.month:02d}" / task_uid
        final_dir.mkdir(parents=True, exist_ok=False)
        final_path = final_dir / "package.ydtask"
        shutil.move(str(temp_path), str(final_path))
        row = SurveyTask(
            task_uid=task_uid,
            package_uid=package_uid,
            project_id=project.id,
            survey_batch_id=batch.id,
            task_name=str(task.get("task_name") or "桌面端历史调查任务")[:240],
            notes=(str(task.get("notes") or "").strip()[:2000] or None),
            target_unit_type=target_type,
            department_uid=str(assignment.get("department_uid") or ""),
            department_name=str(assignment.get("department_name") or ""),
            organization_unit_uid=str(assignment.get("organization_unit_uid") or ""),
            organization_name=str(assignment.get("organization_name") or ""),
            parent_task_uid=str(parent_task_uid) if parent_task_uid else None,
            root_task_uid=root_task_uid,
            task_depth=task_depth,
            selected_scope_uids=selected_uids,
            frozen_snapshot_json=frozen,
            selected_scope_count=len(selected_uids),
            reference_canal_count=len(contents.canals),
            reference_organization_count=len(contents.organizations),
            form_count=len(contents.forms),
            stored_relative_path=final_path.relative_to(BACKEND_ROOT).as_posix(),
            file_sha256=file_sha256,
            file_size=file_size,
            status="downloaded",
            download_count=1,
            first_downloaded_at=now,
            last_downloaded_at=now,
            created_by_user_uid=importer.user_uid,
            created_by_username=importer.username,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            shutil.rmtree(final_dir, ignore_errors=True)
            raise
        return row, False
    finally:
        temp_path.unlink(missing_ok=True)
        await upload.close()


_HEX_UID = re.compile(r"^[0-9a-f]{32}$")
_DESKTOP_DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_DESKTOP_HISTORY_REQUIRED_COLUMNS = {
    "id",
    "task_uid",
    "source_package_uid",
    "project_uid",
    "project_name_snapshot",
    "survey_batch_uid",
    "batch_name_snapshot",
    "batch_code_snapshot",
    "department_uid",
    "department_name_snapshot",
    "organization_unit_uid",
    "organization_name_snapshot",
    "task_name",
    "selected_scope_count",
    "task_created_at",
}
_DESKTOP_SCOPE_REQUIRED_COLUMNS = {
    "task_issue_id",
    "management_scope_uid",
    "canal_unit_uid",
    "organization_unit_uid",
    "canal_name_snapshot",
    "canal_level_snapshot",
    "range_mode",
    "sort_order",
    "source_scope_status",
}


def _desktop_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _desktop_table_rows(connection: sqlite3.Connection, table_name: str) -> list[dict]:
    if not _desktop_table_columns(connection, table_name):
        return []
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table_name}").fetchall()]


def _require_desktop_uid(value: object, field_name: str) -> str:
    uid = str(value or "").strip()
    if not _HEX_UID.fullmatch(uid):
        raise ValueError(f"{field_name} 不是有效的 32 位任务身份。")
    return uid


def _desktop_organization_reference(issue: dict, scopes: list[dict], source_rows: list[dict]) -> list[dict]:
    source_by_uid = {
        str(row.get("organization_unit_uid") or ""): row
        for row in source_rows
        if row.get("organization_unit_uid")
    }
    department_uid = _require_desktop_uid(issue.get("department_uid"), "department_uid")
    target_uid = _require_desktop_uid(issue.get("organization_unit_uid"), "organization_unit_uid")
    target_type = str(issue.get("target_unit_type") or "water_office").strip()
    if target_type not in {"department", "water_office"}:
        raise ValueError("任务目标单位类型不受支持。")
    if target_type == "department" and target_uid != department_uid:
        raise ValueError("处级任务的目标单位身份与所属管理处不一致。")

    owner_uids = {
        _require_desktop_uid(row.get("organization_unit_uid"), "scope.organization_unit_uid")
        for row in scopes
    }
    if target_type == "water_office" and owner_uids != {target_uid}:
        raise ValueError("水管所任务包含了其他单位的分管范围。")

    department_source = source_by_uid.get(department_uid, {})
    result = [
        {
            "organization_uid": department_uid,
            "parent_organization_uid": None,
            "name": str(issue.get("department_name_snapshot") or "历史管理处"),
            "unit_type": "department",
            "business_code": department_source.get("business_code"),
            "status": "active",
            "description": department_source.get("description"),
            "sort_order": int(department_source.get("sort_order") or 0),
        }
    ]
    office_uids = owner_uids | ({target_uid} if target_type == "water_office" else set())
    for index, uid in enumerate(sorted(office_uids), start=1):
        source = source_by_uid.get(uid, {})
        name = (
            str(issue.get("organization_name_snapshot") or "")
            if uid == target_uid
            else str(source.get("name") or "")
        )
        result.append(
            {
                "organization_uid": uid,
                "parent_organization_uid": department_uid,
                "name": name or f"历史分管单位（{uid[:8]}）",
                "unit_type": "water_office",
                "business_code": source.get("business_code"),
                "status": "active",
                "description": source.get("description"),
                "sort_order": int(source.get("sort_order") or index),
            }
        )
    return result


def _desktop_canal_reference(scopes: list[dict], source_rows: list[dict]) -> list[dict]:
    source_by_uid = {
        str(row.get("canal_unit_uid") or ""): row
        for row in source_rows
        if row.get("canal_unit_uid")
    }
    uid_by_id = {
        row.get("id"): str(row.get("canal_unit_uid"))
        for row in source_rows
        if row.get("id") is not None and row.get("canal_unit_uid")
    }
    snapshots: dict[str, dict] = {}
    for scope in scopes:
        uid = _require_desktop_uid(scope.get("canal_unit_uid"), "scope.canal_unit_uid")
        snapshot = {
            "name": str(scope.get("canal_name_snapshot") or "").strip(),
            "canal_level": str(scope.get("canal_level_snapshot") or "").strip(),
        }
        if not snapshot["name"] or snapshot["canal_level"] not in {"01", "02", "03", "04"}:
            raise ValueError("下发历史中的渠道快照不完整。")
        if uid in snapshots and snapshots[uid] != snapshot:
            raise ValueError("同一渠道在下发历史中存在互相冲突的冻结名称或级别。")
        snapshots[uid] = snapshot

    included = set(snapshots)
    pending = list(included)
    while pending:
        row = source_by_uid.get(pending.pop())
        parent_uid = uid_by_id.get(row.get("parent_id")) if row else None
        if parent_uid and parent_uid not in included:
            included.add(parent_uid)
            pending.append(parent_uid)

    result = []
    for uid in included:
        source = source_by_uid.get(uid, {})
        parent_uid = uid_by_id.get(source.get("parent_id"))
        frozen = snapshots.get(uid, {})
        level = str(frozen.get("canal_level") or source.get("canal_level") or "04")
        if level not in {"01", "02", "03", "04"}:
            level = "04"
        result.append(
            {
                "canal_uid": uid,
                "parent_canal_uid": parent_uid if parent_uid in included else None,
                "name": str(frozen.get("name") or source.get("name") or f"历史渠道（{uid[:8]}）"),
                "canal_level": level,
                "status": "active",
                "description": source.get("description"),
                "sort_order": int(source.get("sort_order") or 0),
            }
        )
    return sorted(result, key=lambda item: (item["sort_order"], item["name"], item["canal_uid"]))


def _build_desktop_history_documents(
    issue: dict,
    scopes: list[dict],
    *,
    organization_rows: list[dict],
    canal_rows: list[dict],
    source_filename: str,
    database_sha256: str,
) -> tuple[str, str, dict, dict[str, bytes], dict]:
    task_uid = _require_desktop_uid(issue.get("task_uid"), "task_uid")
    package_uid = _require_desktop_uid(issue.get("source_package_uid"), "source_package_uid")
    project_uid = _require_desktop_uid(issue.get("project_uid"), "project_uid")
    batch_uid = _require_desktop_uid(issue.get("survey_batch_uid"), "survey_batch_uid")
    if not scopes or int(issue.get("selected_scope_count") or 0) != len(scopes):
        raise ValueError("任务下发历史中的分管范围数量不一致。")
    if any(str(item.get("source_scope_status") or "") != "active" for item in scopes):
        raise ValueError("任务下发历史包含非启用范围，无法重建原始正式任务。")

    target_type = str(issue.get("target_unit_type") or "water_office").strip()
    organizations = _desktop_organization_reference(issue, scopes, organization_rows)
    canals = _desktop_canal_reference(scopes, canal_rows)
    organization_names = {item["organization_uid"]: item["name"] for item in organizations}
    management_scopes = []
    for item in scopes:
        range_mode = str(item.get("range_mode") or "")
        if range_mode not in {"whole", "segment_known", "segment_unknown"}:
            raise ValueError("任务下发历史包含无效的分段方式。")
        management_scopes.append(
            {
                "management_scope_uid": _require_desktop_uid(
                    item.get("management_scope_uid"), "management_scope_uid"
                ),
                "canal_uid": _require_desktop_uid(item.get("canal_unit_uid"), "canal_unit_uid"),
                "organization_unit_uid": _require_desktop_uid(
                    item.get("organization_unit_uid"), "organization_unit_uid"
                ),
                "range_mode": range_mode,
                "start_stake_text": item.get("start_stake_text"),
                "start_stake_value": item.get("start_stake_value"),
                "end_stake_text": item.get("end_stake_text"),
                "end_stake_value": item.get("end_stake_value"),
                "sort_order": int(item.get("sort_order") or 0),
                "status": "active",
                "description": item.get("description"),
            }
        )
    selected_uids = [item["management_scope_uid"] for item in management_scopes]
    if len(selected_uids) != len(set(selected_uids)):
        raise ValueError("任务下发历史包含重复的分管范围身份。")

    parent_task_uid = str(issue.get("parent_task_uid") or "").strip() or None
    root_task_uid = str(issue.get("root_task_uid") or "").strip() or task_uid
    if parent_task_uid:
        _require_desktop_uid(parent_task_uid, "parent_task_uid")
    _require_desktop_uid(root_task_uid, "root_task_uid")
    task_depth = int(issue.get("task_depth") or 0)
    if task_depth < 0:
        raise ValueError("任务层级不能小于零。")

    created_at = str(issue.get("task_created_at") or issue.get("issued_at") or "").strip()
    if not created_at:
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    task_document = {
        "task_schema_version": TASK_SCHEMA_VERSION,
        "task_uid": task_uid,
        "lineage": {
            "parent_task_uid": parent_task_uid,
            "root_task_uid": root_task_uid,
            "depth": task_depth,
        },
        "task_name": str(issue.get("task_name") or "桌面端历史调查任务"),
        "notes": str(issue.get("notes") or "").strip() or None,
        "project": {
            "project_uid": project_uid,
            "name": str(issue.get("project_name_snapshot") or "桌面端历史调查项目"),
            "short_name": str(issue.get("project_short_name_snapshot") or "").strip() or None,
        },
        "survey_batch": {
            "survey_batch_uid": batch_uid,
            "batch_name": str(issue.get("batch_name_snapshot") or "桌面端历史调查批次"),
            "batch_code": str(issue.get("batch_code_snapshot") or f"HISTORY-{batch_uid[:8]}"),
            "start_date": issue.get("batch_start_date_snapshot"),
            "end_date": issue.get("batch_end_date_snapshot"),
        },
        "assignment": {
            "target_unit_type": target_type,
            "department_uid": str(issue.get("department_uid")),
            "department_name": str(issue.get("department_name_snapshot") or "历史管理处"),
            "organization_unit_uid": str(issue.get("organization_unit_uid")),
            "organization_name": str(issue.get("organization_name_snapshot") or "历史任务单位"),
        },
        "scope": {
            "selected_management_scope_uids": selected_uids,
            "selected_management_scope_count": len(selected_uids),
        },
        "created_at": created_at,
    }
    form_items, form_version, form_hash = load_form_contract()
    payload_files = {
        "task.json": _encode_json(task_document),
        "reference/organization_units.json": _encode_json({"items": organizations}),
        "reference/canal_units.json": _encode_json({"items": canals}),
        "reference/canal_management_scopes.json": _encode_json({"items": management_scopes}),
        "reference/forms.json": _encode_json({"items": form_items}),
    }
    manifest = {
        "package_kind": PACKAGE_KIND,
        "task_schema_version": TASK_SCHEMA_VERSION,
        "created_at": created_at,
        "app_version": str(issue.get("app_version") or APP_VERSION),
        "app_version_label": f"V{str(issue.get('app_version') or APP_VERSION).lstrip('Vv')}",
        "task_uid": task_uid,
        "parent_task_uid": parent_task_uid,
        "root_task_uid": root_task_uid,
        "task_depth": task_depth,
        "project_uid": project_uid,
        "survey_batch_uid": batch_uid,
    }
    canal_names = {item["canal_uid"]: item["name"] for item in canals}
    frozen_scopes = [
        {
            **item,
            "canal_name": canal_names.get(item["canal_uid"], ""),
            "organization_name": organization_names.get(item["organization_unit_uid"], ""),
        }
        for item in management_scopes
    ]
    frozen = {
        "task": task_document,
        "organizations": organizations,
        "canals": canals,
        "management_scopes": frozen_scopes,
        "forms": form_items,
        "master_data_version": "桌面端正式下发历史快照",
        "master_contract_sha256": "",
        "form_contract_version": form_version,
        "form_contract_sha256": form_hash,
        "handover": {
            "source": "desktop_database_handover",
            "original_filename": source_filename,
            "database_sha256": database_sha256,
            "registered_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
    }
    return task_uid, package_uid, manifest, payload_files, frozen


def _ensure_handover_project_batch(db: Session, issue: dict) -> tuple[Project, SurveyBatch, bool, bool]:
    project_uid = _require_desktop_uid(issue.get("project_uid"), "project_uid")
    batch_uid = _require_desktop_uid(issue.get("survey_batch_uid"), "survey_batch_uid")
    project = db.scalar(select(Project).where(Project.project_uid == project_uid))
    created_project = project is None
    if project is None:
        project = Project(
            project_uid=project_uid,
            name=str(issue.get("project_name_snapshot") or "桌面端历史调查项目")[:200],
            short_name=(str(issue.get("project_short_name_snapshot") or "").strip()[:100] or None),
            status="active",
        )
        db.add(project)
        db.flush()

    batch = db.scalar(select(SurveyBatch).where(SurveyBatch.survey_batch_uid == batch_uid))
    created_batch = batch is None
    if batch is None:
        batch_code = str(issue.get("batch_code_snapshot") or f"HISTORY-{batch_uid[:8]}")[:50]
        code_owner = db.scalar(
            select(SurveyBatch).where(
                SurveyBatch.project_id == project.id,
                SurveyBatch.batch_code == batch_code,
            )
        )
        if code_owner is not None:
            raise TaskPackageConflictError(
                f"批次编号“{batch_code}”已由另一批次使用，请先核对项目批次。"
            )
        batch = SurveyBatch(
            survey_batch_uid=batch_uid,
            project_id=project.id,
            batch_name=str(issue.get("batch_name_snapshot") or "桌面端历史调查批次")[:200],
            batch_code=batch_code,
            start_date=_parse_package_date(issue.get("batch_start_date_snapshot")),
            end_date=_parse_package_date(issue.get("batch_end_date_snapshot")),
            status="active",
        )
        db.add(batch)
        db.flush()
    elif batch.project_id != project.id:
        raise TaskPackageConflictError("桌面下发历史中的项目与调查批次归属不一致。")
    return project, batch, created_project, created_batch


async def import_desktop_task_history_database(
    db: Session,
    *,
    upload: UploadFile,
    importer: User,
) -> dict:
    """Read immutable issued-task history from a desktop SQLite backup.

    The source is opened read-only and is never migrated or modified. Drafts,
    current survey records and media are intentionally outside this handover.
    """
    filename = Path(upload.filename or "desktop-backup.db").name.strip()
    if Path(filename).suffix.lower() not in _DESKTOP_DATABASE_SUFFIXES:
        raise ValueError("请选择桌面端数据库备份文件（.db、.sqlite 或 .sqlite3）。")
    TASK_INCOMING_ROOT.mkdir(parents=True, exist_ok=True)
    temp_path = TASK_INCOMING_ROOT / f"{uuid4().hex}.sqlite.part"
    try:
        database_sha256, _ = await _save_desktop_database_upload(upload, temp_path)
        with temp_path.open("rb") as source:
            header = source.read(16)
        if header != b"SQLite format 3\x00":
            raise ValueError("所选文件不是有效的 SQLite 数据库备份。")
        try:
            connection = sqlite3.connect(
                f"{temp_path.resolve().as_uri()}?mode=ro&immutable=1",
                uri=True,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
        except sqlite3.Error as exc:
            raise ValueError("数据库备份无法以只读方式打开，请重新制作完整备份。") from exc

        try:
            issue_columns = _desktop_table_columns(connection, "survey_task_issues")
            scope_columns = _desktop_table_columns(connection, "survey_task_issue_scopes")
            if not issue_columns or not scope_columns:
                raise ValueError("该数据库没有正式任务下发历史，请改用原始 .ydtask 文件接续。")
            missing_issue = _DESKTOP_HISTORY_REQUIRED_COLUMNS - issue_columns
            missing_scope = _DESKTOP_SCOPE_REQUIRED_COLUMNS - scope_columns
            if missing_issue or missing_scope:
                raise ValueError("任务下发历史结构不完整，请先使用当前桌面端完成数据库升级。")

            issues = [dict(row) for row in connection.execute("SELECT * FROM survey_task_issues ORDER BY id")]
            scope_rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM survey_task_issue_scopes ORDER BY task_issue_id, sort_order, id"
                )
            ]
            scopes_by_issue: dict[int, list[dict]] = {}
            for row in scope_rows:
                scopes_by_issue.setdefault(int(row["task_issue_id"]), []).append(row)
            organization_rows = _desktop_table_rows(connection, "organization_units")
            canal_rows = _desktop_table_rows(connection, "canal_units")
        finally:
            connection.close()

        report = {
            "source_filename": filename,
            "database_sha256": database_sha256,
            "discovered_tasks": len(issues),
            "imported_tasks": 0,
            "existing_tasks": 0,
            "conflict_tasks": 0,
            "created_projects": 0,
            "created_batches": 0,
            "imported_task_uids": [],
            "issues": [],
        }
        created_project_uids: set[str] = set()
        created_batch_uids: set[str] = set()
        for issue in issues:
            label = str(issue.get("task_name") or issue.get("task_uid") or "未命名任务")
            final_dir: Path | None = None
            try:
                task_uid = _require_desktop_uid(issue.get("task_uid"), "task_uid")
                package_uid = _require_desktop_uid(issue.get("source_package_uid"), "source_package_uid")
                existing = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid))
                if existing is not None:
                    if existing.package_uid == package_uid:
                        report["existing_tasks"] += 1
                        continue
                    raise TaskPackageConflictError("相同任务身份已登记，但任务文件身份不同。")
                package_owner = db.scalar(select(SurveyTask).where(SurveyTask.package_uid == package_uid))
                if package_owner is not None:
                    raise TaskPackageConflictError("任务文件身份已由另一个任务占用。")

                task_uid, package_uid, manifest, payload_files, frozen = _build_desktop_history_documents(
                    issue,
                    scopes_by_issue.get(int(issue["id"]), []),
                    organization_rows=organization_rows,
                    canal_rows=canal_rows,
                    source_filename=filename,
                    database_sha256=database_sha256,
                )
                project, batch, created_project, created_batch = _ensure_handover_project_batch(db, issue)
                final_dir = TASK_STORAGE_ROOT / "handover-db" / task_uid
                final_path = final_dir / "package.ydtask"
                _write_package(final_path, package_uid, manifest, payload_files)
                _task_package_reader(final_path)
                file_bytes = final_path.read_bytes()
                task = frozen["task"]
                assignment = task["assignment"]
                lineage = task["lineage"]
                now = datetime.now().astimezone()
                row = SurveyTask(
                    task_uid=task_uid,
                    package_uid=package_uid,
                    project_id=project.id,
                    survey_batch_id=batch.id,
                    task_name=str(task["task_name"])[:240],
                    notes=(str(task.get("notes") or "").strip()[:2000] or None),
                    target_unit_type=str(assignment["target_unit_type"]),
                    department_uid=str(assignment["department_uid"]),
                    department_name=str(assignment["department_name"]),
                    organization_unit_uid=str(assignment["organization_unit_uid"]),
                    organization_name=str(assignment["organization_name"]),
                    parent_task_uid=lineage["parent_task_uid"],
                    root_task_uid=str(lineage["root_task_uid"]),
                    task_depth=int(lineage["depth"]),
                    selected_scope_uids=list(task["scope"]["selected_management_scope_uids"]),
                    frozen_snapshot_json=frozen,
                    selected_scope_count=len(frozen["management_scopes"]),
                    reference_canal_count=len(frozen["canals"]),
                    reference_organization_count=len(frozen["organizations"]),
                    form_count=len(frozen["forms"]),
                    stored_relative_path=final_path.relative_to(BACKEND_ROOT).as_posix(),
                    file_sha256=sha256(file_bytes).hexdigest(),
                    file_size=len(file_bytes),
                    status="downloaded",
                    download_count=1,
                    first_downloaded_at=now,
                    last_downloaded_at=now,
                    created_by_user_uid=importer.user_uid,
                    created_by_username=importer.username,
                )
                db.add(row)
                db.commit()
                report["imported_tasks"] += 1
                report["imported_task_uids"].append(task_uid)
                if created_project:
                    created_project_uids.add(project.project_uid)
                if created_batch:
                    created_batch_uids.add(batch.survey_batch_uid)
            except Exception as exc:
                db.rollback()
                if final_dir is not None:
                    shutil.rmtree(final_dir, ignore_errors=True)
                report["conflict_tasks"] += 1
                if len(report["issues"]) < 100:
                    report["issues"].append(f"{label}：{str(exc) or '无法接续'}")
        report["created_projects"] = len(created_project_uids)
        report["created_batches"] = len(created_batch_uids)
        return report
    except sqlite3.Error as exc:
        raise ValueError("数据库备份读取失败，请确认备份完整且未损坏。") from exc
    finally:
        temp_path.unlink(missing_ok=True)
        await upload.close()


def list_tasks(
    db: Session,
    *,
    project_uid: str | None = None,
    survey_batch_uid: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[tuple[SurveyTask, Project, SurveyBatch]], int]:
    filters = []
    if project_uid:
        filters.append(Project.project_uid == project_uid)
    if survey_batch_uid:
        filters.append(SurveyBatch.survey_batch_uid == survey_batch_uid)
    if status:
        filters.append(SurveyTask.status == status)
    base = (
        select(SurveyTask, Project, SurveyBatch)
        .join(Project, Project.id == SurveyTask.project_id)
        .join(SurveyBatch, SurveyBatch.id == SurveyTask.survey_batch_id)
        .where(*filters)
    )
    count_query = (
        select(func.count()).select_from(SurveyTask)
        .join(Project, Project.id == SurveyTask.project_id)
        .join(SurveyBatch, SurveyBatch.id == SurveyTask.survey_batch_id)
        .where(*filters)
    )
    rows = list(db.execute(base.order_by(SurveyTask.created_at.desc()).limit(limit).offset(offset)).all())
    return rows, int(db.scalar(count_query) or 0)


def get_task(db: Session, task_uid: str) -> tuple[SurveyTask, Project, SurveyBatch] | None:
    return db.execute(
        select(SurveyTask, Project, SurveyBatch)
        .join(Project, Project.id == SurveyTask.project_id)
        .join(SurveyBatch, SurveyBatch.id == SurveyTask.survey_batch_id)
        .where(SurveyTask.task_uid == task_uid)
    ).one_or_none()


def task_file_path(row: SurveyTask) -> Path:
    path = (BACKEND_ROOT / row.stored_relative_path).resolve()
    root = TASK_STORAGE_ROOT.resolve()
    if path == root or root not in path.parents:
        raise RuntimeError("任务包存储路径越界。")
    if not path.is_file():
        raise TaskFileMissingError("服务器上的任务包文件不存在。")
    if sha256(path.read_bytes()).hexdigest() != row.file_sha256:
        raise RuntimeError("服务器上的任务包完整性校验失败。")
    return path


def register_download(db: Session, row: SurveyTask) -> None:
    now = datetime.now().astimezone()
    row.download_count += 1
    row.first_downloaded_at = row.first_downloaded_at or now
    row.last_downloaded_at = now
    if row.status == "issued":
        row.status = "downloaded"
    db.commit()


def cancel_task(db: Session, row: SurveyTask) -> SurveyTask:
    if row.status in {"result_received", "closed"}:
        raise TaskStateError("已有成果返回或已关闭的任务不能取消。")
    row.status = "cancelled"
    db.commit()
    db.refresh(row)
    return row


def safe_download_name(row: SurveyTask, batch: SurveyBatch) -> str:
    base = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", f"{batch.batch_code}_{row.organization_name}_{row.task_name}")
    return f"{base[:160]}_{row.task_uid[:8]}.ydtask"
