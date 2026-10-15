"""Give synthetic source records the received workspace required for editing."""
import database
from services.survey_task_workspace import ensure_survey_task_workspace_schema


def receive_workspace_for_record(record_id):
    ensure_survey_task_workspace_schema()
    with database.get_connection() as connection:
        row = connection.execute("SELECT * FROM survey_records WHERE id=?", (record_id,)).fetchone()
        workspace = connection.execute(
            """INSERT INTO survey_task_workspaces
               (task_uid, source_package_uid, project_id, survey_batch_id, organization_unit_id,
                task_name, managed_package_relative_path, source_package_sha256, is_current)
               VALUES (?, ?, ?, ?, ?, '本机调查任务', 'task_packages/test.ydtask', ?, 0)""",
            (row["source_task_uid"], row["source_task_uid"] + "-package",
             row["project_id"], row["survey_batch_id"], row["organization_unit_id"], "a" * 64),
        )
        connection.execute(
            """INSERT INTO survey_task_workspace_scopes
               (task_workspace_id, management_scope_uid, canal_unit_id, canal_unit_uid,
                organization_unit_uid, canal_name_snapshot, canal_level_snapshot,
                range_mode, source_scope_status)
               SELECT ?, ?, cu.id, cu.canal_unit_uid, ou.organization_unit_uid,
                      cu.name, cu.canal_level, 'whole', 'active'
               FROM canal_units cu, organization_units ou WHERE cu.id=? AND ou.id=?""",
            (workspace.lastrowid, row["source_management_scope_uid"],
             row["canal_unit_id"], row["organization_unit_id"]),
        )
