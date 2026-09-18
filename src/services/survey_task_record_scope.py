from __future__ import annotations

import database

from services.survey_task_workspace import (
    ensure_survey_task_workspace_schema,
)


def ensure_survey_task_record_scope_schema():
    """
    将任务来源精确落实到 SurveyRecord。

    Stage 14.4.3：
    - source_task_uid 保存来源任务；
    - source_management_scope_uid 保存来源分管范围；
    - 当前任务新增记录必须精确属于一个 workspace scope；
    - 同一物理渠道有多个 scope 时必须显式选择；
    - 两个来源 UID 写入后不可修改；
    - 没有当前任务时保持集中录入行为。
    """
    with database.get_connection() as connection:
        connection.executescript(
            """
            DROP TRIGGER IF EXISTS
                trg_survey_records_task_scope_insert;
            DROP TRIGGER IF EXISTS
                trg_survey_records_task_source_insert;
            DROP TRIGGER IF EXISTS
                trg_survey_records_task_scope_update;
            DROP TRIGGER IF EXISTS
                trg_survey_records_source_task_uid_immutable;
            DROP TRIGGER IF EXISTS
                trg_survey_records_source_management_scope_uid_immutable;
            """
        )

    ensure_survey_task_workspace_schema()

    with database.get_connection() as connection:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(survey_records)"
            ).fetchall()
        }

        if "source_task_uid" not in columns:
            connection.execute(
                """
                ALTER TABLE survey_records
                ADD COLUMN source_task_uid TEXT
                """
            )

        if (
            "source_management_scope_uid"
            not in columns
        ):
            connection.execute(
                """
                ALTER TABLE survey_records
                ADD COLUMN
                    source_management_scope_uid TEXT
                """
            )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_survey_records_source_task_uid
            ON survey_records(
                source_task_uid,
                id
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_survey_records_source_scope_uid
            ON survey_records(
                source_task_uid,
                source_management_scope_uid,
                id
            )
            """
        )

        connection.executescript(
            """
            CREATE TRIGGER
                trg_survey_records_task_scope_insert
            BEFORE INSERT ON survey_records
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1
                FROM survey_task_workspaces
                WHERE is_current = 1
            )
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1
                        FROM survey_task_workspaces AS stw
                        WHERE stw.is_current = 1
                          AND stw.project_id
                              = NEW.project_id
                          AND stw.survey_batch_id
                              = NEW.survey_batch_id
                          AND stw.organization_unit_id
                              = NEW.organization_unit_id
                    )
                    THEN RAISE(
                        ABORT,
                        'survey record is outside current task context'
                    )
                END;

                SELECT CASE
                    WHEN
                        NEW.source_task_uid IS NOT NULL
                        AND trim(
                            NEW.source_task_uid
                        ) <> ''
                        AND NEW.source_task_uid
                            <> (
                                SELECT task_uid
                                FROM survey_task_workspaces
                                WHERE is_current = 1
                                LIMIT 1
                            )
                    THEN RAISE(
                        ABORT,
                        'survey record source task does not match current task'
                    )
                END;

                SELECT CASE
                    WHEN
                        NEW.source_management_scope_uid
                            IS NOT NULL
                        AND trim(
                            NEW.source_management_scope_uid
                        ) <> ''
                        AND NOT EXISTS (
                            SELECT 1
                            FROM survey_task_workspaces
                                AS stw
                            JOIN survey_task_workspace_scopes
                                AS stws
                              ON stws.task_workspace_id
                                = stw.id
                            WHERE stw.is_current = 1
                              AND stws.management_scope_uid
                                = NEW.source_management_scope_uid
                              AND stws.canal_unit_id
                                = NEW.canal_unit_id
                        )
                    THEN RAISE(
                        ABORT,
                        'survey record management scope does not match current task canal'
                    )
                END;

                SELECT CASE
                    WHEN
                        (
                            NEW.source_management_scope_uid
                                IS NULL
                            OR trim(
                                NEW.source_management_scope_uid
                            ) = ''
                        )
                        AND (
                            SELECT COUNT(*)
                            FROM survey_task_workspaces
                                AS stw
                            JOIN survey_task_workspace_scopes
                                AS stws
                              ON stws.task_workspace_id
                                = stw.id
                            WHERE stw.is_current = 1
                              AND stws.canal_unit_id
                                = NEW.canal_unit_id
                        ) <> 1
                    THEN RAISE(
                        ABORT,
                        'survey record management scope is required or ambiguous'
                    )
                END;
            END;

            CREATE TRIGGER
                trg_survey_records_task_source_insert
            AFTER INSERT ON survey_records
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1
                FROM survey_task_workspaces
                WHERE is_current = 1
            )
            BEGIN
                UPDATE survey_records
                SET
                    source_task_uid = CASE
                        WHEN
                            NEW.source_task_uid IS NULL
                            OR trim(
                                NEW.source_task_uid
                            ) = ''
                        THEN (
                            SELECT task_uid
                            FROM survey_task_workspaces
                            WHERE is_current = 1
                            LIMIT 1
                        )
                        ELSE NEW.source_task_uid
                    END,
                    source_management_scope_uid = CASE
                        WHEN
                            NEW.source_management_scope_uid
                                IS NULL
                            OR trim(
                                NEW.source_management_scope_uid
                            ) = ''
                        THEN (
                            SELECT
                                stws.management_scope_uid
                            FROM survey_task_workspaces
                                AS stw
                            JOIN survey_task_workspace_scopes
                                AS stws
                              ON stws.task_workspace_id
                                = stw.id
                            WHERE stw.is_current = 1
                              AND stws.canal_unit_id
                                = NEW.canal_unit_id
                            LIMIT 1
                        )
                        ELSE
                            NEW.source_management_scope_uid
                    END
                WHERE id = NEW.id;
            END;

            CREATE TRIGGER
                trg_survey_records_task_scope_update
            BEFORE UPDATE OF
                project_id,
                survey_batch_id,
                organization_unit_id,
                canal_unit_id
            ON survey_records
            FOR EACH ROW
            WHEN
                OLD.source_task_uid IS NOT NULL
                AND trim(
                    OLD.source_task_uid
                ) <> ''
            BEGIN
                SELECT CASE
                    WHEN
                        OLD.source_management_scope_uid
                            IS NULL
                        OR trim(
                            OLD.source_management_scope_uid
                        ) = ''
                    THEN RAISE(
                        ABORT,
                        'task sourced record has no management scope'
                    )
                END;

                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1
                        FROM survey_task_workspaces
                            AS stw
                        JOIN survey_task_workspace_scopes
                            AS stws
                          ON stws.task_workspace_id
                            = stw.id
                        WHERE stw.task_uid
                              = OLD.source_task_uid
                          AND stw.project_id
                              = NEW.project_id
                          AND stw.survey_batch_id
                              = NEW.survey_batch_id
                          AND stw.organization_unit_id
                              = NEW.organization_unit_id
                          AND stws.management_scope_uid
                              = OLD.source_management_scope_uid
                          AND stws.canal_unit_id
                              = NEW.canal_unit_id
                    )
                    THEN RAISE(
                        ABORT,
                        'task sourced record cannot leave assigned management scope'
                    )
                END;
            END;

            CREATE TRIGGER
                trg_survey_records_source_task_uid_immutable
            BEFORE UPDATE OF source_task_uid
            ON survey_records
            FOR EACH ROW
            WHEN
                OLD.source_task_uid IS NOT NULL
                AND trim(
                    OLD.source_task_uid
                ) <> ''
                AND OLD.source_task_uid
                    IS NOT NEW.source_task_uid
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'source_task_uid is immutable'
                );
            END;

            CREATE TRIGGER
                trg_survey_records_source_management_scope_uid_immutable
            BEFORE UPDATE OF source_management_scope_uid
            ON survey_records
            FOR EACH ROW
            WHEN
                OLD.source_management_scope_uid
                    IS NOT NULL
                AND trim(
                    OLD.source_management_scope_uid
                ) <> ''
                AND OLD.source_management_scope_uid
                    IS NOT NEW.source_management_scope_uid
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'source_management_scope_uid is immutable'
                );
            END;
            """
        )

    return {
        "ready": True,
        "source_task_uid_column": True,
        "source_management_scope_uid_column": True,
        "scope_guard": True,
        "exact_scope_guard": True,
        "workspace_scope_snapshot": True,
    }
