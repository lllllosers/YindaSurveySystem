from __future__ import annotations

import sqlite3

import database

from services.survey_task_lineage import (
    normalize_task_lineage,
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


def _optional_text(
    value,
):
    text = _clean_text(
        value
    )
    return text or None


def ensure_survey_task_issue_history_schema():
    """
    建立上级端“已下发调查任务”权威冻结历史。

    这里保存的是任务生成/下发当时的事实，
    后续 current master data 如何调整都不能改写它。

    survey_task_issues：
        保存任务头部、项目/批次/组织的下发时快照。

    survey_task_issue_scopes：
        保存该任务实际授权的 CanalManagementScope 快照。

    两张表都禁止 UPDATE / DELETE。
    如需重新下发，应生成新的 task_uid，而不是修改历史。
    """

    with database.get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                survey_task_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    task_uid TEXT NOT NULL UNIQUE,
                    source_package_uid TEXT NOT NULL UNIQUE,
                    task_schema_version TEXT NOT NULL,
                    app_version TEXT NOT NULL,

                    project_uid TEXT NOT NULL,
                    project_name_snapshot TEXT NOT NULL,
                    project_short_name_snapshot TEXT,

                    survey_batch_uid TEXT NOT NULL,
                    batch_name_snapshot TEXT NOT NULL,
                    batch_code_snapshot TEXT NOT NULL,
                    batch_start_date_snapshot TEXT,
                    batch_end_date_snapshot TEXT,

                    department_uid TEXT NOT NULL,
                    department_name_snapshot TEXT NOT NULL,

                    organization_unit_uid TEXT NOT NULL,
                    organization_name_snapshot TEXT NOT NULL,

                    task_name TEXT NOT NULL,
                    notes TEXT,

                    selected_scope_count INTEGER NOT NULL
                        CHECK (selected_scope_count > 0),

                    task_created_at TEXT NOT NULL,
                    issued_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        )
                );

            CREATE TABLE IF NOT EXISTS
                survey_task_issue_scopes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    task_issue_id INTEGER NOT NULL,
                    management_scope_uid TEXT NOT NULL,

                    canal_unit_uid TEXT NOT NULL,
                    organization_unit_uid TEXT NOT NULL,

                    canal_name_snapshot TEXT NOT NULL,
                    canal_level_snapshot TEXT NOT NULL,

                    range_mode TEXT NOT NULL
                        CHECK (
                            range_mode IN (
                                'whole',
                                'segment_known',
                                'segment_unknown'
                            )
                        ),

                    start_stake_text TEXT,
                    start_stake_value REAL,
                    end_stake_text TEXT,
                    end_stake_value REAL,

                    sort_order INTEGER NOT NULL DEFAULT 0,

                    source_scope_status TEXT NOT NULL
                        CHECK (
                            source_scope_status IN (
                                'active',
                                'inactive'
                            )
                        ),

                    description TEXT,

                    FOREIGN KEY (task_issue_id)
                        REFERENCES survey_task_issues(id),

                    UNIQUE (
                        task_issue_id,
                        management_scope_uid
                    ),

                    CHECK (
                        (
                            range_mode = 'segment_known'
                            AND start_stake_value IS NOT NULL
                            AND end_stake_value IS NOT NULL
                            AND start_stake_value
                                <= end_stake_value
                        )
                        OR
                        (
                            range_mode IN (
                                'whole',
                                'segment_unknown'
                            )
                            AND start_stake_text IS NULL
                            AND start_stake_value IS NULL
                            AND end_stake_text IS NULL
                            AND end_stake_value IS NULL
                        )
                    )
                );

            CREATE INDEX IF NOT EXISTS
                idx_survey_task_issue_scopes_uid
            ON survey_task_issue_scopes(
                management_scope_uid,
                task_issue_id
            );

            CREATE INDEX IF NOT EXISTS
                idx_survey_task_issues_project_batch
            ON survey_task_issues(
                project_uid,
                survey_batch_uid,
                id
            );

            CREATE TRIGGER IF NOT EXISTS
                trg_survey_task_issues_immutable_update
            BEFORE UPDATE ON survey_task_issues
            FOR EACH ROW
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'issued survey task history is immutable'
                );
            END;

            CREATE TRIGGER IF NOT EXISTS
                trg_survey_task_issues_immutable_delete
            BEFORE DELETE ON survey_task_issues
            FOR EACH ROW
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'issued survey task history is immutable'
                );
            END;

            CREATE TRIGGER IF NOT EXISTS
                trg_survey_task_issue_scopes_immutable_update
            BEFORE UPDATE ON survey_task_issue_scopes
            FOR EACH ROW
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'issued survey task scope history is immutable'
                );
            END;

            CREATE TRIGGER IF NOT EXISTS
                trg_survey_task_issue_scopes_immutable_delete
            BEFORE DELETE ON survey_task_issue_scopes
            FOR EACH ROW
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'issued survey task scope history is immutable'
                );
            END;
            """
        )

        issue_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(survey_task_issues)"
            ).fetchall()
        }

        if "parent_task_uid" not in issue_columns:
            connection.execute(
                """
                ALTER TABLE survey_task_issues
                ADD COLUMN parent_task_uid TEXT
                """
            )

        if "root_task_uid" not in issue_columns:
            connection.execute(
                """
                ALTER TABLE survey_task_issues
                ADD COLUMN root_task_uid TEXT
                """
            )

        if "task_depth" not in issue_columns:
            connection.execute(
                """
                ALTER TABLE survey_task_issues
                ADD COLUMN task_depth INTEGER NOT NULL DEFAULT 0
                """
            )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_survey_task_issues_root
            ON survey_task_issues(
                root_task_uid,
                task_depth,
                id
            )
            """
        )

    return {
        "ready": True,
        "issue_table": True,
        "scope_snapshot_table": True,
        "immutable": True,
        "lineage_fields": True,
    }


def _validate_scope_snapshot(
    item,
    *,
    expected_organization_uid,
    canal_by_uid,
):
    management_scope_uid = _require_text(
        item.get(
            "management_scope_uid"
        ),
        "management_scope_uid",
    )
    canal_unit_uid = _require_text(
        item.get(
            "canal_uid"
        ),
        "canal_uid",
    )
    organization_unit_uid = _require_text(
        item.get(
            "organization_unit_uid"
        ),
        "organization_unit_uid",
    )

    canal_reference = canal_by_uid.get(
        canal_unit_uid
    )

    if canal_reference is None:
        raise ValueError(
            "任务分管范围引用的物理渠系"
            "不在冻结 canal reference 中："
            f"{canal_unit_uid}。"
        )

    if (
        organization_unit_uid
        != expected_organization_uid
    ):
        raise ValueError(
            "任务分管范围管理单位与任务 assignment 不一致："
            f"{management_scope_uid}。"
        )

    range_mode = _require_text(
        item.get(
            "range_mode"
        ),
        "range_mode",
    )

    if range_mode not in {
        "whole",
        "segment_known",
        "segment_unknown",
    }:
        raise ValueError(
            "任务分管范围包含无效 range_mode："
            f"{management_scope_uid}。"
        )

    start_text = item.get(
        "start_stake_text"
    )
    start_value = item.get(
        "start_stake_value"
    )
    end_text = item.get(
        "end_stake_text"
    )
    end_value = item.get(
        "end_stake_value"
    )

    if range_mode == "segment_known":
        if (
            start_value is None
            or end_value is None
        ):
            raise ValueError(
                "segment_known 下发快照缺少起止桩号数值。"
            )

        if float(
            start_value
        ) > float(
            end_value
        ):
            raise ValueError(
                "segment_known 下发快照起始桩号大于终止桩号。"
            )

    else:
        if any(
            value is not None
            for value in (
                start_text,
                start_value,
                end_text,
                end_value,
            )
        ):
            raise ValueError(
                "whole / segment_unknown 下发快照"
                "不能携带起止桩号。"
            )

    return {
        "management_scope_uid": (
            management_scope_uid
        ),
        "canal_unit_uid": (
            canal_unit_uid
        ),
        "organization_unit_uid": (
            organization_unit_uid
        ),
        "canal_name_snapshot": (
            _require_text(
                canal_reference.get(
                    "name"
                ),
                "canal reference name",
            )
        ),
        "canal_level_snapshot": (
            _require_text(
                canal_reference.get(
                    "canal_level"
                ),
                "canal reference canal_level",
            )
        ),
        "range_mode": (
            range_mode
        ),
        "start_stake_text": (
            start_text
        ),
        "start_stake_value": (
            start_value
        ),
        "end_stake_text": (
            end_text
        ),
        "end_stake_value": (
            end_value
        ),
        "sort_order": int(
            item.get(
                "sort_order"
            )
            or 0
        ),
        "source_scope_status": (
            _require_text(
                item.get(
                    "status"
                ),
                "status",
            )
        ),
        "description": (
            _optional_text(
                item.get(
                    "description"
                )
            )
        ),
    }


def record_issued_survey_task(
    *,
    package_uid,
    manifest,
    task_document,
    management_scopes,
    canal_units,
):
    """
    将已经成功生成的 .ydtask 内容保存为上级端权威历史。

    记录内容直接取自即将/已经写入任务包的冻结文档，
    不重新查询 current CanalManagementScope，
    避免“包内容”和“上级验收依据”产生双源事实。
    """

    ensure_survey_task_issue_history_schema()

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "manifest 必须是对象。"
        )

    if not isinstance(
        task_document,
        dict,
    ):
        raise ValueError(
            "task_document 必须是对象。"
        )

    task_uid = _require_text(
        task_document.get(
            "task_uid"
        ),
        "task_uid",
    )
    manifest_task_uid = _require_text(
        manifest.get(
            "task_uid"
        ),
        "manifest.task_uid",
    )

    if (
        task_uid
        != manifest_task_uid
    ):
        raise ValueError(
            "manifest 与 task.json 的 task_uid 不一致。"
        )

    package_uid = _require_text(
        package_uid,
        "package_uid",
    )

    task_schema_version = _require_text(
        task_document.get(
            "task_schema_version"
        ),
        "task_schema_version",
    )
    manifest_schema_version = _require_text(
        manifest.get(
            "task_schema_version"
        ),
        "manifest.task_schema_version",
    )

    if (
        task_schema_version
        != manifest_schema_version
    ):
        raise ValueError(
            "manifest 与 task.json 的 task_schema_version 不一致。"
        )

    lineage = normalize_task_lineage(
        task_document,
        manifest=manifest,
    )

    app_version = _require_text(
        manifest.get(
            "app_version"
        ),
        "manifest.app_version",
    )

    project = task_document.get(
        "project"
    )
    batch = task_document.get(
        "survey_batch"
    )
    assignment = task_document.get(
        "assignment"
    )
    scope_contract = task_document.get(
        "scope"
    )

    if not isinstance(
        project,
        dict,
    ):
        raise ValueError(
            "task.project 必须是对象。"
        )

    if not isinstance(
        batch,
        dict,
    ):
        raise ValueError(
            "task.survey_batch 必须是对象。"
        )

    if not isinstance(
        assignment,
        dict,
    ):
        raise ValueError(
            "task.assignment 必须是对象。"
        )

    if not isinstance(
        scope_contract,
        dict,
    ):
        raise ValueError(
            "task.scope 必须是对象。"
        )

    project_uid = _require_text(
        project.get(
            "project_uid"
        ),
        "project_uid",
    )
    batch_uid = _require_text(
        batch.get(
            "survey_batch_uid"
        ),
        "survey_batch_uid",
    )
    department_uid = _require_text(
        assignment.get(
            "department_uid"
        ),
        "department_uid",
    )
    organization_uid = _require_text(
        assignment.get(
            "organization_unit_uid"
        ),
        "organization_unit_uid",
    )

    if (
        _require_text(
            manifest.get(
                "project_uid"
            ),
            "manifest.project_uid",
        )
        != project_uid
    ):
        raise ValueError(
            "manifest 与 task.json 的 project_uid 不一致。"
        )

    if (
        _require_text(
            manifest.get(
                "survey_batch_uid"
            ),
            "manifest.survey_batch_uid",
        )
        != batch_uid
    ):
        raise ValueError(
            "manifest 与 task.json 的 survey_batch_uid 不一致。"
        )

    selected_uids = (
        scope_contract.get(
            "selected_management_scope_uids"
        )
    )

    if (
        not isinstance(
            selected_uids,
            list,
        )
        or not selected_uids
    ):
        raise ValueError(
            "任务必须包含已选择的 management scope UID。"
        )

    selected_uids = [
        _require_text(
            value,
            "selected_management_scope_uid",
        )
        for value in selected_uids
    ]

    if (
        len(
            selected_uids
        )
        != len(
            set(
                selected_uids
            )
        )
    ):
        raise ValueError(
            "任务包含重复的 management scope UID。"
        )

    declared_count = scope_contract.get(
        "selected_management_scope_count"
    )

    if (
        not isinstance(
            declared_count,
            int,
        )
        or isinstance(
            declared_count,
            bool,
        )
        or declared_count
        != len(
            selected_uids
        )
    ):
        raise ValueError(
            "任务 management scope 计数与 UID 集合不一致。"
        )

    raw_canals = list(
        canal_units
        or ()
    )

    canal_by_uid = {}

    for item in raw_canals:
        if not isinstance(
            item,
            dict,
        ):
            raise ValueError(
                "任务冻结 canal reference 项必须是对象。"
            )

        canal_uid = _require_text(
            item.get(
                "canal_uid"
            ),
            "canal_uid",
        )

        if canal_uid in canal_by_uid:
            raise ValueError(
                "任务冻结 canal reference "
                "包含重复 canal_uid："
                f"{canal_uid}。"
            )

        canal_by_uid[
            canal_uid
        ] = item

    raw_scopes = list(
        management_scopes
        or ()
    )

    snapshots = [
        _validate_scope_snapshot(
            item,
            expected_organization_uid=(
                organization_uid
            ),
            canal_by_uid=(
                canal_by_uid
            ),
        )
        for item in raw_scopes
    ]

    snapshot_uids = [
        item[
            "management_scope_uid"
        ]
        for item in snapshots
    ]

    if (
        set(
            snapshot_uids
        )
        != set(
            selected_uids
        )
        or len(
            snapshot_uids
        )
        != len(
            selected_uids
        )
    ):
        raise ValueError(
            "任务 scope UID 集合与冻结 scope 快照不一致。"
        )

    with database.get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO survey_task_issues (
                task_uid,
                source_package_uid,
                task_schema_version,
                app_version,
                parent_task_uid,
                root_task_uid,
                task_depth,

                project_uid,
                project_name_snapshot,
                project_short_name_snapshot,

                survey_batch_uid,
                batch_name_snapshot,
                batch_code_snapshot,
                batch_start_date_snapshot,
                batch_end_date_snapshot,

                department_uid,
                department_name_snapshot,

                organization_unit_uid,
                organization_name_snapshot,

                task_name,
                notes,
                selected_scope_count,
                task_created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                task_uid,
                package_uid,
                task_schema_version,
                app_version,
                lineage.parent_task_uid,
                lineage.root_task_uid,
                lineage.depth,

                project_uid,
                _require_text(
                    project.get(
                        "name"
                    ),
                    "project.name",
                ),
                _optional_text(
                    project.get(
                        "short_name"
                    )
                ),

                batch_uid,
                _require_text(
                    batch.get(
                        "batch_name"
                    ),
                    "survey_batch.batch_name",
                ),
                _require_text(
                    batch.get(
                        "batch_code"
                    ),
                    "survey_batch.batch_code",
                ),
                _optional_text(
                    batch.get(
                        "start_date"
                    )
                ),
                _optional_text(
                    batch.get(
                        "end_date"
                    )
                ),

                department_uid,
                _require_text(
                    assignment.get(
                        "department_name"
                    ),
                    "assignment.department_name",
                ),

                organization_uid,
                _require_text(
                    assignment.get(
                        "organization_name"
                    ),
                    "assignment.organization_name",
                ),

                _require_text(
                    task_document.get(
                        "task_name"
                    ),
                    "task_name",
                ),
                _optional_text(
                    task_document.get(
                        "notes"
                    )
                ),
                len(
                    snapshots
                ),
                _require_text(
                    task_document.get(
                        "created_at"
                    ),
                    "task.created_at",
                ),
            ),
        )

        task_issue_id = int(
            cursor.lastrowid
        )

        for item in snapshots:
            connection.execute(
                """
                INSERT INTO survey_task_issue_scopes (
                    task_issue_id,
                    management_scope_uid,
                    canal_unit_uid,
                    organization_unit_uid,
                    canal_name_snapshot,
                    canal_level_snapshot,
                    range_mode,
                    start_stake_text,
                    start_stake_value,
                    end_stake_text,
                    end_stake_value,
                    sort_order,
                    source_scope_status,
                    description
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    task_issue_id,
                    item[
                        "management_scope_uid"
                    ],
                    item[
                        "canal_unit_uid"
                    ],
                    item[
                        "organization_unit_uid"
                    ],
                    item[
                        "canal_name_snapshot"
                    ],
                    item[
                        "canal_level_snapshot"
                    ],
                    item[
                        "range_mode"
                    ],
                    item[
                        "start_stake_text"
                    ],
                    item[
                        "start_stake_value"
                    ],
                    item[
                        "end_stake_text"
                    ],
                    item[
                        "end_stake_value"
                    ],
                    item[
                        "sort_order"
                    ],
                    item[
                        "source_scope_status"
                    ],
                    item[
                        "description"
                    ],
                ),
            )

    return {
        "task_issue_id": (
            task_issue_id
        ),
        "task_uid": (
            task_uid
        ),
        "package_uid": (
            package_uid
        ),
        "parent_task_uid": (
            lineage.parent_task_uid
        ),
        "root_task_uid": (
            lineage.root_task_uid
        ),
        "task_depth": lineage.depth,
        "selected_management_scope_count": (
            len(
                snapshots
            )
        ),
    }


def _issue_row_to_dict(
    row,
):
    return {
        key: row[
            key
        ]
        for key in row.keys()
    }


def get_issued_survey_task(
    task_uid,
):
    """
    按 task_uid 读取上级端权威下发历史。

    返回的 management_scopes 只来自冻结历史表，
    不读取 current CanalManagementScope。
    """

    ensure_survey_task_issue_history_schema()

    task_uid = _require_text(
        task_uid,
        "task_uid",
    )

    with database.get_connection() as connection:
        issue = connection.execute(
            """
            SELECT *
            FROM survey_task_issues
            WHERE task_uid = ?
            LIMIT 1
            """,
            (
                task_uid,
            ),
        ).fetchone()

        if issue is None:
            return None

        scopes = connection.execute(
            """
            SELECT
                management_scope_uid,
                canal_unit_uid,
                organization_unit_uid,
                canal_name_snapshot,
                canal_level_snapshot,
                range_mode,
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                sort_order,
                source_scope_status,
                description
            FROM survey_task_issue_scopes
            WHERE task_issue_id = ?
            ORDER BY
                sort_order,
                id
            """,
            (
                issue[
                    "id"
                ],
            ),
        ).fetchall()

    result = _issue_row_to_dict(
        issue
    )

    if not _clean_text(
        result.get("root_task_uid")
    ):
        result["root_task_uid"] = result[
            "task_uid"
        ]
        result["parent_task_uid"] = None
        result["task_depth"] = 0

    result[
        "management_scopes"
    ] = tuple(
        _issue_row_to_dict(
            row
        )
        for row in scopes
    )

    return result


def get_issued_task_scope_snapshot(
    task_uid,
    management_scope_uid,
):
    """
    按 task_uid + management_scope_uid
    读取上级端下发时冻结的精确 scope 快照。
    """

    ensure_survey_task_issue_history_schema()

    task_uid = _require_text(
        task_uid,
        "task_uid",
    )
    management_scope_uid = _require_text(
        management_scope_uid,
        "management_scope_uid",
    )

    with database.get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                sti.task_uid,
                sti.project_uid,
                sti.survey_batch_uid,
                sti.department_uid,
                sti.organization_unit_uid
                    AS task_organization_unit_uid,

                stis.management_scope_uid,
                stis.canal_unit_uid,
                stis.organization_unit_uid,
                stis.canal_name_snapshot,
                stis.canal_level_snapshot,
                stis.range_mode,
                stis.start_stake_text,
                stis.start_stake_value,
                stis.end_stake_text,
                stis.end_stake_value,
                stis.sort_order,
                stis.source_scope_status,
                stis.description

            FROM survey_task_issues AS sti
            JOIN survey_task_issue_scopes AS stis
              ON stis.task_issue_id = sti.id

            WHERE sti.task_uid = ?
              AND stis.management_scope_uid = ?
            LIMIT 1
            """,
            (
                task_uid,
                management_scope_uid,
            ),
        ).fetchone()

    if row is None:
        return None

    return _issue_row_to_dict(
        row
    )
