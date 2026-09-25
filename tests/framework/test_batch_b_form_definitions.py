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


from forms.engineering.form_2_10 import (
    FORM_2_10,
)
from forms.engineering.form_2_11 import (
    FORM_2_11,
)
from forms.engineering.form_2_14 import (
    FORM_2_14,
)


class BatchBFormDefinitionTestCase(
    unittest.TestCase,
):
    def test_batch_b_core_contracts(
        self,
    ):
        expectations = (
            (
                FORM_2_10,
                "10",
                17,
                12,
            ),
            (
                FORM_2_11,
                "11",
                12,
                11,
            ),
            (
                FORM_2_14,
                "14",
                9,
                6,
            ),
        )

        for (
            definition,
            business_type_code,
            field_count,
            evaluation_count,
        ) in expectations:
            with self.subTest(
                form_code=definition.form_code,
            ):
                self.assertEqual(
                    definition.position.kind,
                    "range",
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
                    len(
                        definition
                        .evaluation_items
                    ),
                    evaluation_count,
                )
                self.assertEqual(
                    definition.grade_options,
                    (
                        "A",
                        "B",
                        "C",
                    ),
                )
                self.assertIsNotNone(
                    definition
                    .list_definition
                )
                self.assertIsNotNone(
                    definition
                    .summary_export_definition
                )
                self.assertIsNotNone(
                    definition
                    .original_form_export_definition
                )

    def test_all_evaluation_items_are_three_grade(
        self,
    ):
        for definition in (
            FORM_2_10,
            FORM_2_11,
            FORM_2_14,
        ):
            for item in (
                definition
                .evaluation_items
            ):
                with self.subTest(
                    form_code=(
                        definition
                        .form_code
                    ),
                    item_code=(
                        item[
                            "item_code"
                        ]
                    ),
                ):
                    self.assertEqual(
                        tuple(
                            item[
                                "standards"
                            ].keys()
                        ),
                        (
                            "A",
                            "B",
                            "C",
                        ),
                    )

    def test_form_2_14_flood_control_presence_is_choice(
        self,
    ):
        field = FORM_2_14.field_map[
            "has_flood_control_facility"
        ]

        self.assertEqual(
            field.input_type,
            "choice",
        )
        self.assertEqual(
            field.choices,
            (
                "有",
                "无",
            ),
        )

    def test_form_2_14_time_fields_do_not_invent_month_contract(
        self,
    ):
        for key in (
            "flood_control_build_time",
            "flood_control_renovation_time",
        ):
            with self.subTest(
                field=key,
            ):
                self.assertEqual(
                    FORM_2_14
                    .field_map[key]
                    .input_type,
                    "text",
                )


if __name__ == "__main__":
    unittest.main()
