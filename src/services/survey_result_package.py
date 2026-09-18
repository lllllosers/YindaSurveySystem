from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath

import database

from services.master_data_integrity import (
    check_master_data_integrity,
)
from services.yd_package import (
    encode_json_bytes,
    new_stable_token,
    write_package_streaming,
)
from version import (
    APP_VERSION,
    APP_VERSION_LABEL,
)


SURVEY_RESULT_PACKAGE_KIND = (
    "survey_result"
)
SURVEY_RESULT_EXTENSION = (
    ".ydresult"
)

RESULT_SCHEMA_VERSION = "2.0"


@dataclass(frozen=True)
class SurveyResultExportRequest:
    project_id: int
    survey_batch_id: int
    survey_record_ids: tuple[int, ...]
    output_path: Path
    result_name: str = ""
    creator: str = ""
    notes: str = ""


@dataclass(frozen=True)
class SurveyResultExportResult:
    output_path: Path
    package_uid: str
    result_uid: str
    survey_record_count: int
    engineering_asset_count: int
    inspection_result_count: int
    media_count: int
    media_bytes: int


def _clean_text(
    value,
):
    return str(
        value or ""
    ).strip()


def _optional_text(
    value,
):
    cleaned = _clean_text(
        value
    )

    return cleaned or None


def _require_uid(
    value,
    entity_name,
):
    uid = _clean_text(
        value
    )

    if not uid:
        raise ValueError(
            f"{entity_name}缺少稳定 UID。"
        )

    return uid


def _normalize_output_path(
    output_path,
):
    path = Path(
        output_path
    )

    if path.suffix == "":
        path = path.with_suffix(
            SURVEY_RESULT_EXTENSION
        )

    elif (
        path.suffix.lower()
        != SURVEY_RESULT_EXTENSION
    ):
        raise ValueError(
            "调查成果包文件扩展名必须为 .ydresult。"
        )

    return path


def _normalize_request(
    request,
):
    try:
        project_id = int(
            request.project_id
        )
        survey_batch_id = int(
            request.survey_batch_id
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "项目或调查批次 ID 无效。"
        ) from error

    record_ids = []

    for raw_id in (
        request.survey_record_ids
        or ()
    ):
        try:
            record_id = int(
                raw_id
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "调查记录 ID 无效。"
            ) from error

        if record_id not in record_ids:
            record_ids.append(
                record_id
            )

    if not record_ids:
        raise ValueError(
            "调查成果包至少需要包含一条调查记录。"
        )

    return {
        "project_id": project_id,
        "survey_batch_id": (
            survey_batch_id
        ),
        "survey_record_ids": tuple(
            record_ids
        ),
        "output_path": (
            _normalize_output_path(
                request.output_path
            )
        ),
        "result_name": (
            _clean_text(
                request.result_name
            )
        ),
        "creator": (
            _optional_text(
                request.creator
            )
        ),
        "notes": (
            _optional_text(
                request.notes
            )
        ),
    }


def _placeholders(
    values,
):
    return ",".join(
        "?"
        for _ in values
    )


def _load_export_context(
    normalized,
):
    record_ids = normalized[
        "survey_record_ids"
    ]

    placeholders = (
        _placeholders(
            record_ids
        )
    )

    with database.get_connection() as connection:
        project = connection.execute(
            """
            SELECT
                id,
                project_uid,
                name,
                short_name,
                status
            FROM projects
            WHERE id = ?
            """,
            (
                normalized[
                    "project_id"
                ],
            ),
        ).fetchone()

        if project is None:
            raise ValueError(
                "没有找到指定项目。"
            )

        batch = connection.execute(
            """
            SELECT
                id,
                survey_batch_uid,
                project_id,
                batch_name,
                batch_code,
                start_date,
                end_date,
                status
            FROM survey_batches
            WHERE id = ?
            """,
            (
                normalized[
                    "survey_batch_id"
                ],
            ),
        ).fetchone()

        if batch is None:
            raise ValueError(
                "没有找到指定调查批次。"
            )

        if (
            int(
                batch["project_id"]
            )
            != int(
                project["id"]
            )
        ):
            raise ValueError(
                "调查批次不属于指定项目。"
            )

        records = [
            dict(row)
            for row in connection.execute(
                f"""
                SELECT
                    sr.id,
                    sr.survey_record_uid,
                    sr.source_task_uid,
                    sr.source_management_scope_uid,
                    sr.project_id,
                    p.project_uid,
                    sr.survey_batch_id,
                    sb.survey_batch_uid,
                    sr.form_version_id,
                    fd.form_code,
                    fd.form_number,
                    fd.form_name,
                    fd.asset_type
                        AS form_asset_type,
                    fv.version_code,
                    fv.version_name,
                    fv.effective_date,
                    sr.record_type,
                    sr.organization_unit_id,
                    ou.organization_unit_uid,
                    sr.canal_unit_id,
                    cu.canal_unit_uid,
                    sr.engineering_asset_id,
                    ea.engineering_asset_uid,
                    sr.business_code,
                    sr.survey_date,
                    sr.overall_grade,
                    sr.survey_comment,
                    sr.record_status,
                    sr.record_data_json,
                    sr.void_reason,
                    sr.created_at,
                    sr.updated_at
                FROM survey_records AS sr
                JOIN projects AS p
                  ON p.id = sr.project_id
                JOIN survey_batches AS sb
                  ON sb.id = sr.survey_batch_id
                JOIN form_versions AS fv
                  ON fv.id = sr.form_version_id
                JOIN form_definitions AS fd
                  ON fd.id = fv.form_definition_id
                LEFT JOIN organization_units AS ou
                  ON ou.id = sr.organization_unit_id
                LEFT JOIN canal_units AS cu
                  ON cu.id = sr.canal_unit_id
                LEFT JOIN engineering_assets AS ea
                  ON ea.id = sr.engineering_asset_id
                WHERE sr.id IN (
                    {placeholders}
                )
                ORDER BY sr.id
                """,
                record_ids,
            ).fetchall()
        ]

        if len(records) != len(
            record_ids
        ):
            found_ids = {
                int(
                    row["id"]
                )
                for row in records
            }

            missing_ids = [
                record_id
                for record_id
                in record_ids
                if record_id
                not in found_ids
            ]

            raise ValueError(
                "没有找到全部调查记录，缺少 ID："
                + ", ".join(
                    str(value)
                    for value
                    in missing_ids
                )
            )

        asset_ids = sorted(
            {
                int(
                    row[
                        "engineering_asset_id"
                    ]
                )
                for row in records
                if row[
                    "engineering_asset_id"
                ]
                is not None
            }
        )

        assets = []

        if asset_ids:
            asset_placeholders = (
                _placeholders(
                    asset_ids
                )
            )

            assets = [
                dict(row)
                for row in connection.execute(
                    f"""
                    SELECT
                        ea.id,
                        ea.engineering_asset_uid,
                        ea.project_id,
                        p.project_uid,
                        ea.asset_name,
                        ea.asset_type,
                        ea.organization_unit_id,
                        ou.organization_unit_uid,
                        ea.canal_unit_id,
                        cu.canal_unit_uid,
                        ea.business_code,
                        ea.code_scheme_version,
                        ea.single_stake_text,
                        ea.single_stake_value,
                        ea.start_stake_text,
                        ea.start_stake_value,
                        ea.end_stake_text,
                        ea.end_stake_value,
                        ea.first_survey_batch_id,
                        fsb.survey_batch_uid
                            AS first_survey_batch_uid,
                        ea.status,
                        ea.notes,
                        ea.created_at,
                        ea.updated_at
                    FROM engineering_assets AS ea
                    JOIN projects AS p
                      ON p.id = ea.project_id
                    JOIN organization_units AS ou
                      ON ou.id = ea.organization_unit_id
                    JOIN canal_units AS cu
                      ON cu.id = ea.canal_unit_id
                    LEFT JOIN survey_batches AS fsb
                      ON fsb.id = ea.first_survey_batch_id
                    WHERE ea.id IN (
                        {asset_placeholders}
                    )
                    ORDER BY ea.id
                    """,
                    asset_ids,
                ).fetchall()
            ]

        inspections = [
            dict(row)
            for row in connection.execute(
                f"""
                SELECT
                    ir.id,
                    ir.survey_record_id,
                    sr.survey_record_uid,
                    ir.item_code,
                    ir.category,
                    ir.item_name,
                    ir.grade,
                    ir.description,
                    ir.remark,
                    ir.updated_at
                FROM inspection_results AS ir
                JOIN survey_records AS sr
                  ON sr.id = ir.survey_record_id
                WHERE ir.survey_record_id IN (
                    {placeholders}
                )
                ORDER BY
                    ir.survey_record_id,
                    ir.id
                """,
                record_ids,
            ).fetchall()
        ]

        media_rows = [
            dict(row)
            for row in connection.execute(
                f"""
                SELECT
                    sm.id,
                    sm.media_uid,
                    sm.survey_record_id,
                    sr.survey_record_uid,
                    sm.media_kind,
                    sm.media_role,
                    sm.item_code,
                    sm.part_name,
                    sm.sequence_no,
                    sm.original_filename,
                    sm.stored_relative_path,
                    sm.file_sha256,
                    sm.file_size,
                    sm.captured_at,
                    sm.notes,
                    sm.created_at,
                    sm.updated_at
                FROM survey_media AS sm
                JOIN survey_records AS sr
                  ON sr.id = sm.survey_record_id
                WHERE sm.survey_record_id IN (
                    {placeholders}
                )
                ORDER BY
                    sm.survey_record_id,
                    sm.sequence_no,
                    sm.id
                """,
                record_ids,
            ).fetchall()
        ]

    return {
        "project": dict(
            project
        ),
        "batch": dict(
            batch
        ),
        "records": records,
        "assets": assets,
        "inspections": (
            inspections
        ),
        "media": media_rows,
    }


def _validate_records(
    normalized,
    context,
):
    for row in context[
        "records"
    ]:
        if (
            int(row["project_id"])
            != normalized[
                "project_id"
            ]
        ):
            raise ValueError(
                "调查记录不属于指定项目："
                f"{row['id']}。"
            )

        if (
            int(
                row[
                    "survey_batch_id"
                ]
            )
            != normalized[
                "survey_batch_id"
            ]
        ):
            raise ValueError(
                "调查记录不属于指定调查批次："
                f"{row['id']}。"
            )

        if (
            row["record_status"]
            != "completed"
        ):
            raise ValueError(
                "成果包只能包含已完成调查记录："
                f"{row['id']}。"
            )

        if (
            row["record_type"]
            != "engineering"
        ):
            raise ValueError(
                "Stage 11.1 成果包当前只支持工程调查记录："
                f"{row['id']}。"
            )

        if (
            row[
                "engineering_asset_id"
            ]
            is None
        ):
            raise ValueError(
                "工程调查记录没有关联工程对象："
                f"{row['id']}。"
            )

        _require_uid(
            row[
                "survey_record_uid"
            ],
            (
                "调查记录 "
                f"{row['id']}"
            ),
        )

        _require_uid(
            row[
                "engineering_asset_uid"
            ],
            (
                "调查记录关联工程对象 "
                f"{row['id']}"
            ),
        )

        _require_uid(
            row[
                "organization_unit_uid"
            ],
            (
                "调查记录关联管理单位 "
                f"{row['id']}"
            ),
        )

        _require_uid(
            row[
                "canal_unit_uid"
            ],
            (
                "调查记录关联渠系 "
                f"{row['id']}"
            ),
        )

        source_task_uid = (
            _optional_text(
                row[
                    "source_task_uid"
                ]
            )
        )
        source_management_scope_uid = (
            _optional_text(
                row[
                    "source_management_scope_uid"
                ]
            )
        )

        if bool(
            source_task_uid
        ) != bool(
            source_management_scope_uid
        ):
            raise ValueError(
                "调查记录的任务来源信息不完整，"
                "source_task_uid 与 "
                "source_management_scope_uid "
                "必须同时存在或同时为空："
                f"{row['id']}。"
            )


def _validate_assets(
    normalized,
    context,
):
    expected_asset_uids = {
        _require_uid(
            row[
                "engineering_asset_uid"
            ],
            (
                "调查记录关联工程对象 "
                f"{row['id']}"
            ),
        )
        for row in context[
            "records"
        ]
    }

    actual_asset_uids = set()

    for row in context[
        "assets"
    ]:
        if (
            int(row["project_id"])
            != normalized[
                "project_id"
            ]
        ):
            raise ValueError(
                "工程对象不属于指定项目："
                f"{row['asset_name']}。"
            )

        actual_asset_uids.add(
            _require_uid(
                row[
                    "engineering_asset_uid"
                ],
                (
                    "工程对象"
                    f"“{row['asset_name']}”"
                ),
            )
        )

        _require_uid(
            row[
                "organization_unit_uid"
            ],
            (
                "工程对象管理单位"
                f"“{row['asset_name']}”"
            ),
        )

        _require_uid(
            row[
                "canal_unit_uid"
            ],
            (
                "工程对象渠系"
                f"“{row['asset_name']}”"
            ),
        )

    if (
        actual_asset_uids
        != expected_asset_uids
    ):
        raise ValueError(
            "成果包工程对象与调查记录引用不一致。"
        )


def _safe_managed_media_path(
    stored_relative_path,
):
    raw = _clean_text(
        stored_relative_path
    )

    if not raw:
        raise ValueError(
            "影像托管相对路径为空。"
        )

    pure = PurePosixPath(
        raw.replace(
            "\\",
            "/",
        )
    )

    if (
        pure.is_absolute()
        or ".." in pure.parts
    ):
        raise ValueError(
            "影像托管相对路径不安全："
            f"{raw}"
        )

    return (
        database.DATA_DIR
        / Path(*pure.parts)
    )


def _calculate_file_sha256(
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


def _prepare_media(
    context,
):
    metadata = []
    source_files = {}
    total_media_bytes = 0

    for row in context[
        "media"
    ]:
        media_uid = _require_uid(
            row["media_uid"],
            "调查影像",
        )

        survey_record_uid = (
            _require_uid(
                row[
                    "survey_record_uid"
                ],
                "影像关联调查记录",
            )
        )

        absolute_path = (
            _safe_managed_media_path(
                row[
                    "stored_relative_path"
                ]
            )
        )

        if not absolute_path.exists():
            raise FileNotFoundError(
                "调查影像托管文件不存在："
                f"{absolute_path}"
            )

        if not absolute_path.is_file():
            raise ValueError(
                "调查影像托管路径不是文件："
                f"{absolute_path}"
            )

        actual_size = (
            absolute_path.stat().st_size
        )

        expected_size = int(
            row["file_size"]
        )

        if actual_size != expected_size:
            raise ValueError(
                "调查影像文件大小与数据库记录不一致："
                f"{row['original_filename']}。"
            )

        actual_hash = (
            _calculate_file_sha256(
                absolute_path
            )
        )

        expected_hash = _clean_text(
            row["file_sha256"]
        ).lower()

        if actual_hash != expected_hash:
            raise ValueError(
                "调查影像 SHA-256 与数据库记录不一致："
                f"{row['original_filename']}。"
            )

        suffix = (
            absolute_path.suffix
            .lower()
        )

        package_path = (
            "media/"
            + media_uid
            + suffix
        )

        if package_path in source_files:
            raise ValueError(
                "成果包影像路径重复："
                f"{package_path}"
            )

        source_files[
            package_path
        ] = absolute_path

        total_media_bytes += (
            actual_size
        )

        metadata.append(
            {
                "media_uid": (
                    media_uid
                ),
                "survey_record_uid": (
                    survey_record_uid
                ),
                "media_kind": (
                    row["media_kind"]
                ),
                "media_role": (
                    row["media_role"]
                ),
                "item_code": (
                    row["item_code"]
                ),
                "part_name": (
                    row["part_name"]
                ),
                "sequence_no": int(
                    row["sequence_no"]
                ),
                "original_filename": (
                    row[
                        "original_filename"
                    ]
                ),
                "package_path": (
                    package_path
                ),
                "file_sha256": (
                    actual_hash
                ),
                "file_size": (
                    actual_size
                ),
                "captured_at": (
                    row["captured_at"]
                ),
                "notes": (
                    row["notes"]
                ),
                "created_at": (
                    row["created_at"]
                ),
                "updated_at": (
                    row["updated_at"]
                ),
            }
        )

    return (
        metadata,
        source_files,
        total_media_bytes,
    )


def _serialize_assets(
    context,
):
    result = []

    for row in context[
        "assets"
    ]:
        result.append(
            {
                "engineering_asset_uid": (
                    _require_uid(
                        row[
                            "engineering_asset_uid"
                        ],
                        "工程对象",
                    )
                ),
                "project_uid": (
                    _require_uid(
                        row[
                            "project_uid"
                        ],
                        "工程对象所属项目",
                    )
                ),
                "asset_name": (
                    row["asset_name"]
                ),
                "asset_type": (
                    row["asset_type"]
                ),
                "organization_unit_uid": (
                    _require_uid(
                        row[
                            "organization_unit_uid"
                        ],
                        "工程对象管理单位",
                    )
                ),
                "canal_unit_uid": (
                    _require_uid(
                        row[
                            "canal_unit_uid"
                        ],
                        "工程对象渠系",
                    )
                ),
                "business_code": (
                    row["business_code"]
                ),
                "code_scheme_version": (
                    row[
                        "code_scheme_version"
                    ]
                ),
                "single_stake_text": (
                    row[
                        "single_stake_text"
                    ]
                ),
                "single_stake_value": (
                    row[
                        "single_stake_value"
                    ]
                ),
                "start_stake_text": (
                    row[
                        "start_stake_text"
                    ]
                ),
                "start_stake_value": (
                    row[
                        "start_stake_value"
                    ]
                ),
                "end_stake_text": (
                    row[
                        "end_stake_text"
                    ]
                ),
                "end_stake_value": (
                    row[
                        "end_stake_value"
                    ]
                ),
                "first_survey_batch_uid": (
                    row[
                        "first_survey_batch_uid"
                    ]
                ),
                "status": (
                    row["status"]
                ),
                "notes": (
                    row["notes"]
                ),
                "created_at": (
                    row["created_at"]
                ),
                "updated_at": (
                    row["updated_at"]
                ),
            }
        )

    return result


def _serialize_records(
    context,
):
    result = []

    for row in context[
        "records"
    ]:
        try:
            record_data = json.loads(
                row[
                    "record_data_json"
                ]
                or "{}"
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "调查记录 record_data_json "
                f"不是有效 JSON：{row['id']}。"
            ) from error

        result.append(
            {
                "survey_record_uid": (
                    _require_uid(
                        row[
                            "survey_record_uid"
                        ],
                        "调查记录",
                    )
                ),
                "source_task_uid": (
                    _optional_text(
                        row[
                            "source_task_uid"
                        ]
                    )
                ),
                "source_management_scope_uid": (
                    _optional_text(
                        row[
                            "source_management_scope_uid"
                        ]
                    )
                ),
                "project_uid": (
                    _require_uid(
                        row[
                            "project_uid"
                        ],
                        "调查记录所属项目",
                    )
                ),
                "survey_batch_uid": (
                    _require_uid(
                        row[
                            "survey_batch_uid"
                        ],
                        "调查记录所属批次",
                    )
                ),
                "form": {
                    "form_code": (
                        row["form_code"]
                    ),
                    "form_number": (
                        row["form_number"]
                    ),
                    "form_name": (
                        row["form_name"]
                    ),
                    "asset_type": (
                        row[
                            "form_asset_type"
                        ]
                    ),
                    "version_code": (
                        row[
                            "version_code"
                        ]
                    ),
                    "version_name": (
                        row[
                            "version_name"
                        ]
                    ),
                    "effective_date": (
                        row[
                            "effective_date"
                        ]
                    ),
                },
                "record_type": (
                    row["record_type"]
                ),
                "organization_unit_uid": (
                    _require_uid(
                        row[
                            "organization_unit_uid"
                        ],
                        "调查记录管理单位",
                    )
                ),
                "canal_unit_uid": (
                    _require_uid(
                        row[
                            "canal_unit_uid"
                        ],
                        "调查记录渠系",
                    )
                ),
                "engineering_asset_uid": (
                    _require_uid(
                        row[
                            "engineering_asset_uid"
                        ],
                        "调查记录工程对象",
                    )
                ),
                "business_code": (
                    row["business_code"]
                ),
                "survey_date": (
                    row["survey_date"]
                ),
                "overall_grade": (
                    row["overall_grade"]
                ),
                "survey_comment": (
                    row["survey_comment"]
                ),
                "record_status": (
                    row["record_status"]
                ),
                "record_data": (
                    record_data
                ),
                "void_reason": (
                    row["void_reason"]
                ),
                "created_at": (
                    row["created_at"]
                ),
                "updated_at": (
                    row["updated_at"]
                ),
            }
        )

    return result


def _serialize_inspections(
    context,
):
    return [
        {
            "survey_record_uid": (
                _require_uid(
                    row[
                        "survey_record_uid"
                    ],
                    "分项评价关联调查记录",
                )
            ),
            "item_code": (
                row["item_code"]
            ),
            "category": (
                row["category"]
            ),
            "item_name": (
                row["item_name"]
            ),
            "grade": (
                row["grade"]
            ),
            "description": (
                row["description"]
            ),
            "remark": (
                row["remark"]
            ),
            "updated_at": (
                row["updated_at"]
            ),
        }
        for row in context[
            "inspections"
        ]
    ]


def export_survey_result_package(
    request,
):
    """
    导出调查成果包。

    Stage 11.1 只负责从本地数据库生成可交换成果：
    - 不修改现有业务数据；
    - 不执行跨库导入；
    - 不做冲突合并；
    - 只导出明确选择的 completed 工程调查记录及其依赖数据。
    """

    integrity = (
        check_master_data_integrity()
    )

    if not integrity.passed:
        raise ValueError(
            "正式主数据一致性检查未通过，"
            "不能生成调查成果包。"
        )

    normalized = (
        _normalize_request(
            request
        )
    )

    context = (
        _load_export_context(
            normalized
        )
    )

    _validate_records(
        normalized,
        context,
    )

    _validate_assets(
        normalized,
        context,
    )

    project_uid = (
        _require_uid(
            context[
                "project"
            ]["project_uid"],
            "项目",
        )
    )

    batch_uid = (
        _require_uid(
            context[
                "batch"
            ][
                "survey_batch_uid"
            ],
            "调查批次",
        )
    )

    assets = (
        _serialize_assets(
            context
        )
    )

    records = (
        _serialize_records(
            context
        )
    )

    source_task_uids = tuple(
        sorted(
            {
                str(
                    item[
                        "source_task_uid"
                    ]
                ).strip()
                for item in records
                if item.get(
                    "source_task_uid"
                )
            }
        )
    )

    source_task_uid = (
        source_task_uids[0]
        if len(source_task_uids) == 1
        else None
    )

    inspections = (
        _serialize_inspections(
            context
        )
    )

    (
        media,
        media_source_files,
        media_bytes,
    ) = _prepare_media(
        context
    )

    result_uid = (
        new_stable_token()
    )

    package_uid = (
        new_stable_token()
    )

    created_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    result_name = (
        normalized[
            "result_name"
        ]
        or (
            f"{context['batch']['batch_name']}"
            "调查成果"
        )
    )

    result_document = {
        "result_schema_version": (
            RESULT_SCHEMA_VERSION
        ),
        "result_uid": (
            result_uid
        ),
        "result_name": (
            result_name
        ),
        "source_task_uid": (
            source_task_uid
        ),
        "source_task_uids": list(
            source_task_uids
        ),
        "project": {
            "project_uid": (
                project_uid
            ),
            "name": (
                context[
                    "project"
                ]["name"]
            ),
            "short_name": (
                context[
                    "project"
                ]["short_name"]
            ),
        },
        "survey_batch": {
            "survey_batch_uid": (
                batch_uid
            ),
            "batch_name": (
                context[
                    "batch"
                ]["batch_name"]
            ),
            "batch_code": (
                context[
                    "batch"
                ]["batch_code"]
            ),
            "start_date": (
                context[
                    "batch"
                ]["start_date"]
            ),
            "end_date": (
                context[
                    "batch"
                ]["end_date"]
            ),
        },
        "creator": (
            normalized[
                "creator"
            ]
        ),
        "notes": (
            normalized[
                "notes"
            ]
        ),
        "counts": {
            "engineering_assets": (
                len(assets)
            ),
            "survey_records": (
                len(records)
            ),
            "inspection_results": (
                len(inspections)
            ),
            "survey_media": (
                len(media)
            ),
        },
        "created_at": (
            created_at
        ),
    }

    payload_files = {
        "result.json": (
            encode_json_bytes(
                result_document
            )
        ),
        (
            "data/"
            "engineering_assets.json"
        ): (
            encode_json_bytes(
                {
                    "items": assets,
                }
            )
        ),
        (
            "data/"
            "survey_records.json"
        ): (
            encode_json_bytes(
                {
                    "items": records,
                }
            )
        ),
        (
            "data/"
            "inspection_results.json"
        ): (
            encode_json_bytes(
                {
                    "items": inspections,
                }
            )
        ),
        (
            "data/"
            "survey_media.json"
        ): (
            encode_json_bytes(
                {
                    "items": media,
                }
            )
        ),
    }

    manifest = {
        "package_kind": (
            SURVEY_RESULT_PACKAGE_KIND
        ),
        "result_schema_version": (
            RESULT_SCHEMA_VERSION
        ),
        "created_at": (
            created_at
        ),
        "app_version": (
            APP_VERSION
        ),
        "app_version_label": (
            APP_VERSION_LABEL
        ),
        "result_uid": (
            result_uid
        ),
        "source_task_uid": (
            source_task_uid
        ),
        "source_task_uids": list(
            source_task_uids
        ),
        "project_uid": (
            project_uid
        ),
        "survey_batch_uid": (
            batch_uid
        ),
    }

    write_result = (
        write_package_streaming(
            normalized[
                "output_path"
            ],
            package_uid=(
                package_uid
            ),
            manifest=manifest,
            payload_files=(
                payload_files
            ),
            source_files=(
                media_source_files
            ),
        )
    )

    return SurveyResultExportResult(
        output_path=(
            write_result.output_path
        ),
        package_uid=(
            package_uid
        ),
        result_uid=(
            result_uid
        ),
        survey_record_count=(
            len(records)
        ),
        engineering_asset_count=(
            len(assets)
        ),
        inspection_result_count=(
            len(inspections)
        ),
        media_count=(
            len(media)
        ),
        media_bytes=(
            media_bytes
        ),
    )
