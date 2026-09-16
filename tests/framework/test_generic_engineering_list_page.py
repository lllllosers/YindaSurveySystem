import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import (
    QApplication,
)

from forms.engineering.form_2_3 import (
    FORM_2_3,
)

from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)

from pages.components.generic_engineering_list_page import (
    GenericEngineeringListPage,
)


class GenericEngineeringListPageTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def setUp(
        self,
    ):
        self.load_data_patch = patch.object(
            EngineeringSurveyListPage,
            "load_data",
            return_value=None,
        )

        self.load_data_patch.start()

        self.page = (
            GenericEngineeringListPage(
                FORM_2_3
            )
        )

    def tearDown(
        self,
    ):
        self.page.deleteLater()
        self.load_data_patch.stop()

    def test_form_2_3_has_list_definition(
        self,
    ):
        self.assertIsNotNone(
            FORM_2_3.list_definition
        )

        assert (
            FORM_2_3.list_definition
            is not None
        )

        self.assertEqual(
            FORM_2_3.list_definition
            .new_button_text,
            "新增渡槽（座槽）调查",
        )

        self.assertTrue(
            FORM_2_3.list_definition
            .show_grade_statistics
        )

    def test_generic_list_uses_definition_directly(
        self,
    ):
        self.assertIs(
            self.page.definition,
            FORM_2_3,
        )

        self.assertEqual(
            self.page.FORM_CODE,
            FORM_2_3.form_code,
        )

        self.assertEqual(
            self.page.GRADE_OPTIONS,
            FORM_2_3.grade_options,
        )

        original = (
            FORM_2_3
            .original_form_export_definition
        )

        assert original is not None

        self.assertEqual(
            self.page.EXPORT_FILENAME_PREFIX,
            original.output_filename_prefix,
        )

        self.assertEqual(
            self.page.EXPORT_FALLBACK_ASSET_NAME,
            original.fallback_asset_name,
        )

    def test_headers_and_widths_come_from_definition(
        self,
    ):
        definition = (
            FORM_2_3.list_definition
        )

        assert definition is not None

        self.assertEqual(
            self.page.TABLE_HEADERS,
            tuple(
                column.header
                for column
                in definition.columns
            ),
        )

        self.assertEqual(
            self.page.TABLE_WIDTHS,
            tuple(
                column.width
                for column
                in definition.columns
            ),
        )

        self.assertEqual(
            self.page.TABLE_HEADERS,
            (
                "业务编号",
                "工程名称",
                "基层处",
                "水管所",
                "渠系",
                "工程位置",
                "工程状况类别",
                "调查时间",
                "状态",
                "修改时间",
            ),
        )

    def test_row_values_follow_bindings(
        self,
    ):
        record = {
            "survey_record_id": 123,
            "business_code": (
                "1-01-01-03-001"
            ),
            "asset_name": "测试渡槽",
            "department_name": (
                "测试基层处"
            ),
            "office_name": (
                "测试水管所"
            ),
            "canal_name": "测试总干渠",
            "engineering_position": (
                "K25+300"
            ),
            "overall_grade": "B",
            "survey_date": "2026-09-16",
            "record_status": "completed",
            "updated_at": (
                "2026-09-16 10:20:30"
            ),
            "record_data": {},
        }

        self.assertEqual(
            self.page._build_table_values(
                record
            ),
            [
                "1-01-01-03-001",
                "测试渡槽",
                "测试基层处",
                "测试水管所",
                "测试总干渠",
                "K25+300",
                "B",
                "2026-09-16",
                "录入完成",
                "2026-09-16 10:20:30",
            ],
        )

    def test_default_keyword_sources_use_common_query_fields(
        self,
    ):
        record = {
            "business_code": "CODE-001",
            "asset_name": "测试渡槽",
            "engineering_position": (
                "K25+300"
            ),
            "record_data": {},
        }

        self.assertEqual(
            self.page._keyword_values(
                record
            ),
            [
                "CODE-001",
                "测试渡槽",
                "K25+300",
            ],
        )

    def test_status_formatter_preserves_unknown_status(
        self,
    ):
        record = {
            "survey_record_id": 1,
            "business_code": "CODE",
            "asset_name": "名称",
            "department_name": "处",
            "office_name": "所",
            "canal_name": "渠",
            "engineering_position": "K1+000",
            "overall_grade": None,
            "survey_date": None,
            "record_status": "future_status",
            "updated_at": None,
            "record_data": {},
        }

        values = (
            self.page
            ._build_table_values(record)
        )

        self.assertEqual(
            values[8],
            "future_status",
        )

    def test_original_export_calls_generic_engine(
        self,
    ):
        with patch(
            "pages.components."
            "generic_engineering_list_page."
            "export_engineering_original_form",
            return_value={
                "survey_record_id": 123,
            },
        ) as exporter:
            result = (
                self.page
                ._export_original_form(
                    123,
                    "test.xlsx",
                )
            )

        exporter.assert_called_once_with(
            FORM_2_3,
            survey_record_id=123,
            file_path="test.xlsx",
        )

        self.assertEqual(
            result["survey_record_id"],
            123,
        )


if __name__ == "__main__":
    unittest.main()
