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
from forms.engineering.form_2_5 import FORM_2_5
from forms.engineering.formatters import (
    format_dimension_pair_asterisk,
    format_opening_size,
    format_side_slope,
    format_stake_range_compact,
    format_stake_range_spaced,
)


class RemainingOriginalFormDefinitionsTestCase(
    unittest.TestCase,
):
    def test_remaining_original_form_definition_contracts(
        self,
    ):
        expectations = (
            (
                FORM_2_1,
                "form_2_1_V1.xlsx",
                "附表2.1",
                22,
                11,
                "C23",
                "J23",
                "J24",
                "A1:J24",
            ),
            (
                FORM_2_2,
                "form_2_2_V1.xlsx",
                "附表2.2",
                13,
                9,
                "C23",
                "J23",
                "J24",
                "A1:J27",
            ),
            (
                FORM_2_5,
                "form_2_5_V1.xlsx",
                "附表2.5",
                16,
                10,
                "C23",
                "J23",
                "J24",
                "A1:J25",
            ),
        )

        for (
            definition,
            template_filename,
            sheet_name,
            field_count,
            evaluation_start_row,
            comment_cell,
            grade_cell,
            date_cell,
            print_area,
        ) in expectations:
            with self.subTest(
                form_code=definition.form_code
            ):
                original = (
                    definition
                    .original_form_export_definition
                )

                self.assertIsNotNone(
                    original
                )
                assert original is not None

                self.assertEqual(
                    original.template_filename,
                    template_filename,
                )
                self.assertEqual(
                    original.sheet_name,
                    sheet_name,
                )
                self.assertEqual(
                    len(original.field_bindings),
                    field_count,
                )
                self.assertEqual(
                    original.evaluation_binding.column,
                    "E",
                )
                self.assertEqual(
                    original.evaluation_binding.start_row,
                    evaluation_start_row,
                )
                self.assertEqual(
                    original.conclusion_binding.survey_comment_cell,
                    comment_cell,
                )
                self.assertEqual(
                    original.conclusion_binding.overall_grade_cell,
                    grade_cell,
                )
                self.assertEqual(
                    original.conclusion_binding.survey_date_cell,
                    date_cell,
                )
                self.assertEqual(
                    original.print_settings.print_area,
                    print_area,
                )

    def test_legacy_composite_formatters_are_preserved(
        self,
    ):
        self.assertEqual(
            format_stake_range_spaced(
                "K10+000",
                "K11+000",
            ),
            "K10+000 ～ K11+000",
        )

        self.assertEqual(
            format_stake_range_compact(
                "K20+000",
                "K21+200",
            ),
            "K20+000～K21+200",
        )

        self.assertEqual(
            format_side_slope(
                "1:1.5",
                "1:1.5",
            ),
            "1:1.5/1:1.5",
        )

        self.assertEqual(
            format_opening_size(
                2,
                3.5,
                2.8,
            ),
            "2/3.5×2.8",
        )

        self.assertEqual(
            format_dimension_pair_asterisk(
                3.0,
                3.5,
            ),
            "3.0*3.5",
        )

    def test_composite_bindings_use_expected_formatters(
        self,
    ):
        original_21 = (
            FORM_2_1
            .original_form_export_definition
        )
        original_22 = (
            FORM_2_2
            .original_form_export_definition
        )
        original_25 = (
            FORM_2_5
            .original_form_export_definition
        )

        assert original_21 is not None
        assert original_22 is not None
        assert original_25 is not None

        bindings_21 = {
            item.cell: item.binding
            for item in original_21.field_bindings
        }
        bindings_22 = {
            item.cell: item.binding
            for item in original_22.field_bindings
        }
        bindings_25 = {
            item.cell: item.binding
            for item in original_25.field_bindings
        }

        self.assertIs(
            bindings_21["H5"].formatter,
            format_stake_range_spaced,
        )
        self.assertIs(
            bindings_21["H7"].formatter,
            format_side_slope,
        )
        self.assertIs(
            bindings_22["H6"].formatter,
            format_opening_size,
        )
        self.assertIs(
            bindings_25["F5"].formatter,
            format_stake_range_compact,
        )
        self.assertIs(
            bindings_25["E8"].formatter,
            format_dimension_pair_asterisk,
        )


if __name__ == "__main__":
    unittest.main()
