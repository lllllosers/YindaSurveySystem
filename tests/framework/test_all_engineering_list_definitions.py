import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from forms.engineering.form_2_1 import FORM_2_1
from forms.engineering.form_2_2 import FORM_2_2
from forms.engineering.form_2_3 import FORM_2_3
from forms.engineering.form_2_4 import FORM_2_4
from forms.engineering.form_2_5 import FORM_2_5
from forms.engineering.form_2_6 import FORM_2_6
from forms.engineering.list_definitions import (
    STANDARD_ENGINEERING_LIST_HEADERS,
    STANDARD_ENGINEERING_LIST_WIDTHS,
)


FORMS = (
    FORM_2_1,
    FORM_2_2,
    FORM_2_3,
    FORM_2_4,
    FORM_2_5,
    FORM_2_6,
)


class EngineeringListDefinitionContractTestCase(
    unittest.TestCase,
):
    def test_forms_2_1_to_2_6_all_have_list_definition(self):
        for definition in FORMS:
            with self.subTest(
                form_code=definition.form_code,
            ):
                self.assertIsNotNone(
                    definition.list_definition
                )

    def test_forms_2_1_to_2_6_use_same_columns(self):
        for definition in FORMS:
            list_definition = (
                definition.list_definition
            )
            assert list_definition is not None

            with self.subTest(
                form_code=definition.form_code,
            ):
                self.assertEqual(
                    tuple(
                        column.header
                        for column
                        in list_definition.columns
                    ),
                    STANDARD_ENGINEERING_LIST_HEADERS,
                )
                self.assertEqual(
                    tuple(
                        column.width
                        for column
                        in list_definition.columns
                    ),
                    STANDARD_ENGINEERING_LIST_WIDTHS,
                )

    def test_position_is_fully_normalized_at_list_layer(self):
        for definition in FORMS:
            list_definition = (
                definition.list_definition
            )
            assert list_definition is not None

            position_column = (
                list_definition.columns[5]
            )

            with self.subTest(
                form_code=definition.form_code,
            ):
                self.assertEqual(
                    list_definition.position_label,
                    "工程位置",
                )
                self.assertEqual(
                    position_column.header,
                    "工程位置",
                )
                self.assertEqual(
                    position_column.binding.source,
                    "query_record",
                )
                self.assertEqual(
                    position_column.binding.keys,
                    ("engineering_position",),
                )

    def test_keyword_and_statistics_behavior_is_unified(self):
        expected_keyword_keys = (
            "business_code",
            "asset_name",
            "engineering_position",
        )

        for definition in FORMS:
            list_definition = (
                definition.list_definition
            )
            assert list_definition is not None

            with self.subTest(
                form_code=definition.form_code,
            ):
                self.assertEqual(
                    list_definition.keyword_placeholder,
                    "业务编号 / 工程名称 / 工程位置",
                )
                self.assertTrue(
                    list_definition.show_grade_statistics
                )
                self.assertEqual(
                    tuple(
                        binding.keys[0]
                        for binding
                        in list_definition.keyword_bindings
                    ),
                    expected_keyword_keys,
                )

    def test_old_form_specific_list_fields_are_not_list_contracts(self):
        forbidden_headers = {
            "渠道名称",
            "起始桩号",
            "终止桩号",
            "渠段长度(m)",
            "设计流量",
            "桩号",
            "起止桩号",
        }

        for definition in FORMS:
            list_definition = (
                definition.list_definition
            )
            assert list_definition is not None

            headers = {
                column.header
                for column
                in list_definition.columns
            }

            with self.subTest(
                form_code=definition.form_code,
            ):
                self.assertTrue(
                    headers.isdisjoint(
                        forbidden_headers
                    )
                )


if __name__ == "__main__":
    unittest.main()
