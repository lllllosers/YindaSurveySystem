import gc
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import database
from forms.engineering.formatters import format_stake_range_compact
from forms.engineering.registry import get_engineering_form_definitions

AFFECTED_FORM_CODES = {
    'form_2_2', 'form_2_3', 'form_2_4', 'form_2_6',
    'form_2_8', 'form_2_9', 'form_2_10', 'form_2_11',
    'form_2_12', 'form_2_13', 'form_2_14',
}

class V120ChainageCompatibilityTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH
        database.DATA_DIR = Path(self.temp_directory.name) / 'local_data'
        database.DB_PATH = database.DATA_DIR / 'test_yinda_survey.db'
        database.init_database()
        database.create_initial_forms()

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        gc.collect()
        time.sleep(0.05)
        self.temp_directory.cleanup()

    def test_all_series_2_forms_are_range_position(self):
        definitions = get_engineering_form_definitions()
        self.assertEqual(len(definitions), 14)
        for definition in definitions:
            with self.subTest(form_code=definition.form_code):
                self.assertEqual(definition.position.kind, 'range')
                self.assertEqual(definition.position.start_stake_field, 'start_stake')
                self.assertEqual(definition.position.end_stake_field, 'end_stake')

    def test_form_v1_is_retained_and_v2_is_current(self):
        with database.get_connection() as connection:
            rows = connection.execute('''
                SELECT fd.form_code, fv.version_code, fv.is_current
                FROM form_definitions AS fd
                JOIN form_versions AS fv ON fv.form_definition_id = fd.id
                WHERE fd.series = 'series_2'
                ORDER BY fd.sort_order, fv.version_code
            ''').fetchall()
        by_form = {}
        for row in rows:
            by_form.setdefault(row['form_code'], {})[row['version_code']] = int(row['is_current'])
        self.assertEqual(len(by_form), 14)
        for form_code, versions in by_form.items():
            with self.subTest(form_code=form_code):
                self.assertEqual(versions.get('V1'), 0)
                self.assertEqual(versions.get('V2'), 1)

    def test_affected_exports_keep_stake_header_and_bind_range(self):
        for definition in get_engineering_form_definitions():
            if definition.form_code not in AFFECTED_FORM_CODES:
                continue
            summary = definition.summary_export_definition
            original = definition.original_form_export_definition
            self.assertIsNotNone(summary)
            self.assertIsNotNone(original)
            stake_column = next(column for column in summary.columns if column.header == '桩号')
            self.assertEqual(stake_column.binding.keys, ('start_stake', 'end_stake'))
            self.assertIs(stake_column.binding.formatter, format_stake_range_compact)
            bindings = [item.binding for item in original.field_bindings if item.binding.keys == ('start_stake', 'end_stake')]
            self.assertEqual(len(bindings), 1)
            self.assertIs(bindings[0].formatter, format_stake_range_compact)

    def test_old_point_record_migrates_without_revision_bump(self):
        with database.get_connection() as connection:
            project_id = int(connection.execute("INSERT INTO projects (name, status) VALUES ('迁移测试项目', 'active')").lastrowid)
            batch_id = int(connection.execute("INSERT INTO survey_batches (project_id, batch_name, batch_code, status) VALUES (?, '迁移批次', 'V120', 'active')", (project_id,)).lastrowid)
            department_id = int(connection.execute("INSERT INTO organization_units (name, unit_type, business_code) VALUES ('测试处', 'department', '91')").lastrowid)
            office_id = int(connection.execute("INSERT INTO organization_units (parent_id, name, unit_type, business_code) VALUES (?, '测试所', 'water_office', '01')", (department_id,)).lastrowid)
            canal_id = int(connection.execute("INSERT INTO canal_units (name, canal_level) VALUES ('测试干渠', '01')").lastrowid)
            form_row = connection.execute("SELECT fv.id FROM form_definitions fd JOIN form_versions fv ON fv.form_definition_id = fd.id WHERE fd.form_code = 'form_2_2' AND fv.version_code = 'V1'").fetchone()
            asset_id = int(connection.execute('''
                INSERT INTO engineering_assets (
                    project_id, asset_name, asset_type, organization_unit_id, canal_unit_id,
                    business_code, single_stake_text, single_stake_value, first_survey_batch_id,
                    revision_no, source_revision_no, code_status, updated_at
                ) VALUES (?, '旧版测试水闸', 'sluice_gate', ?, ?, '91-01-01-02-001',
                          'CH12+350', 12350.0, ?, 7, 3, 'provisional', '2026-09-20 10:00:00')
            ''', (project_id, office_id, canal_id, batch_id)).lastrowid)
            record_id = int(connection.execute('''
                INSERT INTO survey_records (
                    project_id, survey_batch_id, form_version_id, record_type, organization_unit_id,
                    canal_unit_id, engineering_asset_id, business_code, record_status, record_data_json,
                    revision_no, source_revision_no, updated_at
                ) VALUES (?, ?, ?, 'engineering', ?, ?, ?, '91-01-01-02-001', 'completed', ?,
                          9, 4, '2026-09-20 11:00:00')
            ''', (project_id, batch_id, int(form_row['id']), office_id, canal_id, asset_id,
                  json.dumps({'asset_name': '旧版测试水闸', 'stake': 'CH12+350'}, ensure_ascii=False))).lastrowid)
        database.init_database()
        with database.get_connection() as connection:
            asset = connection.execute("SELECT * FROM engineering_assets WHERE id = ?", (asset_id,)).fetchone()
            record = connection.execute("SELECT * FROM survey_records WHERE id = ?", (record_id,)).fetchone()
        self.assertEqual(asset['single_stake_text'], 'CH12+350')
        self.assertEqual(asset['start_stake_text'], 'CH12+350')
        self.assertIsNone(asset['end_stake_text'])
        self.assertEqual(int(asset['revision_no']), 7)
        self.assertEqual(int(asset['source_revision_no']), 3)
        self.assertEqual(asset['updated_at'], '2026-09-20 10:00:00')
        record_data = json.loads(record['record_data_json'])
        self.assertEqual(record_data['stake'], 'CH12+350')
        self.assertEqual(record_data['start_stake'], 'CH12+350')
        self.assertNotIn('end_stake', record_data)
        self.assertEqual(int(record['revision_no']), 9)
        self.assertEqual(int(record['source_revision_no']), 4)
        self.assertEqual(record['updated_at'], '2026-09-20 11:00:00')
        rows = database.get_engineering_survey_query_records(project_id=project_id, survey_batch_id=batch_id, form_code='form_2_2')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['engineering_position'], 'CH12+350')
        self.assertTrue(rows[0]['chainage_incomplete'])

if __name__ == '__main__':
    unittest.main()
