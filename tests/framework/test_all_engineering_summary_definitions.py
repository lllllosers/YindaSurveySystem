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


from forms.engineering.formatters import (
    format_dimension_pair_asterisk,
)
from forms.engineering.registry import (
    get_engineering_form_definition,
    get_engineering_form_definitions,
)


FORMS = get_engineering_form_definitions()


class AllEngineeringSummaryDefinitionsTestCase(
    unittest.TestCase,
):
    def test_every_registered_form_has_summary_definition(
        self,
    ):
        self.assertTrue(FORMS)

        for definition in FORMS:
            with self.subTest(
                form_code=definition.form_code,
            ):
                summary = (
                    definition
                    .summary_export_definition
                )

                self.assertIsNotNone(summary)

                assert summary is not None

                self.assertTrue(
                    summary.sheet_name.strip()
                )
                self.assertTrue(
                    summary.columns
                )

    def test_every_registered_summary_keeps_common_identity_prefix(
        self,
    ):
        for definition in FORMS:
            summary = (
                definition
                .summary_export_definition
            )

            assert summary is not None

            with self.subTest(
                form_code=definition.form_code,
            ):
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

    def test_existing_forms_keep_exact_summary_layout_regression(
        self,
    ):
        expectations = {
            "form_2_1": (
                "渠道渠段调查汇总",
                28,
                30,
            ),
            "form_2_2": (
                "水闸调查汇总",
                19,
                21,
            ),
            "form_2_3": (
                "渡槽调查汇总",
                20,
                22,
            ),
            "form_2_4": (
                "倒虹吸调查汇总",
                18,
                20,
            ),
            "form_2_5": (
                "隧洞调查汇总",
                21,
                23,
            ),
            "form_2_6": (
                "涵洞（暗涵）调查汇总",
                20,
                22,
            ),
        }

        for (
            form_code,
            (
                sheet_name,
                column_count,
                evaluation_start_column,
            ),
        ) in expectations.items():
            definition = (
                get_engineering_form_definition(
                    form_code
                )
            )

            self.assertIsNotNone(
                definition
            )

            assert definition is not None

            summary = (
                definition
                .summary_export_definition
            )

            assert summary is not None

            with self.subTest(
                form_code=form_code,
            ):
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
