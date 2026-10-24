"""Local task workspaces, rather than task provenance alone, grant editing."""
from contextlib import nullcontext

import database

READ_ONLY_MESSAGE = (
    "该记录为下级提交成果，仅供查看。如需修改，请由原调查单位修正后重新提交成果包。"
)


def is_survey_record_locally_editable(survey_record_id, *, connection=None):
    if survey_record_id is None:
        return True
    with (nullcontext(connection) if connection is not None else database.get_connection()) as conn:
        record = conn.execute(
            "SELECT source_task_uid, source_management_scope_uid, project_id, survey_batch_id, "
            "organization_unit_id, canal_unit_id FROM survey_records WHERE id = ?",
            (survey_record_id,),
        ).fetchone()
        if record is None:
            raise ValueError("没有找到该调查记录。")
        if not str(record["source_task_uid"] or "").strip():
            return True
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='survey_task_workspaces'"
        ).fetchone():
            return False
        return conn.execute(
            """SELECT 1 FROM survey_task_workspaces w
               JOIN survey_task_workspace_scopes s ON s.task_workspace_id = w.id
               JOIN organization_units o ON o.organization_unit_uid = s.organization_unit_uid
               WHERE w.task_uid = ? AND w.project_id = ? AND w.survey_batch_id = ?
                 AND o.id = ? AND s.management_scope_uid = ?
                 AND s.canal_unit_id = ? LIMIT 1""",
            (record["source_task_uid"], record["project_id"], record["survey_batch_id"],
             record["organization_unit_id"], record["source_management_scope_uid"],
             record["canal_unit_id"]),
        ).fetchone() is not None


def require_survey_record_editable(survey_record_id, *, connection=None):
    if not is_survey_record_locally_editable(survey_record_id, connection=connection):
        raise ValueError(READ_ONLY_MESSAGE)


def bump_survey_media_revision(connection, survey_record_id):
    connection.execute(
        """UPDATE survey_records SET revision_no = revision_no + 1,
           updated_at = datetime('now', 'localtime') WHERE id = ?""",
        (survey_record_id,),
    )
