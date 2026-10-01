import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from forms.engineering.form_2_7 import FORM_2_7
from forms.engineering.form_2_8 import FORM_2_8
from forms.engineering.form_2_9 import FORM_2_9
from forms.engineering.form_2_12 import FORM_2_12
from forms.engineering.form_2_13 import FORM_2_13


class BatchAFormDefinitionTestCase(unittest.TestCase):
    def test_batch_a_core_contracts(self):
        expectations = (
            (FORM_2_7, "range", "07", 16, 10),
            (FORM_2_8, "range", "08", 14, 7),
            (FORM_2_9, "range", "09", 13, 9),
            (FORM_2_12, "range", "12", 12, 10),
            (FORM_2_13, "range", "13", 19, 4),
        )

        for (
            definition,
            position_kind,
            business_type_code,
            field_count,
            evaluation_count,
        ) in expectations:
            with self.subTest(
                form_code=definition.form_code,
            ):
                self.assertEqual(
                    definition.position.kind,
                    position_kind,
                )
                self.assertEqual(
                    definition.business_type_code,
                    business_type_code,
                )
                self.assertEqual(
                    len(definition.fields),
                    field_count,
                )
                self.assertEqual(
                    len(definition.evaluation_items),
                    evaluation_count,
                )
                self.assertEqual(
                    definition.grade_options,
                    ("A", "B", "C", "D"),
                )
                self.assertIsNotNone(
                    definition.list_definition
                )
                self.assertIsNotNone(
                    definition.summary_export_definition
                )
                self.assertIsNotNone(
                    definition.original_form_export_definition
                )

    def test_form_2_7_is_range(self):
        self.assertEqual(
            FORM_2_7.position.start_stake_field,
            "start_stake",
        )
        self.assertEqual(
            FORM_2_7.position.end_stake_field,
            "end_stake",
        )

    def test_form_2_13_uses_choice_for_earthwork_type(self):
        field = FORM_2_13.field_map[
            "earthwork_type"
        ]

        self.assertEqual(
            field.input_type,
            "choice",
        )
        self.assertEqual(
            field.choices,
            ("挖方", "填方"),
        )


if __name__ == "__main__":
    unittest.main()
