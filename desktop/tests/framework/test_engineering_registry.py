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


from forms.engineering.registry import (
    get_engineering_form_definition,
    get_engineering_form_definitions,
    get_engineering_grade_options,
)


class EngineeringRegistryContractTestCase(
    unittest.TestCase,
):
    def test_registered_forms_have_unique_core_identity(
        self,
    ):
        definitions = (
            get_engineering_form_definitions()
        )

        self.assertTrue(definitions)

        for attribute in (
            "form_code",
            "form_number",
            "business_type_code",
        ):
            values = tuple(
                getattr(
                    definition,
                    attribute,
                )
                for definition in definitions
            )

            with self.subTest(
                attribute=attribute,
            ):
                self.assertEqual(
                    len(values),
                    len(set(values)),
                )

    def test_lookup_returns_same_registered_definition(
        self,
    ):
        for definition in (
            get_engineering_form_definitions()
        ):
            with self.subTest(
                form_code=definition.form_code,
            ):
                self.assertIs(
                    get_engineering_form_definition(
                        definition.form_code
                    ),
                    definition,
                )

    def test_grade_options_are_registry_driven(
        self,
    ):
        definitions = (
            get_engineering_form_definitions()
        )

        expected_union = []

        for definition in definitions:
            self.assertEqual(
                get_engineering_grade_options(
                    definition.form_code
                ),
                tuple(
                    definition.grade_options
                ),
            )

            for grade in (
                definition.grade_options
            ):
                if grade not in expected_union:
                    expected_union.append(
                        grade
                    )

        self.assertEqual(
            get_engineering_grade_options(),
            tuple(expected_union),
        )

    def test_unknown_form_code_has_no_definition(
        self,
    ):
        self.assertIsNone(
            get_engineering_form_definition(
                "form_2_missing"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "未找到工程调查表定义",
        ):
            get_engineering_grade_options(
                "form_2_missing"
            )


if __name__ == "__main__":
    unittest.main()
