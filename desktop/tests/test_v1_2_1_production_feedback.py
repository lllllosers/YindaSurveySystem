"""Bounded production regression coverage using isolated source/target databases."""
from collections import Counter
import hashlib
import os
import zipfile
from unittest.mock import patch

import pytest

import database
from services.application_bootstrap import initialize_application_database
from services.survey_media import import_survey_media, update_media_metadata, delete_survey_media, get_survey_media
from services.survey_record_editability import is_survey_record_locally_editable
from services.survey_result_import import import_survey_result_package
from services.survey_result_import_preflight import preflight_survey_result_import
from services.survey_result_changes import latest_record_changes, changed_record_ids
from shared.protocol.stake import parse_stake
import tests.test_v1_0_2_incremental_revision_merge as merge_fixture
import tests.test_v1_0_2_engineering_numbering_finalization as numbering_fixture


@pytest.mark.parametrize("value,text,numeric", [
    ("CH12+350", "CH12+350.000", 12350.0),
    ("12+350", "CH12+350.000", 12350.0),
    ("CH12+350.5", "CH12+350.500", 12350.5),
    ("CH12+350.5678", "CH12+350.568", 12350.568),
    ("12350.5678", "CH12+350.568", 12350.568),
    ("CH12+999.9995", "CH13+000.000", 13000.0),
])
def test_stake_precision(value, text, numeric):
    assert parse_stake(value) == (text, numeric)


@pytest.fixture
def flow():
    case = merge_fixture.V102IncrementalRevisionMergeTestCase()
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()


def counts(import_id=None):
    with database.get_connection() as connection:
        if import_id is None:
            import_id = connection.execute("SELECT MAX(id) FROM survey_result_imports").fetchone()[0]
        rows = connection.execute(
            "SELECT change_type FROM survey_result_import_record_changes WHERE result_import_id=?", (import_id,)
        ).fetchall()
    return Counter(row[0] for row in rows)


@pytest.mark.parametrize("revised", [0, 3])
def test_cumulative_50_to_150_and_change_times(flow, revised):
    base = flow.base
    ids = [base.source_record_id] + [flow._create_source_record(n) for n in range(2, 51)]
    day1 = flow._export_source(ids, "day1.ydresult")
    base._use_target()
    import_survey_result_package(day1)
    assert counts() == {"new": 50}
    with database.get_connection() as connection:
        connection.execute("UPDATE survey_result_imports SET imported_at='2026-10-14 09:20:00'")
    before = latest_record_changes()
    ids += [flow._create_source_record(n) for n in range(51, 151)]
    base._use_source()
    with database.get_connection() as connection:
        for record_id in ids[:revised]:
            connection.execute(
                "UPDATE survey_records SET revision_no=revision_no+1, survey_comment='下级修正' WHERE id=?", (record_id,)
            )
    day2 = flow._export_source(ids, "day2.ydresult")
    base._use_target()
    import_survey_result_package(day2, accept_updates=True)
    expected = Counter(new=100, existing=50-revised)
    if revised:
        expected["updated"] = revised
    assert counts() == expected
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM survey_records").fetchone()[0] == 150
        import_id = connection.execute("SELECT MAX(id) FROM survey_result_imports").fetchone()[0]
    assert len(changed_record_ids(import_id)) == 100 + revised
    after = latest_record_changes()
    for record_id in sorted(before)[revised:]:
        assert after[record_id] == before[record_id]


def test_imported_read_only_and_local_workspace_editable(flow):
    base = flow.base
    base._use_source()
    assert is_survey_record_locally_editable(base.source_record_id)
    media = get_survey_media(base.source_record_id)[0]
    update_media_metadata(media["id"], media_role="overview", notes="本机可修改")
    fresh = flow._export_source([base.source_record_id], "local.ydresult")
    base._use_target()
    import_survey_result_package(fresh)
    with database.get_connection() as connection:
        record_id = connection.execute("SELECT id FROM survey_records").fetchone()[0]
        form_code = connection.execute("SELECT form_code FROM form_definitions WHERE id=(SELECT form_definition_id FROM form_versions WHERE id=?)", (base.form_version_id,)).fetchone()[0]
    assert not is_survey_record_locally_editable(record_id)
    for operation in (
        lambda: database.update_range_engineering_survey(record_id, form_code, "修改", {}),
        lambda: database.update_point_engineering_survey(record_id, form_code, "修改", {}),
        lambda: database.delete_engineering_survey_record(record_id, form_code),
        lambda: database.complete_engineering_survey_record(record_id, form_code, "range", ["A01"], ["B"]),
        lambda: import_survey_media(survey_record_id=record_id, source_file=base.temp_root/"source_photo.jpg"),
        lambda: update_media_metadata(get_survey_media(record_id)[0]["id"], media_role="other"),
        lambda: delete_survey_media(get_survey_media(record_id)[0]["id"]),
    ):
        with pytest.raises(ValueError, match="仅供查看"):
            operation()


def test_media_mutations_bump_parent_only(flow):
    base = flow.base
    base._use_source()
    def revision():
        with database.get_connection() as connection:
            return tuple(connection.execute("SELECT revision_no, source_revision_no FROM survey_records WHERE id=?", (base.source_record_id,)).fetchone())
    initial, source = revision()
    photo = base.temp_root / "extra.jpg"
    photo.write_bytes(b"new image")
    result = import_survey_media(survey_record_id=base.source_record_id, source_file=photo)
    assert revision() == (initial+1, source)
    update_media_metadata(result["media_id"], media_role="other", notes="metadata change")
    assert revision() == (initial+2, source)
    delete_survey_media(result["media_id"])
    assert revision() == (initial+3, source)


def test_authoritative_media_legacy_hash_change_and_stale(flow):
    base = flow.base
    base._use_source()
    b = base.temp_root / "b.jpg"
    b.write_bytes(b"photo B")
    old_b = import_survey_media(survey_record_id=base.source_record_id, source_file=b)
    old = flow._export_source([base.source_record_id], "old.ydresult")
    base._use_target()
    import_survey_result_package(old)
    base._use_source()
    a = get_survey_media(base.source_record_id)[0]
    delete_survey_media(old_b["media_id"])
    a["absolute_path"].write_bytes(b"changed photo A")
    with database.get_connection() as connection:
        connection.execute("UPDATE survey_media SET file_sha256=?,file_size=? WHERE id=?",
                           (hashlib.sha256(b"changed photo A").hexdigest(),len(b"changed photo A"),a["id"]))
    c = base.temp_root / "c.jpg"
    c.write_bytes(b"photo C")
    new_c = import_survey_media(survey_record_id=base.source_record_id, source_file=c)
    # Emulate V1.2.0 media edits without a parent revision bump.
    with database.get_connection() as connection:
        old_revision = 2
        connection.execute("UPDATE survey_records SET revision_no=? WHERE id=?", (old_revision,base.source_record_id))
    current = flow._export_source([base.source_record_id], "current.ydresult")
    base._use_target()
    report = preflight_survey_result_import(current)
    assert report.can_import, report.format_text()
    import_survey_result_package(current, accept_updates=True)
    media = get_survey_media(1)
    assert {m["media_uid"] for m in media} == {a["media_uid"], new_c["media_uid"]}
    assert next(m for m in media if m["media_uid"] == a["media_uid"])["absolute_path"].read_bytes() == b"changed photo A"
    base._use_source()
    with database.get_connection() as connection:
        connection.execute("UPDATE survey_records SET revision_no=revision_no+1 WHERE id=?", (base.source_record_id,))
    newer = flow._export_source([base.source_record_id], "newer.ydresult")
    base._use_target()
    import_survey_result_package(newer, accept_updates=True)
    # A distinct old package must be classified stale rather than bypassed as already imported.
    base._use_source()
    delete_survey_media(new_c["media_id"])
    import_survey_media(survey_record_id=base.source_record_id, source_file=b)
    with database.get_connection() as connection:
        connection.execute("UPDATE survey_records SET revision_no=2 WHERE id=?", (base.source_record_id,))
    stale = flow._export_source([base.source_record_id], "stale.ydresult")
    base._use_target()
    report = preflight_survey_result_import(stale)
    assert report.new_media == 0
    import_survey_result_package(stale)
    assert counts() == {"stale": 1}
    assert {m["media_uid"] for m in get_survey_media(1)} == {a["media_uid"],new_c["media_uid"]}


def test_replacement_failure_restores_files_and_no_details(flow):
    base = flow.base
    base._use_target()
    import_survey_result_package(base.package_path)
    original = get_survey_media(1)[0]
    original_bytes = original["absolute_path"].read_bytes()
    base._use_source()
    update_media_metadata(get_survey_media(base.source_record_id)[0]["id"],media_role="other",notes="changed")
    revised = flow._export_source([base.source_record_id],"failure.ydresult")
    base._use_target()
    with database.get_connection() as connection:
        before = connection.execute("SELECT COUNT(*) FROM survey_result_import_record_changes").fetchone()[0]
    with patch("services.survey_result_import._insert_media",side_effect=RuntimeError("injected failure")):
        with pytest.raises(RuntimeError,match="injected"):
            import_survey_result_package(revised,accept_updates=True)
    assert original["absolute_path"].read_bytes() == original_bytes
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM survey_result_import_record_changes").fetchone()[0] == before


def test_valid_package_repairs_missing_or_corrupt_target(flow):
    base = flow.base
    base._use_target()
    import_survey_result_package(base.package_path)
    original = get_survey_media(1)[0]
    original["absolute_path"].write_bytes(b"corrupt")
    package = flow._export_source([base.source_record_id], "repair.ydresult")
    base._use_target()
    import_survey_result_package(package)
    assert original["absolute_path"].read_bytes() == b"stage-12-7-media"
    assert counts() == {"existing": 1}


def test_media_uid_different_record_still_blocks(flow):
    base = flow.base
    second = flow._create_source_record(2)
    package = flow._export_source([base.source_record_id, second], "identity.ydresult")
    base._use_target()
    import_survey_result_package(package)
    with database.get_connection() as connection:
        connection.execute("UPDATE survey_media SET survey_record_id=2")
    report = preflight_survey_result_import(package)
    assert not report.can_import
    assert any(issue.code == "MEDIA_UID_CONFLICT" for issue in report.issues)


def test_package_internal_binary_hash_still_blocks(flow):
    base = flow.base
    broken = base.temp_root / "broken.ydresult"
    with zipfile.ZipFile(base.package_path) as source, zipfile.ZipFile(broken,"w") as target:
        for entry in source.infolist():
            data = source.read(entry.filename)
            target.writestr(entry, b"tampered" if entry.filename.startswith("media/") else data)
    from services.survey_result_package_reader import load_survey_result_package
    with pytest.raises(ValueError):
        load_survey_result_package(broken)


def test_read_only_ui_and_numeric_table_sorting(flow):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QPushButton
    from forms.engineering.registry import get_engineering_form_definition
    from pages.components.generic_engineering_survey_page import GenericEngineeringSurveyPage
    from pages.components.survey_media_dialog import SurveyMediaDialog
    from pages.components.stake_table_item import StakeTableItem
    from pages.data_query_page import DataQueryPage
    app = QApplication.instance() or QApplication([])
    base = flow.base
    base._use_target()
    import_survey_result_package(base.package_path)
    with database.get_connection() as connection:
        form = connection.execute(
            "SELECT fd.form_code FROM survey_records sr JOIN form_versions fv ON fv.id=sr.form_version_id "
            "JOIN form_definitions fd ON fd.id=fv.form_definition_id WHERE sr.id=1"
        ).fetchone()[0]
    page = GenericEngineeringSurveyPage(get_engineering_form_definition(form))
    dialog = SurveyMediaDialog(survey_record_id=1,form_code=form)
    query = DataQueryPage()
    try:
        page.load_record(1)
        assert not page.form_container.isEnabled()
        assert not page.save_button.isEnabled()
        assert not page.complete_button.isEnabled()
        assert not page.save_shortcut.isEnabled()
        assert page._save_current_record() is None
        assert page.complete_survey() is None
        buttons = {button.text():button for button in dialog.findChildren(QPushButton)}
        assert not buttons["批量导入影像"].isEnabled()
        assert not buttons["编辑信息"].isEnabled()
        assert not buttons["删除影像"].isEnabled()
        assert buttons["打开影像"].isEnabled()
        query.show_import_changes(1)
        assert len(query.filtered_records) == 1
        query.reset_filters()
        assert query.result_import_id is None
        assert StakeTableItem("CH2+900.000",(2900,2900)) < StakeTableItem("CH10+100.000",(10100,10100))
        assert StakeTableItem("CH2+900.000 ～ CH3+000.000",(2900,3000)) < StakeTableItem("CH2+900.000 ～ CH4+000.000",(2900,4000))
    finally:
        page.close()
        dialog.close()
        query.close()
        page.deleteLater()
        dialog.deleteLater()
        query.deleteLater()
        app.processEvents()


def test_v120_upgrade_preserves_all_business_rows(flow):
    base = flow.base
    base._use_source()
    tables = ("engineering_assets","survey_records","survey_media","inspection_results")
    def snapshot():
        with database.get_connection() as connection:
            return {name:[tuple(row) for row in connection.execute("SELECT * FROM "+name+" ORDER BY id")] for name in tables}
    # Keep task source revision 0 to catch accidental bootstrap backfill.
    with database.get_connection() as connection:
        connection.execute("UPDATE survey_records SET source_revision_no=0")
        connection.execute("DROP TABLE survey_result_import_record_changes")
    (database.DATA_DIR/".v1_2_1_upgrade_backup_complete").unlink()
    before = snapshot()
    result = initialize_application_database()
    assert snapshot() == before
    assert result["v1_2_1_upgrade_backup"]["backup_path"].exists()
    with database.get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM survey_result_import_record_changes").fetchone()[0] == 0


def test_upgrade_backup_failure_stops_before_schema(flow):
    flow.base._use_source()
    (database.DATA_DIR/".v1_2_1_upgrade_backup_complete").unlink()
    with patch("services.application_bootstrap.database_backup_module.create_database_backup",side_effect=OSError("backup failed")), patch("services.application_bootstrap.init_database") as init:
        with pytest.raises(OSError,match="backup failed"):
            initialize_application_database()
        init.assert_not_called()


@pytest.mark.parametrize("end,allowed",[(1000,True),(999,False)])
def test_equal_range_numbering_and_reversed_blocked(end,allowed):
    case = numbering_fixture.V102EngineeringNumberingFinalizationTestCase()
    case.setUp()
    try:
        case._add_lined(start=1000,end=end,sequence=1)
        from services.engineering_numbering import preview_engineering_business_code_renumber
        from services.engineering_numbering_finalization import preview_engineering_numbering_finalization
        basic=preview_engineering_business_code_renumber(project_id=case.project_id,survey_batch_id=case.batch_id)
        final=preview_engineering_numbering_finalization(project_id=case.project_id,survey_batch_id=case.batch_id)
        assert (not basic.issues) == allowed
        assert (not final.errors) == allowed
        with database.get_connection() as connection:
            record_id = connection.execute("SELECT id FROM survey_records").fetchone()[0]
            connection.execute("UPDATE survey_records SET record_status='draft',survey_date='2026-10-15',overall_grade='B',survey_comment='调查完成'")
            connection.execute("INSERT INTO inspection_results(survey_record_id,item_code,category,item_name,grade) VALUES (?,'A01','主体','试验','B')",(record_id,))
        if allowed:
            database.complete_engineering_survey_record(record_id,"form_2_1","range",["A01"],["B"])
        else:
            with pytest.raises(ValueError,match="不能小于"):
                database.complete_engineering_survey_record(record_id,"form_2_1","range",["A01"],["B"])
    finally:
        case.tearDown()


def test_numbering_prefers_current_range_over_legacy_single():
    case = numbering_fixture.V102EngineeringNumberingFinalizationTestCase()
    case.setUp()
    try:
        case._add_point(stake=9000, sequence=1)
        case._add_point(stake=2000, sequence=2)
        from services.engineering_numbering import _load_candidates, _prepare_plan
        with database.get_connection() as connection:
            connection.execute(
                "UPDATE engineering_assets SET start_stake_value=1000,end_stake_value=1000 WHERE single_stake_value=9000"
            )
            connection.execute(
                "UPDATE engineering_assets SET start_stake_value=2000,end_stake_value=2000 WHERE single_stake_value=2000"
            )
            rows = _load_candidates(connection, project_id=case.project_id, survey_batch_id=case.batch_id)
            plan, issues = _prepare_plan(rows)
            assert not issues
            assert [item["engineering_asset_id"] for item in plan] == [rows[0]["engineering_asset_id"], rows[1]["engineering_asset_id"]]
            connection.execute(
                "UPDATE engineering_assets SET end_stake_value=999 WHERE single_stake_value=9000"
            )
            _, issues = _prepare_plan(_load_candidates(connection,project_id=case.project_id,survey_batch_id=case.batch_id))
            assert any(issue.code == "RANGE_STAKE_REVERSED" for issue in issues)
    finally:
        case.tearDown()
