from __future__ import annotations

from database import get_connection


def _empty_summary() -> dict:
    return {
        "total_records": 0,
        "completed_records": 0,
        "draft_records": 0,
        "completion_rate": None,
        "grades": {
            "A": 0,
            "B": 0,
            "C": 0,
            "D": 0,
        },
    }


def _finalize_summary(summary: dict) -> dict:
    total = int(summary["total_records"])
    completed = int(summary["completed_records"])

    if total > 0:
        summary["completion_rate"] = (
            completed * 100.0 / total
        )
    else:
        summary["completion_rate"] = None

    return summary


def _accumulate(
    target: dict,
    source: dict,
) -> None:
    target["total_records"] += int(
        source["total_records"]
    )
    target["completed_records"] += int(
        source["completed_records"]
    )
    target["draft_records"] += int(
        source["draft_records"]
    )

    for grade in (
        "A",
        "B",
        "C",
        "D",
    ):
        target["grades"][grade] += int(
            source["grades"][grade]
        )


def get_engineering_progress(
    project_id: int,
    survey_batch_id: int,
) -> dict:
    project_id = int(project_id)
    survey_batch_id = int(
        survey_batch_id
    )

    overall = _empty_summary()

    with get_connection() as connection:
        department_rows = (
            connection.execute(
                '''
                SELECT
                    id,
                    name,
                    sort_order
                FROM organization_units
                WHERE unit_type = 'department'
                  AND status = 'active'
                ORDER BY
                    sort_order,
                    id
                '''
            ).fetchall()
        )

        office_rows = (
            connection.execute(
                '''
                SELECT
                    department.id
                        AS department_id,
                    office.id
                        AS office_id,
                    office.name
                        AS office_name,
                    office.sort_order
                        AS office_sort_order,

                    COUNT(sr.id)
                        AS total_records,

                    SUM(
                        CASE
                            WHEN sr.record_status
                                = 'completed'
                            THEN 1
                            ELSE 0
                        END
                    )
                        AS completed_records,

                    SUM(
                        CASE
                            WHEN sr.record_status
                                = 'draft'
                            THEN 1
                            ELSE 0
                        END
                    )
                        AS draft_records,

                    SUM(
                        CASE
                            WHEN sr.record_status
                                = 'completed'
                             AND sr.overall_grade
                                = 'A'
                            THEN 1
                            ELSE 0
                        END
                    )
                        AS grade_a,

                    SUM(
                        CASE
                            WHEN sr.record_status
                                = 'completed'
                             AND sr.overall_grade
                                = 'B'
                            THEN 1
                            ELSE 0
                        END
                    )
                        AS grade_b,

                    SUM(
                        CASE
                            WHEN sr.record_status
                                = 'completed'
                             AND sr.overall_grade
                                = 'C'
                            THEN 1
                            ELSE 0
                        END
                    )
                        AS grade_c,

                    SUM(
                        CASE
                            WHEN sr.record_status
                                = 'completed'
                             AND sr.overall_grade
                                = 'D'
                            THEN 1
                            ELSE 0
                        END
                    )
                        AS grade_d

                FROM organization_units AS office

                JOIN organization_units
                    AS department
                  ON department.id
                    = office.parent_id
                 AND department.unit_type
                    = 'department'
                 AND department.status
                    = 'active'

                LEFT JOIN survey_records
                    AS sr
                  ON sr.organization_unit_id
                    = office.id
                 AND sr.project_id = ?
                 AND sr.survey_batch_id = ?
                 AND sr.record_type
                    = 'engineering'
                 AND sr.record_status
                    IN (
                        'draft',
                        'completed'
                    )

                WHERE office.unit_type
                    = 'water_office'
                  AND office.status
                    = 'active'

                GROUP BY
                    department.id,
                    office.id,
                    office.name,
                    office.sort_order

                ORDER BY
                    department.sort_order,
                    department.id,
                    office.sort_order,
                    office.id
                ''',
                (
                    project_id,
                    survey_batch_id,
                ),
            ).fetchall()
        )

    departments: dict[int, dict] = {}

    for row in department_rows:
        department_id = int(
            row["id"]
        )

        departments[
            department_id
        ] = {
            "department_id": (
                department_id
            ),
            "department_name": (
                str(row["name"])
            ),
            **_empty_summary(),
            "offices": [],
        }

    for row in office_rows:
        department_id = int(
            row["department_id"]
        )

        if department_id not in departments:
            continue

        office_summary = {
            "office_id": int(
                row["office_id"]
            ),
            "office_name": str(
                row["office_name"]
            ),
            "total_records": int(
                row["total_records"]
                or 0
            ),
            "completed_records": int(
                row["completed_records"]
                or 0
            ),
            "draft_records": int(
                row["draft_records"]
                or 0
            ),
            "completion_rate": None,
            "grades": {
                "A": int(
                    row["grade_a"]
                    or 0
                ),
                "B": int(
                    row["grade_b"]
                    or 0
                ),
                "C": int(
                    row["grade_c"]
                    or 0
                ),
                "D": int(
                    row["grade_d"]
                    or 0
                ),
            },
        }

        _finalize_summary(
            office_summary
        )

        department = departments[
            department_id
        ]

        department["offices"].append(
            office_summary
        )

        _accumulate(
            department,
            office_summary,
        )

        _accumulate(
            overall,
            office_summary,
        )

    result_departments = []

    for department in (
        departments.values()
    ):
        _finalize_summary(
            department
        )

        result_departments.append(
            department
        )

    _finalize_summary(
        overall
    )

    return {
        "project_id": project_id,
        "survey_batch_id": (
            survey_batch_id
        ),
        **overall,
        "departments": (
            result_departments
        ),
    }
