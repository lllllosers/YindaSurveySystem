import sys
import unittest
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from forms.engineering.formatters import (
    format_dimension_pair,
    format_dimension_pair_asterisk,
    format_opening_size,
    format_side_slope,
    format_stake_range_compact,
    format_stake_range_spaced,
)
from forms.engineering.registry import (
    get_engineering_form_definition,
    get_engineering_form_definitions,
)


FORMS = get_engineering_form_definitions()


class AllEngineeringOriginalFormDefinitionsTestCase(
    unittest.TestCase,
):
    def test_every_registered_form_has_original_form_definition(
        self,
    ):
        self.assertTrue(FORMS)

        for definition in FORMS:
            with self.subTest(
                form_code=definition.form_code,
            ):
                original = (
                    definition
                    .original_form_export_definition
                )

                self.assertIsNotNone(
                    original
                )

                assert original is not None

                self.assertTrue(
                    original.template_filename.strip()
                )
                self.assertTrue(
                    original.sheet_name.strip()
                )
                self.assertTrue(
                    original.field_bindings
                )
                self.assertTrue(
                    original.output_filename_prefix
                )
                self.assertTrue(
                    original.fallback_asset_name
                )

    def test_existing_forms_keep_exact_original_layout_regression(
        self,
    ):
        expectations = {
            "form_2_1": (
                "form_2_1_V1.xlsx",
                "附表2.1",
                22,
                11,
                "C23",
                "J23",
                "J24",
                "A1:J24",
            ),
            "form_2_2": (
                "form_2_2_V1.xlsx",
                "附表2.2",
                13,
                9,
                "C23",
                "J23",
                "J24",
                "A1:J27",
            ),
            "form_2_3": (
                "form_2_3_V1.xlsx",
                "附表2.3",
                16,
                10,
                "C22",
                "J22",
                "J23",
                "A1:J26",
            ),
            "form_2_4": (
                "form_2_4_V1.xlsx",
                "附表2.4",
                14,
                10,
                "C22",
                "J22",
                "J23",
                "A1:J25",
            ),
            "form_2_5": (
                "form_2_5_V1.xlsx",
                "附表2.5",
                16,
                10,
                "C23",
                "J23",
                "J24",
                "A1:J25",
            ),
            "form_2_6": (
                "form_2_6_V1.xlsx",
                "附表2.6",
                16,
                10,
                "C21",
                "J21",
                "J22",
                "A1:J23",
            ),
        }

        for (
            form_code,
            (
                template_filename,
                sheet_name,
                field_count,
                evaluation_start_row,
                comment_cell,
                grade_cell,
                date_cell,
                print_area,
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

            original = (
                definition
                .original_form_export_definition
            )

            assert original is not None

            with self.subTest(
                form_code=form_code
            ):
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
                    original.conclusion_binding
                    .survey_comment_cell,
                    comment_cell,
                )
                self.assertEqual(
                    original.conclusion_binding
                    .overall_grade_cell,
                    grade_cell,
                )
                self.assertEqual(
                    original.conclusion_binding
                    .survey_date_cell,
                    date_cell,
                )
                self.assertEqual(
                    original.print_settings
                    .print_area,
                    print_area,
                )

    def test_existing_composite_bindings_keep_shared_formatters(
        self,
    ):
        bindings = {}

        for form_code in (
            "form_2_1",
            "form_2_2",
            "form_2_3",
            "form_2_5",
        ):
            definition = (
                get_engineering_form_definition(
                    form_code
                )
            )

            self.assertIsNotNone(
                definition
            )

            assert definition is not None

            original = (
                definition
                .original_form_export_definition
            )

            assert original is not None

            bindings[form_code] = {
                item.cell: item.binding
                for item
                in original.field_bindings
            }

        self.assertIs(
            bindings["form_2_1"]["H5"]
            .formatter,
            format_stake_range_spaced,
        )
        self.assertIs(
            bindings["form_2_1"]["H7"]
            .formatter,
            format_side_slope,
        )
        self.assertIs(
            bindings["form_2_2"]["H6"]
            .formatter,
            format_opening_size,
        )
        self.assertIs(
            bindings["form_2_3"]["D7"]
            .formatter,
            format_dimension_pair,
        )
        self.assertIs(
            bindings["form_2_5"]["F5"]
            .formatter,
            format_stake_range_compact,
        )
        self.assertIs(
            bindings["form_2_5"]["E8"]
            .formatter,
            format_dimension_pair_asterisk,
        )

    def test_legacy_composite_formats_are_preserved(
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
            format_dimension_pair(
                3.2,
                2.4,
            ),
            "3.2×2.4",
        )
        self.assertEqual(
            format_dimension_pair_asterisk(
                3.0,
                3.5,
            ),
            "3.0*3.5",
        )


    def test_all_signature_bindings_match_template_footer_contract(
        self,
    ):
        for definition in FORMS:
            original = definition.original_form_export_definition

            self.assertIsNotNone(original)
            assert original is not None

            conclusion = original.conclusion_binding
            date_cell = conclusion.survey_date_cell

            self.assertTrue(date_cell.startswith("J"))
            row = date_cell[1:]

            with self.subTest(form_code=definition.form_code):
                self.assertEqual(
                    conclusion.surveyor_signatures_cell,
                    f"B{row}",
                )
                self.assertEqual(
                    conclusion.water_office_manager_signature_cell,
                    f"D{row}",
                )
                self.assertEqual(
                    conclusion.engineering_section_chief_signature_cell,
                    f"F{row}",
                )
                self.assertEqual(
                    conclusion.department_head_signature_cell,
                    f"H{row}",
                )


if __name__ == "__main__":
    unittest.main()
