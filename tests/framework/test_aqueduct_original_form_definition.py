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


from forms.engineering.form_2_3 import (
    FORM_2_3,
)
from forms.engineering.formatters import (
    format_dimension_pair,
)


class AqueductOriginalFormDefinitionTestCase(
    unittest.TestCase,
):
    def test_form_2_3_original_form_definition_contract(
        self,
    ):
        definition = (
            FORM_2_3
            .original_form_export_definition
        )

        self.assertIsNotNone(definition)

        assert definition is not None

        self.assertEqual(
            definition.template_filename,
            "form_2_3_V1.xlsx",
        )
        self.assertEqual(
            definition.sheet_name,
            "附表2.3",
        )
        self.assertEqual(
            len(definition.field_bindings),
            16,
        )
        self.assertEqual(
            definition.evaluation_binding.column,
            "E",
        )
        self.assertEqual(
            definition.evaluation_binding.start_row,
            10,
        )
        self.assertEqual(
            definition.conclusion_binding.survey_comment_cell,
            "C22",
        )
        self.assertEqual(
            definition.conclusion_binding.overall_grade_cell,
            "J22",
        )
        self.assertEqual(
            definition.conclusion_binding.survey_date_cell,
            "J23",
        )
        self.assertEqual(
            definition.print_settings.print_area,
            "A1:J26",
        )
        self.assertEqual(
            definition.output_filename_prefix,
            "附表2.3_渡槽（座槽）工程状况调查表",
        )
        self.assertEqual(
            definition.fallback_asset_name,
            "渡槽（座槽）",
        )

    def test_section_size_binding_uses_shared_formatter(
        self,
    ):
        definition = (
            FORM_2_3
            .original_form_export_definition
        )

        assert definition is not None

        binding_by_cell = {
            item.cell: item.binding
            for item
            in definition.field_bindings
        }

        size_binding = binding_by_cell[
            "D7"
        ]

        self.assertEqual(
            size_binding.keys,
            (
                "section_width",
                "section_height",
            ),
        )

        self.assertIs(
            size_binding.formatter,
            format_dimension_pair,
        )

        self.assertEqual(
            size_binding.formatter(
                3.2,
                2.4,
            ),
            "3.2×2.4",
        )


if __name__ == "__main__":
    unittest.main()
