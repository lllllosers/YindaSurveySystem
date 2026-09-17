from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import database

from services.master_data_integrity import (
    check_master_data_integrity,
)
from services.yd_package import (
    SURVEY_TASK_PACKAGE_KIND,
    encode_json_bytes,
    new_stable_token,
    normalize_task_package_path,
    write_package,
)
from version import (
    APP_VERSION,
    APP_VERSION_LABEL,
)


@dataclass(frozen=True)
class SurveyTaskExportRequest:
    project_id: int
    survey_batch_id: int
    organization_unit_id: int
    canal_ids: tuple[int, ...]
    task_name: str
    output_path: Path
    notes: str = ""


@dataclass(frozen=True)
class SurveyTaskExportResult:
    output_path: Path
    package_uid: str
    task_uid: str
    organization_name: str
    selected_canal_count: int
    reference_canal_count: int
    reference_organization_count: int
    form_count: int


def _clean_text(
    value,
):
    return str(
        value or ""
    ).strip()


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
        organization_unit_id = int(
            request.organization_unit_id
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "任务包项目、批次或管理单位 ID 无效。"
        ) from error

    canal_ids = []

    for raw_id in (
        request.canal_ids or ()
    ):
        try:
            canal_id = int(
                raw_id
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "任务包包含无效渠系 ID。"
            ) from error

        if canal_id not in canal_ids:
            canal_ids.append(
                canal_id
            )

    if not canal_ids:
        raise ValueError(
            "调查任务至少需要选择一个渠系。"
        )

    task_name = _clean_text(
        request.task_name
    )

    if not task_name:
        raise ValueError(
            "任务名称不能为空。"
        )

    notes = _clean_text(
        request.notes
    )

    output_path = (
        normalize_task_package_path(
            request.output_path
        )
    )

    return {
        "project_id": project_id,
        "survey_batch_id": (
            survey_batch_id
        ),
        "organization_unit_id": (
            organization_unit_id
        ),
        "canal_ids": tuple(
            canal_ids
        ),
        "task_name": task_name,
        "notes": notes,
        "output_path": (
            output_path
        ),
    }


def _load_context(
    normalized,
):
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
            int(batch["project_id"])
            != int(project["id"])
        ):
            raise ValueError(
                "调查批次不属于指定项目。"
            )

        office = connection.execute(
            """
            SELECT
                id,
                organization_unit_uid,
                parent_id,
                name,
                unit_type,
                business_code,
                status,
                description,
                sort_order
            FROM organization_units
            WHERE id = ?
            """,
            (
                normalized[
                    "organization_unit_id"
                ],
            ),
        ).fetchone()

        if office is None:
            raise ValueError(
                "没有找到指定管理单位。"
            )

        if (
            office["unit_type"]
            != "water_office"
        ):
            raise ValueError(
                "调查任务必须分配给末级管理单位。"
            )

        if office["status"] != "active":
            raise ValueError(
                "当前管理单位已停用，不能创建调查任务。"
            )

        department = connection.execute(
            """
            SELECT
                id,
                organization_unit_uid,
                name,
                unit_type,
                business_code,
                status,
                description,
                sort_order
            FROM organization_units
            WHERE id = ?
            """,
            (
                office["parent_id"],
            ),
        ).fetchone()

        if (
            department is None
            or department["unit_type"]
            != "department"
        ):
            raise ValueError(
                "当前管理单位没有有效的所属基层处。"
            )

        all_canals = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    id,
                    canal_unit_uid,
                    parent_id,
                    name,
                    canal_level,
                    organization_unit_id,
                    status,
                    description,
                    sort_order
                FROM canal_units
                ORDER BY
                    CASE
                        WHEN sort_order > 0
                        THEN sort_order
                        ELSE 1000000 + id
                    END,
                    id
                """
            ).fetchall()
        ]

        forms = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    fd.form_code,
                    fd.form_number,
                    fd.form_name,
                    fd.asset_type,
                    fd.sort_order,
                    fv.version_code,
                    fv.version_name,
                    fv.effective_date
                FROM form_definitions AS fd
                LEFT JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                 AND fv.is_current = 1
                WHERE fd.series = 'series_2'
                  AND fd.record_type = 'engineering'
                  AND fd.is_enabled = 1
                ORDER BY
                    fd.sort_order,
                    fd.form_code
                """
            ).fetchall()
        ]

    return {
        "project": dict(
            project
        ),
        "batch": dict(batch),
        "office": dict(office),
        "department": dict(
            department
        ),
        "all_canals": (
            all_canals
        ),
        "forms": forms,
    }


def _require_stable_uid(
    row,
    field_name,
    entity_name,
):
    uid = _clean_text(
        row.get(
            field_name
        )
    )

    if not uid:
        raise ValueError(
            f"{entity_name}缺少稳定 UID。"
        )

    return uid


def _build_selected_canals(
    normalized,
    context,
):
    all_canals = context[
        "all_canals"
    ]

    by_id = {
        int(row["id"]): row
        for row in all_canals
    }

    requested_ids = set(
        normalized[
            "canal_ids"
        ]
    )

    missing_ids = (
        requested_ids
        - set(by_id)
    )

    if missing_ids:
        missing_text = ", ".join(
            str(item)
            for item in sorted(
                missing_ids
            )
        )

        raise ValueError(
            "任务包含不存在的渠系 ID："
            f"{missing_text}。"
        )

    office_id = normalized[
        "organization_unit_id"
    ]

    selected = []

    for row in all_canals:
        canal_id = int(
            row["id"]
        )

        if canal_id not in requested_ids:
            continue

        if row["status"] != "active":
            raise ValueError(
                "任务不能包含停用渠系："
                f"{row['name']}。"
            )

        if (
            row[
                "organization_unit_id"
            ]
            is None
            or int(
                row[
                    "organization_unit_id"
                ]
            )
            != office_id
        ):
            raise ValueError(
                "所选渠系不属于当前管理单位："
                f"{row['name']}。"
            )

        _require_stable_uid(
            row,
            "canal_unit_uid",
            (
                f"渠系“{row['name']}”"
            ),
        )

        selected.append(
            row
        )

    if not selected:
        raise ValueError(
            "调查任务没有可导出的有效渠系。"
        )

    return selected, by_id


def _collect_reference_canal_ids(
    selected,
    by_id,
):
    reference_ids = set()

    for row in selected:
        current = row
        visited = set()

        while current is not None:
            current_id = int(
                current["id"]
            )

            if current_id in visited:
                raise ValueError(
                    "渠系层级存在循环引用。"
                )

            visited.add(
                current_id
            )
            reference_ids.add(
                current_id
            )

            parent_id = current[
                "parent_id"
            ]

            if parent_id is None:
                break

            current = by_id.get(
                int(parent_id)
            )

            if current is None:
                raise ValueError(
                    "渠系上级节点缺失："
                    f"{row['name']}。"
                )

    return reference_ids


def _build_reference_organizations(
    context,
):
    department = context[
        "department"
    ]
    office = context["office"]

    department_uid = (
        _require_stable_uid(
            department,
            "organization_unit_uid",
            "所属基层处",
        )
    )

    office_uid = (
        _require_stable_uid(
            office,
            "organization_unit_uid",
            "管理单位",
        )
    )

    items = [
        {
            "organization_uid": (
                department_uid
            ),
            "parent_organization_uid": None,
            "name": (
                department["name"]
            ),
            "unit_type": (
                department[
                    "unit_type"
                ]
            ),
            "business_code": (
                department[
                    "business_code"
                ]
            ),
            "status": (
                department[
                    "status"
                ]
            ),
            "description": (
                department[
                    "description"
                ]
            ),
            "sort_order": int(
                department[
                    "sort_order"
                ]
                or 0
            ),
        },
        {
            "organization_uid": (
                office_uid
            ),
            "parent_organization_uid": (
                department_uid
            ),
            "name": office["name"],
            "unit_type": (
                office["unit_type"]
            ),
            "business_code": (
                office[
                    "business_code"
                ]
            ),
            "status": (
                office["status"]
            ),
            "description": (
                office[
                    "description"
                ]
            ),
            "sort_order": int(
                office[
                    "sort_order"
                ]
                or 0
            ),
        },
    ]

    return (
        items,
        department_uid,
        office_uid,
    )


def _build_reference_canals(
    context,
    reference_ids,
):
    by_id = {
        int(row["id"]): row
        for row in context[
            "all_canals"
        ]
    }

    organization_uid_by_id = {}

    with database.get_connection() as connection:
        for row in connection.execute(
            """
            SELECT
                id,
                organization_unit_uid
            FROM organization_units
            """
        ).fetchall():
            organization_uid_by_id[
                int(row["id"])
            ] = _clean_text(
                row[
                    "organization_unit_uid"
                ]
            )

    items = []

    for row in context[
        "all_canals"
    ]:
        canal_id = int(
            row["id"]
        )

        if canal_id not in reference_ids:
            continue

        canal_uid = (
            _require_stable_uid(
                row,
                "canal_unit_uid",
                (
                    f"渠系“{row['name']}”"
                ),
            )
        )

        parent_uid = None

        if row["parent_id"] is not None:
            parent = by_id.get(
                int(
                    row[
                        "parent_id"
                    ]
                )
            )

            if parent is None:
                raise ValueError(
                    "渠系上级节点缺失："
                    f"{row['name']}。"
                )

            parent_uid = (
                _require_stable_uid(
                    parent,
                    "canal_unit_uid",
                    (
                        "上级渠系"
                        f"“{parent['name']}”"
                    ),
                )
            )

        management_uid = None

        if (
            row[
                "organization_unit_id"
            ]
            is not None
        ):
            management_uid = (
                organization_uid_by_id.get(
                    int(
                        row[
                            "organization_unit_id"
                        ]
                    )
                )
            )

            if not management_uid:
                raise ValueError(
                    "渠系管理单位缺少稳定 UID："
                    f"{row['name']}。"
                )

        items.append(
            {
                "canal_uid": (
                    canal_uid
                ),
                "parent_canal_uid": (
                    parent_uid
                ),
                "name": row["name"],
                "canal_level": (
                    row[
                        "canal_level"
                    ]
                ),
                "management_organization_uid": (
                    management_uid
                ),
                "status": (
                    row["status"]
                ),
                "description": (
                    row[
                        "description"
                    ]
                ),
                "sort_order": int(
                    row["sort_order"]
                    or 0
                ),
            }
        )

    return items


def _build_form_reference(
    context,
):
    return [
        {
            "form_code": (
                row["form_code"]
            ),
            "form_number": (
                row[
                    "form_number"
                ]
            ),
            "form_name": (
                row["form_name"]
            ),
            "asset_type": (
                row["asset_type"]
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
        }
        for row in context[
            "forms"
        ]
    ]


def export_survey_task_package(
    request,
):
    """
    导出一个纸质外业调查任务范围包。

    这个阶段只做“任务定义 + 参考主数据”，不创建工程、
    调查记录，也不包含调查结果或影像。
    """

    integrity = (
        check_master_data_integrity()
    )

    if not integrity.passed:
        raise ValueError(
            "正式主数据一致性检查未通过，"
            "不能生成调查任务包。"
        )

    normalized = (
        _normalize_request(
            request
        )
    )

    context = _load_context(
        normalized
    )

    project = context[
        "project"
    ]
    batch = context["batch"]

    project_uid = (
        _require_stable_uid(
            project,
            "project_uid",
            "项目",
        )
    )

    batch_uid = (
        _require_stable_uid(
            batch,
            "survey_batch_uid",
            "调查批次",
        )
    )

    (
        selected,
        by_id,
    ) = _build_selected_canals(
        normalized,
        context,
    )

    reference_canal_ids = (
        _collect_reference_canal_ids(
            selected,
            by_id,
        )
    )

    (
        organization_reference,
        department_uid,
        office_uid,
    ) = _build_reference_organizations(
        context
    )

    canal_reference = (
        _build_reference_canals(
            context,
            reference_canal_ids,
        )
    )

    form_reference = (
        _build_form_reference(
            context
        )
    )

    selected_canal_uids = [
        _require_stable_uid(
            row,
            "canal_unit_uid",
            (
                f"渠系“{row['name']}”"
            ),
        )
        for row in selected
    ]

    task_uid = (
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

    task_data = {
        "task_uid": task_uid,
        "task_name": (
            normalized[
                "task_name"
            ]
        ),
        "notes": (
            normalized[
                "notes"
            ]
            or None
        ),
        "project": {
            "project_uid": (
                project_uid
            ),
            "name": (
                project["name"]
            ),
            "short_name": (
                project[
                    "short_name"
                ]
            ),
        },
        "survey_batch": {
            "survey_batch_uid": (
                batch_uid
            ),
            "batch_name": (
                batch[
                    "batch_name"
                ]
            ),
            "batch_code": (
                batch[
                    "batch_code"
                ]
            ),
            "start_date": (
                batch[
                    "start_date"
                ]
            ),
            "end_date": (
                batch[
                    "end_date"
                ]
            ),
        },
        "assignment": {
            "department_uid": (
                department_uid
            ),
            "department_name": (
                context[
                    "department"
                ]["name"]
            ),
            "organization_unit_uid": (
                office_uid
            ),
            "organization_name": (
                context[
                    "office"
                ]["name"]
            ),
        },
        "scope": {
            "selected_canal_uids": (
                selected_canal_uids
            ),
            "selected_canal_count": (
                len(
                    selected_canal_uids
                )
            ),
        },
        "created_at": created_at,
    }

    organization_data = {
        "items": (
            organization_reference
        )
    }

    canal_data = {
        "items": (
            canal_reference
        )
    }

    form_data = {
        "items": (
            form_reference
        )
    }

    manifest = {
        "package_kind": (
            SURVEY_TASK_PACKAGE_KIND
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
        "task_uid": task_uid,
        "project_uid": (
            project_uid
        ),
        "survey_batch_uid": (
            batch_uid
        ),
    }

    payload_files = {
        "task.json": (
            encode_json_bytes(
                task_data
            )
        ),
        (
            "reference/"
            "organization_units.json"
        ): (
            encode_json_bytes(
                organization_data
            )
        ),
        (
            "reference/"
            "canal_units.json"
        ): (
            encode_json_bytes(
                canal_data
            )
        ),
        (
            "reference/"
            "forms.json"
        ): (
            encode_json_bytes(
                form_data
            )
        ),
    }

    write_result = (
        write_package(
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
        )
    )

    return SurveyTaskExportResult(
        output_path=(
            write_result.output_path
        ),
        package_uid=(
            package_uid
        ),
        task_uid=task_uid,
        organization_name=(
            context[
                "office"
            ]["name"]
        ),
        selected_canal_count=(
            len(selected)
        ),
        reference_canal_count=(
            len(canal_reference)
        ),
        reference_organization_count=(
            len(
                organization_reference
            )
        ),
        form_count=(
            len(form_reference)
        ),
    )
