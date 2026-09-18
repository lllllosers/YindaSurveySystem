from __future__ import annotations

import database

from services.survey_task_workspace import (
    ensure_survey_task_workspace_schema,
)


def ensure_survey_task_record_scope_schema():
    """
    将“当前调查任务”落实到 SurveyRecord 层。

    规则：
    1. survey_records.source_task_uid 记录基层数据来源任务；
    2. 当前存在 task workspace 时，新建调查记录必须属于：
       - 同一项目；
       - 同一调查批次；
       - 同一管理单位；
       - 任务允许的渠系；
    3. 符合范围的新记录自动写入当前 task_uid；
    4. 已带 source_task_uid 的记录不能被修改到原任务范围之外；
    5. 没有当前任务时保持原有集中录入行为，不强制任务来源。

    约束落在数据库触发器层，而不是只依赖界面下拉框，
    避免未来出现其他入口绕过任务范围。
    """

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
            CREATE TRIGGER IF NOT EXISTS
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
                          AND stw.project_id = NEW.project_id
                          AND stw.survey_batch_id
                              = NEW.survey_batch_id
                          AND stw.organization_unit_id
                              = NEW.organization_unit_id
                          AND EXISTS (
                              SELECT 1
                              FROM survey_task_workspace_canals
                                  AS stwc
                              WHERE stwc.task_workspace_id
                                  = stw.id
                                AND stwc.canal_unit_id
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
                        AND trim(NEW.source_task_uid) <> ''
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

            CREATE TRIGGER IF NOT EXISTS
                trg_survey_records_task_source_insert
            AFTER INSERT ON survey_records
            FOR EACH ROW
            WHEN
                (
                    NEW.source_task_uid IS NULL
                    OR trim(NEW.source_task_uid) = ''
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

            CREATE TRIGGER IF NOT EXISTS
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
                AND trim(OLD.source_task_uid) <> ''
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
                              FROM survey_task_workspace_canals
                                  AS stwc
                              WHERE stwc.task_workspace_id
                                  = stw.id
                                AND stwc.canal_unit_id
                                  = NEW.canal_unit_id
                          )
                    )
                    THEN RAISE(
                        ABORT,
                        'task sourced record cannot leave assigned scope'
                    )
                END;
            END;

            CREATE TRIGGER IF NOT EXISTS
                trg_survey_records_source_task_uid_immutable
            BEFORE UPDATE OF source_task_uid
            ON survey_records
            FOR EACH ROW
            WHEN
                OLD.source_task_uid IS NOT NULL
                AND trim(OLD.source_task_uid) <> ''
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
    }
