from __future__ import annotations

import database

from services.survey_task_workspace import (
    ensure_survey_task_workspace_schema,
)


def ensure_survey_task_record_scope_schema():
    """
    Stage 14.4.2 过渡约束：

    workspace 的任务权限事实已经切换到
    survey_task_workspace_scopes。

    本阶段 SurveyRecord 尚只有 source_task_uid，
    因而数据库先按“任务 scope 所映射的 CanalUnit”
    约束新增/修改。Stage 14.4.3 再增加
    source_management_scope_uid，将记录精确绑定到
    某一个分管段。
    """
    # 先移除可能仍引用旧 workspace_canals 的触发器，
    # 再允许 workspace schema 删除测试阶段旧表。
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
                          AND EXISTS (
                              SELECT 1
                              FROM survey_task_workspace_scopes
                                  AS stws
                              WHERE stws.task_workspace_id
                                  = stw.id
                                AND stws.canal_unit_id
                                  = NEW.canal_unit_id
                          )
                    )
                    THEN RAISE(
                        ABORT,
                        'survey record is outside current task scope'
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
            END;

            CREATE TRIGGER
                trg_survey_records_task_source_insert
            AFTER INSERT ON survey_records
            FOR EACH ROW
            WHEN
                (
                    NEW.source_task_uid IS NULL
                    OR trim(
                        NEW.source_task_uid
                    ) = ''
                )
                AND EXISTS (
                    SELECT 1
                    FROM survey_task_workspaces
                    WHERE is_current = 1
                )
            BEGIN
                UPDATE survey_records
                SET source_task_uid = (
                    SELECT task_uid
                    FROM survey_task_workspaces
                    WHERE is_current = 1
                    LIMIT 1
                )
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
                    WHEN NOT EXISTS (
                        SELECT 1
                        FROM survey_task_workspaces AS stw
                        WHERE stw.task_uid
                              = OLD.source_task_uid
                          AND stw.project_id
                              = NEW.project_id
                          AND stw.survey_batch_id
                              = NEW.survey_batch_id
                          AND stw.organization_unit_id
                              = NEW.organization_unit_id
                          AND EXISTS (
                              SELECT 1
                              FROM survey_task_workspace_scopes
                                  AS stws
                              WHERE stws.task_workspace_id
                                  = stw.id
                                AND stws.canal_unit_id
                                  = NEW.canal_unit_id
                          )
                    )
                    THEN RAISE(
                        ABORT,
                        'task sourced record cannot leave assigned scope'
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
            """
        )

    return {
        "ready": True,
        "source_task_uid_column": True,
        "scope_guard": True,
        "workspace_scope_snapshot": True,
    }
