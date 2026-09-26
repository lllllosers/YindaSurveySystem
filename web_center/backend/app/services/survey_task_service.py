from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
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
