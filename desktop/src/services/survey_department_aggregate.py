from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import database

from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_task_workspace import (
    get_current_task_workspace,
)


@dataclass(frozen=True)
class DepartmentAggregatePreview:
    parent_task_uid: str
    project_id: int
    survey_batch_id: int
    survey_record_ids: tuple[int, ...]
    source_task_uids: tuple[str, ...]
    source_office_uids: tuple[str, ...]
    management_scope_uids: tuple[str, ...]

    @property
    def record_count(self):
        return len(
            self.survey_record_ids
        )

    @property
    def source_task_count(self):
        return len(
            self.source_task_uids
        )

    @property
    def source_office_count(self):
        return len(
            self.source_office_uids
        )

    @property
    def management_scope_count(self):
        return len(
            self.management_scope_uids
        )


def _clean_text(value):
    return str(
        value or ""
    ).strip()


def _require_text(
    value,
    field_name,
):
    text = _clean_text(
        value
    )

    if not text:
        raise ValueError(
            f"{field_name}不能为空。"
        )

    return text


def _load_department_workspace():
    workspace = (
        get_current_task_workspace()
    )

    if workspace is None:
        raise ValueError(
            "当前没有已接收的调查任务工作区。"
        )

    if (
        _clean_text(
            workspace.get(
                "target_unit_type"
            )
        )
        != "department"
    ):
        raise ValueError(
            "当前任务不是基层处父任务，"
            "不能生成处级汇总成果。"
        )

    parent_task_uid = _require_text(
        workspace.get(
            "task_uid"
        ),
        "父任务 task_uid",
    )

    root_task_uid = (
        _clean_text(
            workspace.get(
                "root_task_uid"
            )
        )
        or parent_task_uid
    )

    try:
        parent_depth = int(
            workspace.get(
                "task_depth"
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "父任务 task_depth 无效。"
        ) from error

    return (
        workspace,
        parent_task_uid,
        root_task_uid,
        parent_depth,
    )


def _parent_scope_map(
    workspace,
):
    result = {}

    for item in (
        workspace.get(
            "management_scopes"
        )
        or ()
    ):
        uid = _require_text(
            item.get(
                "management_scope_uid"
            ),
            "父任务 scope UID",
        )

        if uid in result:
            raise ValueError(
                "父任务工作区包含重复的 scope UID。"
            )

        result[
            uid
        ] = {
            "organization_unit_uid": (
                _require_text(
                    item.get(
                        "organization_unit_uid"
                    ),
                    "scope owner UID",
                )
            ),
            "canal_unit_uid": (
                _require_text(
                    item.get(
                        "canal_unit_uid"
                    ),
                    "scope canal UID",
                )
            ),
        }

    if not result:
        raise ValueError(
            "当前处级父任务没有冻结分管范围。"
        )

    return result


def _load_child_task_authority(
    connection,
    *,
    parent_task_uid,
    root_task_uid,
    expected_depth,
):
    rows = connection.execute(
        """
        SELECT
            id,
            task_uid,
            parent_task_uid,
            root_task_uid,
            task_depth,
            target_unit_type,
            organization_unit_uid
        FROM survey_task_issues
        WHERE parent_task_uid = ?
          AND root_task_uid = ?
          AND task_depth = ?
          AND target_unit_type =
            'water_office'
        ORDER BY id
        """,
        (
            parent_task_uid,
            root_task_uid,
            int(
                expected_depth
            ),
        ),
    ).fetchall()

    result = {}

    for row in rows:
        task_uid = _require_text(
            row[
                "task_uid"
            ],
            "child task UID",
        )

        scope_rows = (
            connection.execute(
                """
                SELECT
                    management_scope_uid,
                    canal_unit_uid,
                    organization_unit_uid
                FROM survey_task_issue_scopes
                WHERE task_issue_id = ?
                ORDER BY
                    sort_order,
                    id
                """,
                (
                    int(
                        row[
                            "id"
                        ]
                    ),
                ),
            ).fetchall()
        )

        result[
            task_uid
        ] = {
            "organization_unit_uid": (
                _require_text(
                    row[
                        "organization_unit_uid"
                    ],
                    "child task organization UID",
                )
            ),
            "scopes": {
                _require_text(
                    scope[
                        "management_scope_uid"
                    ],
                    "child scope UID",
                ): {
                    "organization_unit_uid": (
                        _require_text(
                            scope[
                                "organization_unit_uid"
                            ],
                            "child scope owner UID",
                        )
                    ),
                    "canal_unit_uid": (
                        _require_text(
                            scope[
                                "canal_unit_uid"
                            ],
                            "child scope canal UID",
                        )
                    ),
                }
                for scope in scope_rows
            },
        }

    return result


def preview_current_department_aggregate():
    (
        workspace,
        parent_task_uid,
        root_task_uid,
        parent_depth,
    ) = _load_department_workspace()

    parent_scopes = (
        _parent_scope_map(
            workspace
        )
    )

    parent_scope_uids = tuple(
        parent_scopes.keys()
    )

    placeholders = ",".join(
        "?"
        for _ in parent_scope_uids
    )

    project_id = int(
        workspace[
            "project_id"
        ]
    )
    batch_id = int(
        workspace[
            "survey_batch_id"
        ]
    )

    with database.get_connection() as connection:
        child_authority = (
            _load_child_task_authority(
                connection,
                parent_task_uid=(
                    parent_task_uid
                ),
                root_task_uid=(
                    root_task_uid
                ),
                expected_depth=(
                    parent_depth
                    + 1
                ),
            )
        )

        rows = connection.execute(
            f"""
            SELECT
                sr.id,
                sr.source_task_uid,
                sr.source_management_scope_uid,
                ou.organization_unit_uid,
                cu.canal_unit_uid
            FROM survey_records AS sr
            JOIN organization_units AS ou
              ON ou.id =
                sr.organization_unit_id
            JOIN canal_units AS cu
              ON cu.id =
                sr.canal_unit_id
            WHERE sr.project_id = ?
              AND sr.survey_batch_id = ?
              AND sr.record_status =
                'completed'
              AND
                sr.source_management_scope_uid
                IN ({placeholders})
            ORDER BY
                sr.id
            """,
            (
                project_id,
                batch_id,
                *parent_scope_uids,
            ),
        ).fetchall()

    record_ids = []
    source_task_uids = []
    source_office_uids = []
    used_scope_uids = []

    for row in rows:
        record_id = int(
            row[
                "id"
            ]
        )

        source_task_uid = (
            _require_text(
                row[
                    "source_task_uid"
                ],
                (
                    "调查记录 "
                    f"{record_id} source_task_uid"
                ),
            )
        )

        scope_uid = (
            _require_text(
                row[
                    "source_management_scope_uid"
                ],
                (
                    "调查记录 "
                    f"{record_id} scope UID"
                ),
            )
        )

        organization_uid = (
            _require_text(
                row[
                    "organization_unit_uid"
                ],
                (
                    "调查记录 "
                    f"{record_id} organization UID"
                ),
            )
        )

        canal_uid = (
            _require_text(
                row[
                    "canal_unit_uid"
                ],
                (
                    "调查记录 "
                    f"{record_id} canal UID"
                ),
            )
        )

        parent_scope = (
            parent_scopes.get(
                scope_uid
            )
        )

        if parent_scope is None:
            raise ValueError(
                "处级汇总发现超出父任务冻结范围的调查记录："
                f"record_id={record_id}。"
            )

        if (
            parent_scope[
                "organization_unit_uid"
            ]
            != organization_uid
        ):
            raise ValueError(
                "处级汇总发现调查记录管理单位"
                "与父任务冻结 scope owner 不一致："
                f"record_id={record_id}。"
            )

        if (
            parent_scope[
                "canal_unit_uid"
            ]
            != canal_uid
        ):
            raise ValueError(
                "处级汇总发现调查记录渠系"
                "与父任务冻结 scope 不一致："
                f"record_id={record_id}。"
            )

        if (
            source_task_uid
            != parent_task_uid
        ):
            child = (
                child_authority.get(
                    source_task_uid
                )
            )

            if child is None:
                raise ValueError(
                    "处级汇总发现不属于当前父任务"
                    "直接子任务的调查记录："
                    f"record_id={record_id}，"
                    f"source_task_uid={source_task_uid}。"
                )

            if (
                child[
                    "organization_unit_uid"
                ]
                != organization_uid
            ):
                raise ValueError(
                    "处级汇总发现调查记录管理单位"
                    "与子任务目标水管所不一致："
                    f"record_id={record_id}。"
                )

            child_scope = (
                child[
                    "scopes"
                ].get(
                    scope_uid
                )
            )

            if child_scope is None:
                raise ValueError(
                    "处级汇总发现调查记录 scope "
                    "不属于其来源子任务冻结范围："
                    f"record_id={record_id}。"
                )

            if (
                child_scope[
                    "organization_unit_uid"
                ]
                != organization_uid
                or child_scope[
                    "canal_unit_uid"
                ]
                != canal_uid
            ):
                raise ValueError(
                    "处级汇总发现调查记录与来源子任务"
                    "冻结 scope 快照不一致："
                    f"record_id={record_id}。"
                )

        record_ids.append(
            record_id
        )

        if (
            source_task_uid
            not in source_task_uids
        ):
            source_task_uids.append(
                source_task_uid
            )

        if (
            organization_uid
            not in source_office_uids
        ):
            source_office_uids.append(
                organization_uid
            )

        if (
            scope_uid
            not in used_scope_uids
        ):
            used_scope_uids.append(
                scope_uid
            )

    if not record_ids:
        raise ValueError(
            "当前处级父任务下没有可汇总的"
            "已完成调查记录。"
        )

    return DepartmentAggregatePreview(
        parent_task_uid=(
            parent_task_uid
        ),
        project_id=(
            project_id
        ),
        survey_batch_id=(
            batch_id
        ),
        survey_record_ids=tuple(
            record_ids
        ),
        source_task_uids=tuple(
            source_task_uids
        ),
        source_office_uids=tuple(
            source_office_uids
        ),
        management_scope_uids=tuple(
            used_scope_uids
        ),
    )


def export_current_department_aggregate_result_package(
    output_path,
    *,
    result_name="处级汇总成果",
    notes="",
):
    preview = (
        preview_current_department_aggregate()
    )

    result = (
        export_survey_result_package(
            SurveyResultExportRequest(
                project_id=(
                    preview.project_id
                ),
                survey_batch_id=(
                    preview.survey_batch_id
                ),
                survey_record_ids=(
                    preview.survey_record_ids
                ),
                output_path=Path(
                    output_path
                ),
                result_name=(
                    result_name
                ),
                notes=(
                    notes
                ),
                submission_task_uid=(
                    preview.parent_task_uid
                ),
            )
        )
    )

    return result
