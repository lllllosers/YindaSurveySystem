from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import zipfile

import database

from services.database_backup import (
    create_database_backup,
)
from services.survey_result_import_preflight import (
    preflight_survey_result_import,
)
from services.survey_result_package_reader import (
    load_survey_result_package,
)


@dataclass(frozen=True)
class SurveyResultImportResult:
    package_path: Path
    package_uid: str
    result_uid: str

    backup_path: Path | None
    managed_package_path: Path | None

    # 旧公开结果字段保持构造兼容。
    imported_assets: int
    existing_assets: int

    imported_records: int
    existing_records: int

    imported_inspections: int
    existing_inspections: int

    imported_media: int
    existing_media: int

    already_imported: bool

    # V1.0.2 新增统计放到末尾并给默认值。
    updated_assets: int = 0
    stale_assets: int = 0
    updated_records: int = 0
    stale_records: int = 0
    updated_inspections: int = 0

def ensure_survey_result_import_schema():
    """
    成果包导入审计表。

    package_uid / result_uid 都只允许成功接收一次。
    失败事务不会写入 completed 记录。
    """

    with database.get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                survey_result_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    package_uid TEXT NOT NULL UNIQUE,
                    result_uid TEXT NOT NULL UNIQUE,

                    package_sha256 TEXT NOT NULL,

                    project_uid TEXT NOT NULL,
                    survey_batch_uid TEXT NOT NULL,

                    source_package_name TEXT NOT NULL,
                    managed_package_relative_path TEXT,

                    summary_json TEXT NOT NULL
                        DEFAULT '{}',

                    imported_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        )
                );

            CREATE INDEX IF NOT EXISTS
                idx_survey_result_imports_batch
            ON survey_result_imports (
                survey_batch_uid,
                imported_at,
                id
            );
            """
        )

    return {
        "ready": True,
        "table": (
            "survey_result_imports"
        ),
    }


def _clean_text(value):
    return str(
        value or ""
    ).strip()


def _optional_text(value):
    value = _clean_text(
        value
    )
    return value or None



def _incoming_revision(
    item,
):
    try:
        value = int(
            item.get(
                "revision_no"
            )
            or 1
        )
    except (
        TypeError,
        ValueError,
    ):
        value = 1

    return max(
        1,
        value,
    )


def _now_text():
    return (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )


def _source_timestamp(
    value,
):
    return (
        _clean_text(
            value
        )
        or _now_text()
    )


def _file_sha256(
    path,
):
    digest = sha256()

    with open(
        path,
        "rb",
    ) as source:
        while True:
            chunk = source.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def _safe_package_media_member(
    media,
):
    media_uid = _clean_text(
        media.get(
            "media_uid"
        )
    )

    package_path = _clean_text(
        media.get(
            "package_path"
        )
    )

    if (
        not media_uid
        or not package_path
    ):
        raise ValueError(
            "成果包影像缺少 media_uid 或 package_path。"
        )

    pure = PurePosixPath(
        package_path
    )

    if (
        pure.is_absolute()
        or ".." in pure.parts
        or len(
            pure.parts
        ) != 2
        or pure.parts[0]
        != "media"
    ):
        raise ValueError(
            "成果包影像路径不安全："
            f"{package_path}"
        )

    filename = pure.name

    if not filename.startswith(
        media_uid
    ):
        raise ValueError(
            "成果包影像文件名与 media_uid 不一致。"
        )

    suffix = Path(
        filename
    ).suffix.lower()

    if not suffix:
        raise ValueError(
            "成果包影像文件缺少扩展名。"
        )

    return (
        package_path,
        suffix,
    )


def _stage_new_media(
    package_path,
    media_items,
    new_media_uids,
    staging_root,
):
    """
    从已经通过 reader 完整性检查的 ZIP 中，
    再次流式提取需要新增的影像。

    文件先进入 local_data 下的 staging，
    不直接写最终业务路径。
    """

    staged = {}

    if not new_media_uids:
        return staged

    media_root = (
        staging_root
        / "media"
    )

    media_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    with zipfile.ZipFile(
        package_path,
        "r",
    ) as archive:
        for media in media_items:
            media_uid = _clean_text(
                media.get(
                    "media_uid"
                )
            )

            if (
                media_uid
                not in new_media_uids
            ):
                continue

            (
                member_path,
                suffix,
            ) = (
                _safe_package_media_member(
                    media
                )
            )

            staged_path = (
                media_root
                / (
                    media_uid
                    + suffix
                    + ".staged"
                )
            )

            digest = sha256()
            actual_size = 0

            with archive.open(
                member_path,
                "r",
            ) as source:
                with open(
                    staged_path,
                    "wb",
                ) as target:
                    while True:
                        chunk = source.read(
                            1024 * 1024
                        )

                        if not chunk:
                            break

                        target.write(
                            chunk
                        )
                        digest.update(
                            chunk
                        )
                        actual_size += len(
                            chunk
                        )

            expected_hash = (
                _clean_text(
                    media.get(
                        "file_sha256"
                    )
                ).lower()
            )

            expected_size = int(
                media.get(
                    "file_size"
                )
                or 0
            )

            if (
                digest.hexdigest()
                != expected_hash
                or actual_size
                != expected_size
            ):
                raise ValueError(
                    "成果包影像在导入暂存阶段校验失败："
                    f"{media_uid}"
                )

            staged[
                media_uid
            ] = {
                "path": (
                    staged_path
                ),
                "suffix": suffix,
            }

    if (
        set(staged)
        != set(new_media_uids)
    ):
        missing = sorted(
            set(new_media_uids)
            - set(staged)
        )

        raise ValueError(
            "成果包缺少需要导入的影像文件："
            + ", ".join(
                missing
            )
        )

    return staged


def _lookup_import_by_package(
    connection,
    package_uid,
):
    return connection.execute(
        """
        SELECT
            id,
            package_uid,
            result_uid,
            package_sha256,
            managed_package_relative_path,
            summary_json
        FROM survey_result_imports
        WHERE package_uid = ?
        """,
        (
            package_uid,
        ),
    ).fetchone()


def _lookup_import_by_result(
    connection,
    result_uid,
):
    return connection.execute(
        """
        SELECT
            id,
            package_uid,
            result_uid,
            package_sha256
        FROM survey_result_imports
        WHERE result_uid = ?
        """,
        (
            result_uid,
        ),
    ).fetchone()


def _already_imported_result(
    package_path,
    row,
):
    try:
        summary = json.loads(
            row[
                "summary_json"
            ]
            or "{}"
        )
    except json.JSONDecodeError:
        summary = {}

    relative = (
        _optional_text(
            row[
                "managed_package_relative_path"
            ]
        )
    )

    managed_path = (
        (
            database.DATA_DIR
            / Path(
                *PurePosixPath(
                    relative
                ).parts
            )
        )
        if relative
        else None
    )

    return SurveyResultImportResult(
        package_path=Path(
            package_path
        ),
        package_uid=(
            row[
                "package_uid"
            ]
        ),
        result_uid=(
            row[
                "result_uid"
            ]
        ),
        backup_path=None,
        managed_package_path=(
            managed_path
        ),
        imported_assets=0,
        existing_assets=int(
            summary.get(
                "assets_total",
                0,
            )
        ),
        updated_assets=0,
        stale_assets=0,
        imported_records=0,
        existing_records=int(
            summary.get(
                "records_total",
                0,
            )
        ),
        updated_records=0,
        stale_records=0,
        imported_inspections=0,
        existing_inspections=int(
            summary.get(
                "inspections_total",
                0,
            )
        ),
        updated_inspections=0,
        imported_media=0,
        existing_media=int(
            summary.get(
                "media_total",
                0,
            )
        ),
        already_imported=True,
    )


def _lookup_project_id(
    connection,
    project_uid,
):
    row = connection.execute(
        """
        SELECT id
        FROM projects
        WHERE project_uid = ?
        """,
        (
            project_uid,
        ),
    ).fetchone()

    if row is None:
        raise ValueError(
            "目标数据库不存在成果包对应项目。"
        )

    return int(
        row["id"]
    )


def _lookup_batch_id(
    connection,
    survey_batch_uid,
    project_id,
):
    row = connection.execute(
        """
        SELECT
            id,
            project_id
        FROM survey_batches
        WHERE survey_batch_uid = ?
        """,
        (
            survey_batch_uid,
        ),
    ).fetchone()

    if row is None:
        raise ValueError(
            "目标数据库不存在成果包对应调查批次。"
        )

    if int(
        row[
            "project_id"
        ]
    ) != int(
        project_id
    ):
        raise ValueError(
            "目标调查批次不属于成果包对应项目。"
        )

    return int(
        row["id"]
    )


def _lookup_org_id(
    connection,
    uid,
):
    row = connection.execute(
        """
        SELECT id
        FROM organization_units
        WHERE organization_unit_uid = ?
        """,
        (
            uid,
        ),
    ).fetchone()

    if row is None:
        raise ValueError(
            "目标数据库缺少成果记录引用的管理单位："
            f"{uid}"
        )

    return int(
        row["id"]
    )


def _lookup_canal_id(
    connection,
    uid,
):
    row = connection.execute(
        """
        SELECT id
        FROM canal_units
        WHERE canal_unit_uid = ?
        """,
        (
            uid,
        ),
    ).fetchone()

    if row is None:
        raise ValueError(
            "目标数据库缺少成果记录引用的渠系："
            f"{uid}"
        )

    return int(
        row["id"]
    )


def _lookup_form_version_id(
    connection,
    form_code,
    version_code,
):
    row = connection.execute(
        """
        SELECT fv.id
        FROM form_definitions AS fd
        JOIN form_versions AS fv
          ON fv.form_definition_id = fd.id
        WHERE fd.form_code = ?
          AND fv.version_code = ?
        """,
        (
            form_code,
            version_code,
        ),
    ).fetchone()

    if row is None:
        raise ValueError(
            "目标数据库缺少成果记录使用的表单版本："
            f"{form_code} / {version_code}"
        )

    return int(
        row["id"]
    )


def _lookup_asset_id(
    connection,
    engineering_asset_uid,
):
    row = connection.execute(
        """
        SELECT id
        FROM engineering_assets
        WHERE engineering_asset_uid = ?
        """,
        (
            engineering_asset_uid,
        ),
    ).fetchone()

    return (
        int(
            row["id"]
        )
        if row is not None
        else None
    )


def _lookup_record_id(
    connection,
    survey_record_uid,
):
    row = connection.execute(
        """
        SELECT id
        FROM survey_records
        WHERE survey_record_uid = ?
        """,
        (
            survey_record_uid,
        ),
    ).fetchone()

    return (
        int(
            row["id"]
        )
        if row is not None
        else None
    )


def _lookup_batch_id_optional(
    connection,
    survey_batch_uid,
):
    if not survey_batch_uid:
        return None

    row = connection.execute(
        """
        SELECT id
        FROM survey_batches
        WHERE survey_batch_uid = ?
        """,
        (
            survey_batch_uid,
        ),
    ).fetchone()

    if row is None:
        raise ValueError(
            "工程对象引用的首次调查批次"
            "在目标数据库中不存在："
            f"{survey_batch_uid}"
        )

    return int(
        row["id"]
    )


def _normalize_v120_legacy_chainage_asset(item):
    normalized = dict(item or {})
    start_text = str(normalized.get("start_stake_text") or "").strip()
    single_text = str(normalized.get("single_stake_text") or "").strip()
    if not start_text and (single_text or normalized.get('single_stake_value') is not None):
        normalized["start_stake_text"] = normalized.get("single_stake_text")
        normalized["start_stake_value"] = normalized.get("single_stake_value")
    return normalized


def _normalize_v120_legacy_chainage_record(item):
    normalized = dict(item or {})
    record_data = dict(normalized.get("record_data") or {})
    start_text = str(record_data.get("start_stake") or "").strip()
    legacy_text = str(record_data.get("stake") or "").strip()
    if not start_text and legacy_text:
        record_data["start_stake"] = legacy_text
    normalized["record_data"] = record_data
    return normalized

def _insert_asset(
    connection,
    item,
    *,
    project_id,
):
    item = _normalize_v120_legacy_chainage_asset(item)

    organization_id = (
        _lookup_org_id(
            connection,
            item[
                "organization_unit_uid"
            ],
        )
    )

    canal_id = (
        _lookup_canal_id(
            connection,
            item[
                "canal_unit_uid"
            ],
        )
    )

    first_batch_id = (
        _lookup_batch_id_optional(
            connection,
            _optional_text(
                item.get(
                    "first_survey_batch_uid"
                )
            ),
        )
    )

    cursor = connection.execute(
        """
        INSERT INTO engineering_assets (
            engineering_asset_uid,
            project_id,
            asset_name,
            asset_type,
            organization_unit_id,
            canal_unit_id,
            business_code,
            code_scheme_version,
            single_stake_text,
            single_stake_value,
            start_stake_text,
            start_stake_value,
            end_stake_text,
            end_stake_value,
            first_survey_batch_id,
            status,
            notes,
            created_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            item[
                "engineering_asset_uid"
            ],
            project_id,
            item[
                "asset_name"
            ],
            item[
                "asset_type"
            ],
            organization_id,
            canal_id,
            item[
                "business_code"
            ],
            (
                item.get(
                    "code_scheme_version"
                )
                or "V1"
            ),
            item.get(
                "single_stake_text"
            ),
            item.get(
                "single_stake_value"
            ),
            item.get(
                "start_stake_text"
            ),
            item.get(
                "start_stake_value"
            ),
            item.get(
                "end_stake_text"
            ),
            item.get(
                "end_stake_value"
            ),
            first_batch_id,
            (
                item.get(
                    "status"
                )
                or "active"
            ),
            item.get(
                "notes"
            ),
            _source_timestamp(
                item.get(
                    "created_at"
                )
            ),
            _source_timestamp(
                item.get(
                    "updated_at"
                )
            ),
        ),
    )

    asset_id = int(
        cursor.lastrowid
    )

    incoming_revision = (
        _incoming_revision(
            item
        )
    )

    connection.execute(
        """
        UPDATE engineering_assets
        SET
            revision_no = ?,
            source_revision_no = ?,
            code_status = 'provisional'
        WHERE id = ?
        """,
        (
            incoming_revision,
            incoming_revision,
            asset_id,
        ),
    )

    return asset_id


def _insert_record(
    connection,
    item,
    *,
    project_id,
    batch_id,
    asset_id,
):
    item = _normalize_v120_legacy_chainage_record(item)

    form = item.get(
        "form"
    ) or {}

    form_version_id = (
        _lookup_form_version_id(
            connection,
            form.get(
                "form_code"
            ),
            form.get(
                "version_code"
            ),
        )
    )

    organization_id = (
        _lookup_org_id(
            connection,
            item[
                "organization_unit_uid"
            ],
        )
    )

    canal_id = (
        _lookup_canal_id(
            connection,
            item[
                "canal_unit_uid"
            ],
        )
    )

    asset_code_row = connection.execute(
        """
        SELECT business_code
        FROM engineering_assets
        WHERE id = ?
        """,
        (asset_id,),
    ).fetchone()

    target_business_code = (
        asset_code_row["business_code"]
        if asset_code_row is not None
        else item.get("business_code")
    )

    record_data_json = json.dumps(
        item.get(
            "record_data"
        )
        or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    cursor = connection.execute(
        """
        INSERT INTO survey_records (
            survey_record_uid,
            source_task_uid,
            source_management_scope_uid,
            project_id,
            survey_batch_id,
            form_version_id,
            record_type,
            organization_unit_id,
            canal_unit_id,
            engineering_asset_id,
            business_code,
            survey_date,
            overall_grade,
            survey_comment,
            surveyor_signatures,
            water_office_manager_signature,
            engineering_section_chief_signature,
            department_head_signature,
            record_status,
            record_data_json,
            void_reason,
            created_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            item[
                "survey_record_uid"
            ],
            _optional_text(
                item.get(
                    "source_task_uid"
                )
            ),
            _optional_text(
                item.get(
                    "source_management_scope_uid"
                )
            ),
            project_id,
            batch_id,
            form_version_id,
            (
                item.get(
                    "record_type"
                )
                or "engineering"
            ),
            organization_id,
            canal_id,
            asset_id,
            target_business_code,
            item.get(
                "survey_date"
            ),
            item.get(
                "overall_grade"
            ),
            item.get(
                "survey_comment"
            ),
            item.get(
                "surveyor_signatures"
            ),
            item.get(
                "water_office_manager_signature"
            ),
            item.get(
                "engineering_section_chief_signature"
            ),
            item.get(
                "department_head_signature"
            ),
            item.get(
                "record_status"
            )
            or "completed",
            record_data_json,
            item.get(
                "void_reason"
            ),
            _source_timestamp(
                item.get(
                    "created_at"
                )
            ),
            _source_timestamp(
                item.get(
                    "updated_at"
                )
            ),
        ),
    )

    record_id = int(
        cursor.lastrowid
    )

    incoming_revision = (
        _incoming_revision(
            item
        )
    )

    connection.execute(
        """
        UPDATE survey_records
        SET
            revision_no = ?,
            source_revision_no = ?
        WHERE id = ?
        """,
        (
            incoming_revision,
            incoming_revision,
            record_id,
        ),
    )

    return record_id



def _update_asset_from_package(
    connection,
    item,
    *,
    asset_id,
):
    item = _normalize_v120_legacy_chainage_asset(item)

    incoming_revision = _incoming_revision(item)

    current = connection.execute(
        """
        SELECT
            business_code,
            code_scheme_version,
            single_stake_value,
            start_stake_value,
            end_stake_value,
            code_status
        FROM engineering_assets
        WHERE id = ?
        """,
        (asset_id,),
    ).fetchone()

    if current is None:
        raise ValueError("待更新工程对象不存在。")

    position_changed = (
        current["single_stake_value"] != item.get("single_stake_value")
        or current["start_stake_value"] != item.get("start_stake_value")
        or current["end_stake_value"] != item.get("end_stake_value")
    )
    next_code_status = (
        "provisional"
        if position_changed
        else (current["code_status"] or "provisional")
    )

    connection.execute(
        """
        UPDATE engineering_assets
        SET
            asset_name = ?,
            single_stake_text = ?,
            single_stake_value = ?,
            start_stake_text = ?,
            start_stake_value = ?,
            end_stake_text = ?,
            end_stake_value = ?,
            status = ?,
            notes = ?,
            revision_no = ?,
            source_revision_no = ?,
            code_status = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            item.get("asset_name") or "",
            item.get("single_stake_text"),
            item.get("single_stake_value"),
            item.get("start_stake_text"),
            item.get("start_stake_value"),
            item.get("end_stake_text"),
            item.get("end_stake_value"),
            item.get("status") or "active",
            item.get("notes"),
            incoming_revision,
            incoming_revision,
            next_code_status,
            _source_timestamp(item.get("updated_at")),
            asset_id,
        ),
    )


def _update_record_from_package(
    connection,
    item,
    *,
    record_id,
):
    item = _normalize_v120_legacy_chainage_record(item)

    incoming_revision = _incoming_revision(item)

    record_data_json = json.dumps(
        item.get("record_data") or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    connection.execute(
        """
        UPDATE survey_records
        SET
            survey_date = ?,
            overall_grade = ?,
            survey_comment = ?,
            surveyor_signatures = ?,
            water_office_manager_signature = ?,
            engineering_section_chief_signature = ?,
            department_head_signature = ?,
            record_status = ?,
            record_data_json = ?,
            void_reason = ?,
            revision_no = ?,
            source_revision_no = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            item.get("survey_date"),
            item.get("overall_grade"),
            item.get("survey_comment"),
            item.get("surveyor_signatures"),
            item.get("water_office_manager_signature"),
            item.get("engineering_section_chief_signature"),
            item.get("department_head_signature"),
            item.get("record_status") or "completed",
            record_data_json,
            item.get("void_reason"),
            incoming_revision,
            incoming_revision,
            _source_timestamp(item.get("updated_at")),
            record_id,
        ),
    )


def _inspection_exists(
    connection,
    survey_record_id,
    item_code,
):
    row = connection.execute(
        """
        SELECT id
        FROM inspection_results
        WHERE survey_record_id = ?
          AND item_code = ?
        """,
        (
            survey_record_id,
            item_code,
        ),
    ).fetchone()

    return row is not None


def _insert_inspection(
    connection,
    item,
    *,
    survey_record_id,
):
    connection.execute(
        """
        INSERT INTO inspection_results (
            survey_record_id,
            item_code,
            category,
            item_name,
            grade,
            description,
            remark,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            survey_record_id,
            item[
                "item_code"
            ],
            item.get(
                "category"
            )
            or "",
            item.get(
                "item_name"
            )
            or "",
            item.get(
                "grade"
            ),
            item.get(
                "description"
            ),
            item.get(
                "remark"
            ),
            _source_timestamp(
                item.get(
                    "updated_at"
                )
            ),
        ),
    )


def _load_existing_media_row(
    connection,
    media_uid,
):
    return connection.execute(
        """
        SELECT
            id,
            media_uid,
            stored_relative_path,
            file_sha256,
            file_size
        FROM survey_media
        WHERE media_uid = ?
        """,
        (
            media_uid,
        ),
    ).fetchone()


def _verify_existing_media_file(
    row,
):
    path = (
        database.DATA_DIR
        / Path(
            *PurePosixPath(
                row[
                    "stored_relative_path"
                ]
            ).parts
        )
    )

    if (
        not path.exists()
        or not path.is_file()
    ):
        raise FileNotFoundError(
            "目标数据库记录的既有影像文件不存在："
            f"{path}"
        )

    if int(
        path.stat().st_size
    ) != int(
        row[
            "file_size"
        ]
    ):
        raise ValueError(
            "目标数据库既有影像文件大小与元数据不一致："
            f"{row['media_uid']}"
        )

    if (
        _file_sha256(
            path
        )
        != _clean_text(
            row[
                "file_sha256"
            ]
        ).lower()
    ):
        raise ValueError(
            "目标数据库既有影像文件哈希与元数据不一致："
            f"{row['media_uid']}"
        )


def _build_media_target(
    *,
    project_id,
    batch_id,
    survey_record_id,
    media_uid,
    suffix,
):
    relative = Path(
        "media",
        f"project_{project_id}",
        f"batch_{batch_id}",
        f"record_{survey_record_id}",
        (
            media_uid
            + suffix.lower()
        ),
    )

    return (
        relative,
        database.DATA_DIR
        / relative
    )


def _install_staged_media_file(
    staged_path,
    final_path,
):
    final_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if final_path.exists():
        raise FileExistsError(
            "影像目标文件已经存在，拒绝覆盖："
            f"{final_path}"
        )

    os.replace(
        staged_path,
        final_path,
    )


def _insert_media(
    connection,
    item,
    *,
    survey_record_id,
    stored_relative_path,
):
    connection.execute(
        """
        INSERT INTO survey_media (
            media_uid,
            survey_record_id,
            media_kind,
            media_role,
            item_code,
            part_name,
            sequence_no,
            original_filename,
            stored_relative_path,
            file_sha256,
            file_size,
            captured_at,
            notes,
            created_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        """,
        (
            item[
                "media_uid"
            ],
            survey_record_id,
            item.get(
                "media_kind"
            )
            or "photo",
            item.get(
                "media_role"
            )
            or "other",
            item.get(
                "item_code"
            ),
            item.get(
                "part_name"
            ),
            int(
                item.get(
                    "sequence_no"
                )
                or 1
            ),
            item[
                "original_filename"
            ],
            stored_relative_path,
            item[
                "file_sha256"
            ],
            int(
                item[
                    "file_size"
                ]
            ),
            item.get(
                "captured_at"
            ),
            item.get(
                "notes"
            ),
            _source_timestamp(
                item.get(
                    "created_at"
                )
            ),
            _source_timestamp(
                item.get(
                    "updated_at"
                )
            ),
        ),
    )


def _table_exists(
    connection,
    table_name,
):
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (
            table_name,
        ),
    ).fetchone()

    return row is not None


def _suspend_current_task_workspace(
    connection,
):
    """
    Stage 12.3 的触发器用于约束“本机新增录入”。

    成果导入必须保留来自下级的 source_task_uid，
    不能被当前父任务自动覆盖。因此在同一 SQLite
    事务内暂时取消当前 workspace，再在提交前恢复。

    未提交的 is_current 变化对其他连接不可见；
    任意异常回滚后也会恢复原状态。
    """

    if not _table_exists(
        connection,
        "survey_task_workspaces",
    ):
        return ()

    rows = connection.execute(
        """
        SELECT id
        FROM survey_task_workspaces
        WHERE is_current = 1
        ORDER BY id
        """
    ).fetchall()

    ids = tuple(
        int(
            row["id"]
        )
        for row in rows
    )

    if ids:
        connection.execute(
            """
            UPDATE survey_task_workspaces
            SET is_current = 0
            WHERE is_current = 1
            """
        )

    return ids


def _restore_current_task_workspace(
    connection,
    workspace_ids,
):
    if not workspace_ids:
        return

    placeholders = ",".join(
        "?"
        for _ in workspace_ids
    )

    connection.execute(
        f"""
        UPDATE survey_task_workspaces
        SET is_current = 1
        WHERE id IN (
            {placeholders}
        )
        """,
        workspace_ids,
    )


def _prepare_managed_package(
    package_path,
    package_uid,
    staging_root,
):
    package_staging = (
        staging_root
        / (
            package_uid
            + ".ydresult.staged"
        )
    )

    shutil.copy2(
        package_path,
        package_staging,
    )

    final_relative = Path(
        "result_packages",
        package_uid,
        (
            package_uid
            + ".ydresult"
        ),
    )

    final_absolute = (
        database.DATA_DIR
        / final_relative
    )

    return (
        package_staging,
        final_relative,
        final_absolute,
    )


def _result_source_task_uids(
    result_document,
):
    values = result_document.get(
        "source_task_uids"
    )

    if not isinstance(
        values,
        (list, tuple),
    ):
        values = (
            result_document.get(
                "source_task_uid"
            ),
        )

    result = []

    for value in values:
        uid = _clean_text(
            value
        )

        if (
            uid
            and uid not in result
        ):
            result.append(
                uid
            )

    return tuple(
        result
    )


def import_survey_result_package(
    package_path,
    *,
    accept_updates=False,
):
    """
    事务化导入 .ydresult。

    流程：
    1. 校验包并做 Stage 12.5 目标库预检；
    2. 检查重复导入；
    3. 创建数据库 pre_result_import 备份；
    4. 影像和原成果包先进入 staging；
    5. BEGIN IMMEDIATE；
    6. 按稳定 UID 映射/插入 Asset -> Record ->
       Inspection -> Media；
    7. 在事务内安装托管文件；
    8. 写入 survey_result_imports；
    9. 恢复当前 task workspace；
    10. commit；
    11. 任意异常：SQLite rollback + 删除本次已安装文件。

    不做：
    - 自动改业务编号；
    - 自动合并 UID 冲突；
    - 自动创建缺失项目/批次/主数据；
    - 覆盖既有业务数据。
    """

    package_path = Path(
        package_path
    ).expanduser().resolve()

    ensure_survey_result_import_schema()

    contents = (
        load_survey_result_package(
            package_path
        )
    )

    manifest = (
        contents.manifest
        or {}
    )
    result_document = (
        contents.result
        or {}
    )

    package_uid = _clean_text(
        manifest.get(
            "package_uid"
        )
    )
    result_uid = _clean_text(
        result_document.get(
            "result_uid"
        )
    )

    project_document = (
        result_document.get(
            "project"
        )
        or {}
    )
    batch_document = (
        result_document.get(
            "survey_batch"
        )
        or {}
    )

    project_uid = _clean_text(
        project_document.get(
            "project_uid"
        )
    )
    survey_batch_uid = _clean_text(
        batch_document.get(
            "survey_batch_uid"
        )
    )

    package_hash = (
        _file_sha256(
            package_path
        )
    )

    with database.get_connection() as connection:
        prior = (
            _lookup_import_by_package(
                connection,
                package_uid,
            )
        )

        if prior is not None:
            if (
                _clean_text(
                    prior[
                        "package_sha256"
                    ]
                ).lower()
                != package_hash
            ):
                raise ValueError(
                    "相同 package_uid 已接收过，"
                    "但当前文件哈希不同，拒绝继续。"
                )

            return (
                _already_imported_result(
                    package_path,
                    prior,
                )
            )

        prior_result = (
            _lookup_import_by_result(
                connection,
                result_uid,
            )
        )

        if prior_result is not None:
            raise ValueError(
                "相同 result_uid 已通过另一成果包接收，"
                "拒绝重复包装后再次导入。"
            )

    preflight = (
        preflight_survey_result_import(
            package_path
        )
    )

    if not preflight.can_import:
        raise ValueError(
            "成果包目标数据库预检未通过，"
            "禁止正式导入。\n\n"
            + preflight.format_text()
        )

    if (
        preflight.has_updates
        and not accept_updates
    ):
        raise ValueError(
            "成果包包含下级修订数据。"
            "为避免静默覆盖，必须由用户明确确认"
            "后才能执行更新导入。\n\n"
            + preflight.format_text()
        )

    backup_path = (
        create_database_backup(
            reason=(
                "pre_result_import"
            ),
            skip_if_unchanged=False,
        )
    )

    staging_root = (
        database.DATA_DIR
        / "result_import_staging"
        / package_uid
    )

    if staging_root.exists():
        shutil.rmtree(
            staging_root
        )

    staging_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    installed_files = []
    managed_package_path = None

    try:
        with database.get_connection() as connection:
            existing_media_uids = set()

            for media in contents.survey_media:
                media_uid = _clean_text(
                    media.get(
                        "media_uid"
                    )
                )

                current = (
                    _load_existing_media_row(
                        connection,
                        media_uid,
                    )
                )

                if current is not None:
                    _verify_existing_media_file(
                        current
                    )
                    existing_media_uids.add(
                        media_uid
                    )

            new_media_uids = {
                _clean_text(
                    media.get(
                        "media_uid"
                    )
                )
                for media in contents.survey_media
                if _clean_text(
                    media.get(
                        "media_uid"
                    )
                )
                not in existing_media_uids
            }

        staged_media = (
            _stage_new_media(
                package_path,
                contents.survey_media,
                new_media_uids,
                staging_root,
            )
        )

        (
            staged_package,
            managed_package_relative,
            managed_package_absolute,
        ) = (
            _prepare_managed_package(
                package_path,
                package_uid,
                staging_root,
            )
        )

        if (
            managed_package_absolute.exists()
        ):
            raise FileExistsError(
                "成果包托管目标已经存在，"
                "但没有对应导入日志，拒绝覆盖："
                f"{managed_package_absolute}"
            )

        managed_package_absolute.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        imported_assets = 0
        existing_assets = 0
        updated_assets = 0
        stale_assets = 0
        imported_records = 0
        existing_records = 0
        updated_records = 0
        stale_records = 0
        imported_inspections = 0
        existing_inspections = 0
        updated_inspections = 0
        imported_media = 0
        existing_media = 0

        asset_update_uids = set(
            preflight.asset_update_uids
        )
        asset_stale_uids = set(
            preflight.asset_stale_uids
        )
        record_update_uids = set(
            preflight.record_update_uids
        )
        record_stale_uids = set(
            preflight.record_stale_uids
        )

        with database.get_connection() as connection:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            current_workspace_ids = (
                _suspend_current_task_workspace(
                    connection
                )
            )

            try:
                project_id = (
                    _lookup_project_id(
                        connection,
                        project_uid,
                    )
                )

                batch_id = (
                    _lookup_batch_id(
                        connection,
                        survey_batch_uid,
                        project_id,
                    )
                )

                asset_id_by_uid = {}

                for item in (
                    contents.engineering_assets
                ):
                    uid = _clean_text(
                        item[
                            "engineering_asset_uid"
                        ]
                    )

                    asset_id = (
                        _lookup_asset_id(
                            connection,
                            uid,
                        )
                    )

                    if asset_id is None:
                        asset_id = (
                            _insert_asset(
                                connection,
                                item,
                                project_id=(
                                    project_id
                                ),
                            )
                        )
                        imported_assets += 1

                    elif uid in asset_stale_uids:
                        stale_assets += 1

                    elif uid in asset_update_uids:
                        _update_asset_from_package(
                            connection,
                            item,
                            asset_id=asset_id,
                        )
                        updated_assets += 1

                    else:
                        existing_assets += 1

                    asset_id_by_uid[
                        uid
                    ] = asset_id

                record_id_by_uid = {}

                for item in (
                    contents.survey_records
                ):
                    uid = _clean_text(
                        item[
                            "survey_record_uid"
                        ]
                    )

                    record_id = (
                        _lookup_record_id(
                            connection,
                            uid,
                        )
                    )

                    if record_id is None:
                        asset_uid = _clean_text(
                            item[
                                "engineering_asset_uid"
                            ]
                        )

                        asset_id = (
                            asset_id_by_uid.get(
                                asset_uid
                            )
                            or _lookup_asset_id(
                                connection,
                                asset_uid,
                            )
                        )

                        if asset_id is None:
                            raise ValueError(
                                "调查记录引用的工程对象"
                                "无法在目标数据库定位："
                                f"{asset_uid}"
                            )

                        record_id = (
                            _insert_record(
                                connection,
                                item,
                                project_id=(
                                    project_id
                                ),
                                batch_id=(
                                    batch_id
                                ),
                                asset_id=(
                                    asset_id
                                ),
                            )
                        )
                        imported_records += 1

                    elif uid in record_stale_uids:
                        stale_records += 1

                    elif uid in record_update_uids:
                        _update_record_from_package(
                            connection,
                            item,
                            record_id=record_id,
                        )
                        updated_records += 1

                    else:
                        existing_records += 1

                    record_id_by_uid[
                        uid
                    ] = record_id

                # 对已确认更新的调查记录，分项评价属于该 revision
                # 的权威子内容：先删除旧集合，再按成果包重建。
                for record_uid in record_update_uids:
                    record_id = (
                        record_id_by_uid.get(
                            record_uid
                        )
                        or _lookup_record_id(
                            connection,
                            record_uid,
                        )
                    )

                    if record_id is None:
                        raise ValueError(
                            "待更新记录无法在目标数据库定位："
                            f"{record_uid}"
                        )

                    connection.execute(
                        """
                        DELETE FROM inspection_results
                        WHERE survey_record_id = ?
                        """,
                        (
                            record_id,
                        ),
                    )

                for item in (
                    contents.inspection_results
                ):
                    record_uid = _clean_text(
                        item[
                            "survey_record_uid"
                        ]
                    )

                    record_id = (
                        record_id_by_uid.get(
                            record_uid
                        )
                        or _lookup_record_id(
                            connection,
                            record_uid,
                        )
                    )

                    if record_id is None:
                        raise ValueError(
                            "分项评价引用的调查记录"
                            "无法在目标数据库定位："
                            f"{record_uid}"
                        )

                    if record_uid in record_stale_uids:
                        existing_inspections += 1
                        continue

                    if record_uid in record_update_uids:
                        _insert_inspection(
                            connection,
                            item,
                            survey_record_id=(
                                record_id
                            ),
                        )
                        updated_inspections += 1
                        continue

                    if _inspection_exists(
                        connection,
                        record_id,
                        item[
                            "item_code"
                        ],
                    ):
                        existing_inspections += 1
                    else:
                        _insert_inspection(
                            connection,
                            item,
                            survey_record_id=(
                                record_id
                            ),
                        )
                        imported_inspections += 1

                for item in (
                    contents.survey_media
                ):
                    media_uid = _clean_text(
                        item[
                            "media_uid"
                        ]
                    )

                    existing = (
                        _load_existing_media_row(
                            connection,
                            media_uid,
                        )
                    )

                    if existing is not None:
                        _verify_existing_media_file(
                            existing
                        )
                        existing_media += 1
                        continue

                    record_uid = _clean_text(
                        item[
                            "survey_record_uid"
                        ]
                    )

                    record_id = (
                        record_id_by_uid.get(
                            record_uid
                        )
                        or _lookup_record_id(
                            connection,
                            record_uid,
                        )
                    )

                    if record_id is None:
                        raise ValueError(
                            "影像引用的调查记录"
                            "无法在目标数据库定位："
                            f"{record_uid}"
                        )

                    staged_info = (
                        staged_media.get(
                            media_uid
                        )
                    )

                    if staged_info is None:
                        raise ValueError(
                            "没有找到已经暂存的成果影像："
                            f"{media_uid}"
                        )

                    (
                        relative_path,
                        final_path,
                    ) = _build_media_target(
                        project_id=(
                            project_id
                        ),
                        batch_id=(
                            batch_id
                        ),
                        survey_record_id=(
                            record_id
                        ),
                        media_uid=(
                            media_uid
                        ),
                        suffix=(
                            staged_info[
                                "suffix"
                            ]
                        ),
                    )

                    _install_staged_media_file(
                        staged_info[
                            "path"
                        ],
                        final_path,
                    )

                    installed_files.append(
                        final_path
                    )

                    _insert_media(
                        connection,
                        item,
                        survey_record_id=(
                            record_id
                        ),
                        stored_relative_path=(
                            relative_path.as_posix()
                        ),
                    )

                    imported_media += 1

                os.replace(
                    staged_package,
                    managed_package_absolute,
                )

                installed_files.append(
                    managed_package_absolute
                )

                summary = {
                    "result_name": (
                        _clean_text(
                            result_document.get(
                                "result_name"
                            )
                        )
                        or None
                    ),
                    "source_task_uids": list(
                        _result_source_task_uids(
                            result_document
                        )
                    ),
                    "assets_total": len(
                        contents.engineering_assets
                    ),
                    "records_total": len(
                        contents.survey_records
                    ),
                    "inspections_total": len(
                        contents.inspection_results
                    ),
                    "media_total": len(
                        contents.survey_media
                    ),
                    "imported_assets": (
                        imported_assets
                    ),
                    "existing_assets": (
                        existing_assets
                    ),
                    "updated_assets": (
                        updated_assets
                    ),
                    "stale_assets": (
                        stale_assets
                    ),
                    "imported_records": (
                        imported_records
                    ),
                    "existing_records": (
                        existing_records
                    ),
                    "updated_records": (
                        updated_records
                    ),
                    "stale_records": (
                        stale_records
                    ),
                    "imported_inspections": (
                        imported_inspections
                    ),
                    "existing_inspections": (
                        existing_inspections
                    ),
                    "updated_inspections": (
                        updated_inspections
                    ),
                    "imported_media": (
                        imported_media
                    ),
                    "existing_media": (
                        existing_media
                    ),
                }

                connection.execute(
                    """
                    INSERT INTO survey_result_imports (
                        package_uid,
                        result_uid,
                        package_sha256,
                        project_uid,
                        survey_batch_uid,
                        source_package_name,
                        managed_package_relative_path,
                        summary_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        package_uid,
                        result_uid,
                        package_hash,
                        project_uid,
                        survey_batch_uid,
                        package_path.name,
                        (
                            managed_package_relative
                            .as_posix()
                        ),
                        json.dumps(
                            summary,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )

                _restore_current_task_workspace(
                    connection,
                    current_workspace_ids,
                )

                managed_package_path = (
                    managed_package_absolute
                )

            except Exception:
                _restore_current_task_workspace(
                    connection,
                    current_workspace_ids,
                )
                raise

        return SurveyResultImportResult(
            package_path=(
                package_path
            ),
            package_uid=(
                package_uid
            ),
            result_uid=(
                result_uid
            ),
            backup_path=(
                backup_path
            ),
            managed_package_path=(
                managed_package_path
            ),
            imported_assets=(
                imported_assets
            ),
            existing_assets=(
                existing_assets
            ),
            updated_assets=(
                updated_assets
            ),
            stale_assets=(
                stale_assets
            ),
            imported_records=(
                imported_records
            ),
            existing_records=(
                existing_records
            ),
            updated_records=(
                updated_records
            ),
            stale_records=(
                stale_records
            ),
            imported_inspections=(
                imported_inspections
            ),
            existing_inspections=(
                existing_inspections
            ),
            updated_inspections=(
                updated_inspections
            ),
            imported_media=(
                imported_media
            ),
            existing_media=(
                existing_media
            ),
            already_imported=False,
        )

    except Exception:
        for path in reversed(
            installed_files
        ):
            try:
                Path(
                    path
                ).unlink(
                    missing_ok=True
                )
            except OSError:
                pass

        raise

    finally:
        if staging_root.exists():
            shutil.rmtree(
                staging_root,
                ignore_errors=True,
            )
