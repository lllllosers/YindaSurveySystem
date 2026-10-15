"""Reception facts only; existing/stale packages never advance change time."""
import database


def latest_record_changes():
    with database.get_connection() as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='survey_result_import_record_changes'"
        ).fetchone():
            return {}
        rows = connection.execute(
            """SELECT sr.id AS record_id, c.change_type, i.imported_at
               FROM survey_result_import_record_changes c
               JOIN survey_result_imports i ON i.id = c.result_import_id
               JOIN survey_records sr ON sr.survey_record_uid = c.survey_record_uid
               WHERE c.change_type IN ('new', 'updated')
               ORDER BY i.id, c.id"""
        ).fetchall()
    return {row["record_id"]: dict(row) for row in rows}


def change_label(change):
    if not change:
        return "历史已有"
    timestamp = str(change["imported_at"]).replace("T", " ")[5:16]
    label = "新接收" if change["change_type"] == "new" else "已更新"
    return f"{label} · {timestamp}"


def changed_record_ids(result_import_id):
    with database.get_connection() as connection:
        return {
            row["id"] for row in connection.execute(
                """SELECT sr.id FROM survey_result_import_record_changes c
                   JOIN survey_records sr ON sr.survey_record_uid = c.survey_record_uid
                   WHERE c.result_import_id = ? AND c.change_type IN ('new', 'updated')""",
                (result_import_id,),
            ).fetchall()
        }
