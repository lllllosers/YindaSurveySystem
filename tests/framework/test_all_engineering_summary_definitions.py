import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from forms.engineering.form_2_1 import FORM_2_1
from forms.engineering.form_2_2 import FORM_2_2
from forms.engineering.form_2_3 import FORM_2_3
from forms.engineering.form_2_4 import FORM_2_4
from forms.engineering.form_2_5 import FORM_2_5
from forms.engineering.form_2_6 import FORM_2_6
from forms.engineering.formatters import (
    format_dimension_pair_asterisk,
)


class AllEngineeringSummaryDefinitionsTestCase(
    unittest.TestCase,
):
    def test_forms_2_1_to_2_6_have_summary_definitions(
        self,
    ):
        # EngineeringFormDefinition 是 frozen dataclass，
        # 但其 evaluation_items 内含 dict，
        # 因此对象本身不适合作为 dict key。
        # 这里使用普通 tuple 保存测试期望。
        expectations = (
            (
                FORM_2_1,
                "渠道渠段调查汇总",
                28,
                30,
            ),
            (
                FORM_2_2,
                "水闸调查汇总",
                19,
                21,
            ),
            (
                FORM_2_3,
                "渡槽调查汇总",
                20,
                22,
            ),
            (
                FORM_2_4,
                "倒虹吸调查汇总",
                18,
                20,
            ),
            (
                FORM_2_5,
                "隧洞调查汇总",
                21,
                23,
            ),
            (
                FORM_2_6,
                "涵洞（暗涵）调查汇总",
                20,
                22,
            ),
        )

        for (
            definition,
            sheet_name,
            column_count,
            evaluation_start_column,
        ) in expectations:
            with self.subTest(
                form_code=definition.form_code
            ):
                summary = (
                    definition
                    .summary_export_definition
                )

                self.assertIsNotNone(summary)

                assert summary is not None

                self.assertEqual(
                    summary.sheet_name,
                    sheet_name,
                )

                self.assertEqual(
                    len(summary.columns),
                    column_count,
                )

                self.assertEqual(
                    2 + len(summary.columns),
                    evaluation_start_column,
                )

    def test_all_summary_definitions_keep_common_identity_prefix(
        self,
    ):
        for definition in (
            FORM_2_1,
            FORM_2_2,
            FORM_2_3,
            FORM_2_4,
            FORM_2_5,
            FORM_2_6,
        ):
            summary = (
                definition
                .summary_export_definition
            )

            assert summary is not None

            self.assertEqual(
                summary.columns[0].header,
                "业务编号",
            )

            self.assertEqual(
                tuple(
                    column.header
                    for column
                    in summary.columns[2:5]
                ),
                (
                    "基层处",
                    "水管所",
                    "渠系",
                ),
            )

    def test_tunnel_dimension_formatter_preserves_legacy_asterisk_format(
        self,
    ):
        self.assertEqual(
            format_dimension_pair_asterisk(
                3.0,
                2.4,
            ),
            "3.0*2.4",
        )

        self.assertEqual(
            format_dimension_pair_asterisk(
                None,
                None,
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
