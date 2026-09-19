from __future__ import annotations

from dataclasses import dataclass

import database


@dataclass(frozen=True)
class SurveyTaskTrackingItem:
    issue_id: int
    task_uid: str
    issued_at: str

    department_name: str
    organization_uid: str
    organization_name: str

    task_name: str
    selected_scope_count: int
    returned_record_count: int

    status_text: str


def _clean_text(value):
    return str(
        value or ""
    ).strip()


def _required_tables_available(
    connection,
):
    required = {
        "projects",
        "survey_batches",
        "survey_task_issues",
        "survey_records",
    }

    available = {
        str(row["name"])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
    }

    return required.issubset(
        available
    )


def list_survey_task_tracking(
    *,
    project_id,
    survey_batch_id,
    organization_uid=None,
):
    """
    返回当前项目/调查批次的任务分发历史及成果回收状态。

    事实来源：
    - 任务信息来自不可变 survey_task_issues 冻结历史；
    - 回收数量来自 survey_records.source_task_uid；
    - 不使用名称匹配推断任务与成果关系。

    状态仅表达“是否已有调查记录返回”，
    不把“已有成果返回”误判为整个调查任务已经完成。
    """

    try:
        project_id = int(
            project_id
        )
        survey_batch_id = int(
            survey_batch_id
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "任务分发历史的项目或调查批次 ID 无效。"
        ) from error

    filter_organization_uid = (
        _clean_text(
            organization_uid
        )
        or None
    )

    with database.get_connection() as connection:
        if not _required_tables_available(
            connection
        ):
            return ()

        identity = connection.execute(
            """
            SELECT
                p.project_uid,
                sb.survey_batch_uid
            FROM projects AS p
            JOIN survey_batches AS sb
              ON sb.project_id = p.id
            WHERE
                p.id = ?
                AND sb.id = ?
            """,
            (
                project_id,
                survey_batch_id,
            ),
        ).fetchone()

        if identity is None:
            return ()

        parameters = [
            project_id,
            survey_batch_id,
            identity["project_uid"],
            identity["survey_batch_uid"],
        ]

        organization_filter_sql = ""

        if filter_organization_uid:
            organization_filter_sql = (
                "\n  AND sti.organization_unit_uid = ?"
            )
            parameters.append(
                filter_organization_uid
            )

        rows = connection.execute(
            f"""
            SELECT
                sti.id,
                sti.task_uid,
                sti.issued_at,
                sti.department_name_snapshot,
                sti.organization_unit_uid,
                sti.organization_name_snapshot,
                sti.task_name,
                sti.selected_scope_count,

                COUNT(
                    DISTINCT CASE
                        WHEN sr.record_status = 'completed'
                        THEN sr.id
                    END
                ) AS returned_record_count

            FROM survey_task_issues AS sti

            LEFT JOIN survey_records AS sr
              ON sr.source_task_uid = sti.task_uid
             AND sr.project_id = ?
             AND sr.survey_batch_id = ?

            WHERE
                sti.project_uid = ?
                AND sti.survey_batch_uid = ?
                {organization_filter_sql}

            GROUP BY
                sti.id,
                sti.task_uid,
                sti.issued_at,
                sti.department_name_snapshot,
                sti.organization_unit_uid,
                sti.organization_name_snapshot,
                sti.task_name,
                sti.selected_scope_count

            ORDER BY
                sti.issued_at DESC,
                sti.id DESC
            """,
            tuple(
                parameters
            ),
        ).fetchall()

    result = []

    for row in rows:
        returned_record_count = int(
            row[
                "returned_record_count"
            ]
            or 0
        )

        result.append(
            SurveyTaskTrackingItem(
                issue_id=int(
                    row["id"]
                ),
                task_uid=_clean_text(
                    row["task_uid"]
                ),
                issued_at=_clean_text(
                    row["issued_at"]
                ),
                department_name=_clean_text(
                    row[
                        "department_name_snapshot"
                    ]
                ),
                organization_uid=_clean_text(
                    row[
                        "organization_unit_uid"
                    ]
                ),
                organization_name=_clean_text(
                    row[
                        "organization_name_snapshot"
                    ]
                ),
                task_name=_clean_text(
                    row["task_name"]
                ),
                selected_scope_count=int(
                    row[
                        "selected_scope_count"
                    ]
                    or 0
                ),
                returned_record_count=(
                    returned_record_count
                ),
                status_text=(
                    "已有成果返回"
                    if returned_record_count > 0
                    else "待回收"
                ),
            )
        )

    return tuple(
        result
    )
