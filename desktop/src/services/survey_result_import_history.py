from __future__ import annotations

from dataclasses import dataclass
import json

import database


@dataclass(frozen=True)
class SurveyResultImportHistoryItem:
    import_id: int
    imported_at: str
    source_package_name: str
    result_name: str

    source_task_uids: tuple[str, ...]
    organization_uids: tuple[str, ...]
    organization_names: tuple[str, ...]
    department_names: tuple[str, ...]

    assets_total: int
    records_total: int
    inspections_total: int
    media_total: int

    imported_assets: int
    imported_records: int
    imported_inspections: int
    imported_media: int

    status_text: str = "已导入"


def _clean_text(value):
    return str(value or "").strip()


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_summary(raw_value):
    raw = _clean_text(raw_value)

    if not raw:
        return {}

    try:
        value = json.loads(raw)
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return {}

    return value if isinstance(value, dict) else {}


def _normalize_task_uids(summary):
    raw = summary.get("source_task_uids")

    if not isinstance(raw, (list, tuple)):
        raw = ()

    result = []

    for value in raw:
        uid = _clean_text(value)

        if uid and uid not in result:
            result.append(uid)

    return tuple(result)


def _load_issue_identity_map(
    connection,
    task_uids,
):
    task_uids = tuple(
        dict.fromkeys(
            uid
            for uid in task_uids
            if _clean_text(uid)
        )
    )

    if not task_uids:
        return {}

    table_exists = (
        connection.execute(
            '''
            SELECT 1
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name = 'survey_task_issues'
            '''
        ).fetchone()
        is not None
    )

    if not table_exists:
        return {}

    placeholders = ",".join(
        "?"
        for _ in task_uids
    )

    rows = connection.execute(
        f'''
        SELECT
            task_uid,
            organization_unit_uid,
            organization_name_snapshot,
            department_name_snapshot
        FROM survey_task_issues
        WHERE task_uid IN ({placeholders})
        ''',
        task_uids,
    ).fetchall()

    return {
        _clean_text(row["task_uid"]): {
            "organization_uid": _clean_text(
                row["organization_unit_uid"]
            ),
            "organization_name": _clean_text(
                row["organization_name_snapshot"]
            ),
            "department_name": _clean_text(
                row["department_name_snapshot"]
            ),
        }
        for row in rows
    }


def list_survey_result_import_history(
    *,
    project_id,
    survey_batch_id,
    organization_uid=None,
):
    '''
    返回指定项目/调查批次的成果接收历史。

    排序：
    - imported_at 倒序；
    - 同一秒内按 import id 倒序。

    分类：
    - 通过成果包 source_task_uids
      回溯上级端 survey_task_issues 冻结历史；
    - 可按任务分发时的管理单位稳定 UID 过滤。
    '''

    try:
        project_id = int(project_id)
        survey_batch_id = int(
            survey_batch_id
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "成果接收历史的项目或调查批次 ID 无效。"
        ) from error

    filter_organization_uid = (
        _clean_text(
            organization_uid
        )
        or None
    )

    with database.get_connection() as connection:
        identity = connection.execute(
            '''
            SELECT
                p.project_uid,
                sb.survey_batch_uid
            FROM projects AS p
            JOIN survey_batches AS sb
              ON sb.project_id = p.id
            WHERE
                p.id = ?
                AND sb.id = ?
            ''',
            (
                project_id,
                survey_batch_id,
            ),
        ).fetchone()

        if identity is None:
            return ()

        rows = connection.execute(
            '''
            SELECT
                id,
                source_package_name,
                summary_json,
                imported_at
            FROM survey_result_imports
            WHERE
                project_uid = ?
                AND survey_batch_uid = ?
            ORDER BY
                imported_at DESC,
                id DESC
            ''',
            (
                identity["project_uid"],
                identity["survey_batch_uid"],
            ),
        ).fetchall()

        prepared = []
        all_task_uids = []

        for row in rows:
            summary = _load_summary(
                row["summary_json"]
            )
            task_uids = (
                _normalize_task_uids(
                    summary
                )
            )

            prepared.append(
                (
                    row,
                    summary,
                    task_uids,
                )
            )
            all_task_uids.extend(
                task_uids
            )

        issue_map = _load_issue_identity_map(
            connection,
            all_task_uids,
        )

    result = []

    for (
        row,
        summary,
        task_uids,
    ) in prepared:
        organization_uids = []
        organization_names = []
        department_names = []

        for task_uid in task_uids:
            identity_item = issue_map.get(
                task_uid
            )

            if not identity_item:
                continue

            organization_uid_value = (
                identity_item[
                    "organization_uid"
                ]
            )
            organization_name = (
                identity_item[
                    "organization_name"
                ]
            )
            department_name = (
                identity_item[
                    "department_name"
                ]
            )

            if (
                organization_uid_value
                and organization_uid_value
                not in organization_uids
            ):
                organization_uids.append(
                    organization_uid_value
                )

            if (
                organization_name
                and organization_name
                not in organization_names
            ):
                organization_names.append(
                    organization_name
                )

            if (
                department_name
                and department_name
                not in department_names
            ):
                department_names.append(
                    department_name
                )

        if (
            filter_organization_uid
            and filter_organization_uid
            not in organization_uids
        ):
            continue

        source_package_name = _clean_text(
            row["source_package_name"]
        )

        result_name = (
            _clean_text(
                summary.get(
                    "result_name"
                )
            )
            or source_package_name
            or "未命名成果包"
        )

        result.append(
            SurveyResultImportHistoryItem(
                import_id=int(row["id"]),
                imported_at=_clean_text(
                    row["imported_at"]
                ),
                source_package_name=(
                    source_package_name
                ),
                result_name=result_name,
                source_task_uids=(
                    task_uids
                ),
                organization_uids=tuple(
                    organization_uids
                ),
                organization_names=tuple(
                    organization_names
                ),
                department_names=tuple(
                    department_names
                ),
                assets_total=_safe_int(
                    summary.get(
                        "assets_total"
                    )
                ),
                records_total=_safe_int(
                    summary.get(
                        "records_total"
                    )
                ),
                inspections_total=_safe_int(
                    summary.get(
                        "inspections_total"
                    )
                ),
                media_total=_safe_int(
                    summary.get(
                        "media_total"
                    )
                ),
                imported_assets=_safe_int(
                    summary.get(
                        "imported_assets"
                    )
                ),
                imported_records=_safe_int(
                    summary.get(
                        "imported_records"
                    )
                ),
                imported_inspections=_safe_int(
                    summary.get(
                        "imported_inspections"
                    )
                ),
                imported_media=_safe_int(
                    summary.get(
                        "imported_media"
                    )
                ),
            )
        )

    return tuple(result)
