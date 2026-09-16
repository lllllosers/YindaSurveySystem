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


from forms.engineering.form_2_1 import (
    FORM_2_1,
)
from forms.engineering.form_2_2 import (
    FORM_2_2,
)
from forms.engineering.form_2_3 import (
    FORM_2_3,
)
from forms.engineering.form_2_4 import (
    FORM_2_4,
)
from forms.engineering.form_2_5 import (
    FORM_2_5,
)
from forms.engineering.form_2_6 import (
    FORM_2_6,
)

from forms.engineering.models import (
    EngineeringFormDefinition,
)

from forms.engineering.registry import (
    get_engineering_form_definition,
    get_engineering_form_definitions,
)

from services.business_code import (
    LEGACY_ENGINEERING_TYPE_CODES,
    get_engineering_type_code,
)


class EngineeringFormRegistryContractTestCase(
    unittest.TestCase,
):
    def test_all_current_forms_are_registered(
        self,
    ):
        self.assertEqual(
            get_engineering_form_definitions(),
            (
                FORM_2_1,
                FORM_2_2,
                FORM_2_3,
                FORM_2_4,
                FORM_2_5,
                FORM_2_6,
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

            self.assertEqual(
                len(values),
                len(set(values)),
            )

    def test_legacy_business_code_map_is_empty(
        self,
    ):
        self.assertEqual(
            LEGACY_ENGINEERING_TYPE_CODES,
            {},
        )

    def test_all_business_codes_come_from_definitions(
        self,
    ):
        expected_codes = (
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
        )

        definitions = (
            get_engineering_form_definitions()
        )

        self.assertEqual(
            tuple(
                definition.business_type_code
                for definition
                in definitions
            ),
            expected_codes,
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
