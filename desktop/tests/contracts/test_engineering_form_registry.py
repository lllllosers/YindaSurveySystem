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


from forms.engineering.models import (
    EngineeringFormDefinition,
)

from forms.engineering.registry import (
    get_engineering_form_definition,
    get_engineering_form_definitions,
)

from services.business_code import (
    get_engineering_type_code,
)


class EngineeringFormRegistryContractTestCase(
    unittest.TestCase,
):
    def test_registry_contains_form_definitions_in_numeric_order(
        self,
    ):
        definitions = (
            get_engineering_form_definitions()
        )

        self.assertTrue(
            definitions
        )

        # form_number 是层级编号，不是十进制数：
        # 2.12 应排在 2.9 之后，而不是按 float
        # 被解释成 2.12 < 2.2。
        form_number_keys = tuple(
            tuple(
                int(part)
                for part in
                definition.form_number.split(".")
            )
            for definition
            in definitions
        )

        self.assertEqual(
            form_number_keys,
            tuple(
                sorted(form_number_keys)
            ),
        )

    def test_registered_definition_lookup(
        self,
    ):
        definitions = (
            get_engineering_form_definitions()
        )

        for definition in definitions:
            with self.subTest(
                form_code=definition.form_code
            ):
                self.assertIs(
                    get_engineering_form_definition(
                        definition.form_code
                    ),
                    definition,
                )

    def test_registered_definitions_are_valid_contract_objects(
        self,
    ):
        definitions = (
            get_engineering_form_definitions()
        )

        for definition in definitions:
            with self.subTest(
                form_code=definition.form_code
            ):
                self.assertIsInstance(
                    definition,
                    EngineeringFormDefinition,
                )

                self.assertTrue(
                    definition.form_code.startswith(
                        "form_2_"
                    )
                )

                self.assertRegex(
                    definition.business_type_code,
                    r"^\d{2}$",
                )

                expected_code = (
                    "form_"
                    + definition.form_number.replace(
                        ".",
                        "_",
                    )
                )

                self.assertEqual(
                    definition.form_code,
                    expected_code,
                )

    def test_registry_identity_values_are_unique(
        self,
    ):
        definitions = (
            get_engineering_form_definitions()
        )

        for attribute_name in (
            "form_code",
            "form_number",
            "business_type_code",
        ):
            values = [
                getattr(
                    definition,
                    attribute_name,
                )
                for definition
                in definitions
            ]

            with self.subTest(
                attribute_name=attribute_name,
            ):
                self.assertEqual(
                    len(values),
                    len(set(values)),
                )

    def test_all_business_codes_come_from_definitions(
        self,
    ):
        definitions = (
            get_engineering_form_definitions()
        )

        for definition in definitions:
            with self.subTest(
                form_code=definition.form_code
            ):
                self.assertEqual(
                    get_engineering_type_code(
                        definition.form_code
                    ),
                    definition.business_type_code,
                )

    def test_unknown_form_code_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "暂不支持调查表",
        ):
            get_engineering_type_code(
                "form_2_99"
            )


if __name__ == "__main__":
    unittest.main()
