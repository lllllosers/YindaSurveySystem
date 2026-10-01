import gc
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import database

from PySide6.QtWidgets import QApplication, QLineEdit
from pages.components.generic_engineering_survey_page import GenericEngineeringSurveyPage
from tests.framework.engineering_test_fixtures import TEST_POINT_DEFINITION


class EngineeringSignatureUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = GenericEngineeringSurveyPage(TEST_POINT_DEFINITION)

    def tearDown(self):
        self.page.deleteLater()

    def test_four_signature_inputs_exist(self):
        controls = (
            self.page.surveyor_signatures_edit,
            self.page.water_office_manager_signature_edit,
            self.page.engineering_section_chief_signature_edit,
            self.page.department_head_signature_edit,
        )
        for control in controls:
            self.assertIsInstance(control, QLineEdit)

    def test_multiple_surveyors_preserve_user_text(self):
        self.page.surveyor_signatures_edit.setText("张三、李四，王五")
        self.page.water_office_manager_signature_edit.setText("赵六")
        self.page.engineering_section_chief_signature_edit.setText("钱七")
        self.page.department_head_signature_edit.setText("孙八")

        data = self.page.collect_conclusion_data()

        self.assertEqual(data["surveyor_signatures"], "张三、李四，王五")
        self.assertEqual(data["water_office_manager_signature"], "赵六")
        self.assertEqual(data["engineering_section_chief_signature"], "钱七")
        self.assertEqual(data["department_head_signature"], "孙八")
        self.assertIn("多人", self.page.surveyor_signatures_edit.placeholderText())

    def test_signatures_are_optional_for_completion(self):
        errors = self.page.validate_for_completion()

        for label in (
            "调查人签字",
            "水管所负责人",
            "工程科科长",
            "基层处负责人",
        ):
            self.assertFalse(
                any(label in error for error in errors)
            )

    def test_load_and_clear_signature_fields(self):
        self.page.load_conclusion_data(
            survey_date="2026-09-19",
            overall_grade=None,
            survey_comment="测试意见",
            surveyor_signatures="甲、乙",
            water_office_manager_signature="丙",
            engineering_section_chief_signature="丁",
            department_head_signature="戊",
        )

        self.assertEqual(self.page.surveyor_signatures_edit.text(), "甲、乙")
        self.assertEqual(self.page.water_office_manager_signature_edit.text(), "丙")
        self.assertEqual(self.page.engineering_section_chief_signature_edit.text(), "丁")
        self.assertEqual(self.page.department_head_signature_edit.text(), "戊")

        self.page.clear_form_data()

        self.assertEqual(self.page.surveyor_signatures_edit.text(), "")
        self.assertEqual(self.page.water_office_manager_signature_edit.text(), "")
        self.assertEqual(self.page.engineering_section_chief_signature_edit.text(), "")
        self.assertEqual(self.page.department_head_signature_edit.text(), "")


class SurveyRecordSignaturePersistenceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_data_dir = Path(self.temp_directory.name) / "local_data"
        self.temp_db_path = self.temp_data_dir / "signature_test.db"

        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_data_dir
        database.DB_PATH = self.temp_db_path

        database.init_database()
        database.create_initial_forms()

        project = database.create_project(
            name="签字测试项目",
            short_name="签字测试",
        )
        self.project_id = int(project["project_id"])

        batch = database.create_survey_batch(
            project_id=self.project_id,
            batch_name="签字测试批次",
            batch_code="SIG_001",
        )
        self.batch_id = int(batch["batch_id"])

        database.create_organization_unit(
            name="测试基层处",
            unit_type="department",
            business_code="1",
        )
        department = database.get_departments()[0]

        database.create_organization_unit(
            name="测试水管所",
            unit_type="water_office",
            business_code="01",
            parent_id=int(department["id"]),
        )
        office = database.get_water_offices(int(department["id"]))[0]
        self.office_id = int(office["id"])

        database.create_canal_unit(
            name="测试干渠",
            canal_level="01",
            parent_id=None,
        )

        with database.get_connection() as connection:
            canal = connection.execute(
                "SELECT id FROM canal_units ORDER BY id LIMIT 1"
            ).fetchone()

        self.canal_id = int(canal["id"])
        form_version = database.get_current_form_version("form_2_2")
        self.form_version_id = int(form_version["id"])

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        gc.collect()
        time.sleep(0.05)
        self.temp_directory.cleanup()

    def test_schema_has_four_signature_columns(self):
        with database.get_connection() as connection:
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(survey_records)"
                ).fetchall()
            }

        self.assertTrue(
            {
                "surveyor_signatures",
                "water_office_manager_signature",
                "engineering_section_chief_signature",
                "department_head_signature",
            }.issubset(columns)
        )

    def test_point_record_signatures_create_load_update(self):
        created = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=self.form_version_id,
            asset_name="测试水闸",
            asset_type="sluice_gate",
            organization_unit_id=self.office_id,
            canal_unit_id=self.canal_id,
            business_code="1-01-01-02-001",
            record_data={"stake": "CH1+000"},
            single_stake_text="CH1+000",
            single_stake_value=1000.0,
            surveyor_signatures="张三、李四",
            water_office_manager_signature="王五",
            engineering_section_chief_signature="赵六",
            department_head_signature="钱七",
        )

        record_id = int(created["survey_record_id"])
        loaded = database.get_point_engineering_record(
            record_id,
            "form_2_2",
        )

        self.assertEqual(loaded["surveyor_signatures"], "张三、李四")
        self.assertEqual(loaded["water_office_manager_signature"], "王五")

        database.update_point_engineering_survey(
            survey_record_id=record_id,
            form_code="form_2_2",
            asset_name="测试水闸",
            record_data={"stake": "CH1+000"},
            single_stake_text="CH1+000",
            single_stake_value=1000.0,
            surveyor_signatures="张三、李四、周八",
            water_office_manager_signature="王五",
            engineering_section_chief_signature="赵六",
            department_head_signature="钱七",
        )

        updated = database.get_point_engineering_record(
            record_id,
            "form_2_2",
        )
        self.assertEqual(
            updated["surveyor_signatures"],
            "张三、李四、周八",
        )


if __name__ == "__main__":
    unittest.main()
