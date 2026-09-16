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
    """
    EngineeringFormRegistry 全局合同。

    这里只检查所有已迁移 definition
    都必须满足的跨表单约束。

    各张正式附表自己的详细字段、
    评价标准等继续由对应 golden contract
    测试负责。
    """

    def test_current_registered_definitions(
        self,
    ):
        definitions = get_engineering_form_definitions()

        self.assertEqual(
            definitions,
            (
                FORM_2_5,
                FORM_2_6,
            ),
        )

    def test_registered_definition_lookup(
        self,
    ):
        self.assertIs(
            get_engineering_form_definition("form_2_5"),
            FORM_2_5,
        )

        self.assertIs(
            get_engineering_form_definition("form_2_6"),
            FORM_2_6,
        )

        self.assertIsNone(get_engineering_form_definition("form_2_4"))

    def test_registered_definitions_are_valid_contract_objects(
        self,
    ):
        definitions = get_engineering_form_definitions()

        for definition in definitions:
            with self.subTest(
                form_code=(definition.form_code),
            ):
                self.assertIsInstance(
                    definition,
                    EngineeringFormDefinition,
                )

                self.assertTrue(definition.form_code.startswith("form_2_"))

                self.assertTrue(definition.form_number.strip())

                self.assertTrue(definition.form_name.strip())

                self.assertTrue(definition.asset_type.strip())

                self.assertRegex(
                    definition.business_type_code,
                    r"^\d{2}$",
                )

                self.assertTrue(definition.grade_options)

                self.assertTrue(
                    set(definition.grade_options).issubset(
                        {
                            "A",
                            "B",
                            "C",
                            "D",
                        }
                    )
                )

                self.assertIs(
                    get_engineering_form_definition(definition.form_code),
                    definition,
                )

    def test_registry_identity_values_are_unique(
        self,
    ):
        definitions = get_engineering_form_definitions()

        for attribute_name in (
            "form_code",
            "form_number",
            "business_type_code",
        ):
            with self.subTest(
                attribute=attribute_name,
            ):
                values = [
                    getattr(
                        definition,
                        attribute_name,
                    )
                    for definition in definitions
                ]

                self.assertEqual(
                    len(values),
                    len(set(values)),
                )

    def test_migrated_forms_are_not_in_legacy_business_code_map(
        self,
    ):
        for definition in get_engineering_form_definitions():
            with self.subTest(
                form_code=(definition.form_code),
            ):
                self.assertNotIn(
                    definition.form_code,
                    LEGACY_ENGINEERING_TYPE_CODES,
                )

    def test_migrated_business_codes_come_from_definitions(
        self,
    ):
        expected = (
            (
                FORM_2_5,
                "05",
            ),
            (
                FORM_2_6,
                "06",
            ),
        )

        for (
            definition,
            expected_code,
        ) in expected:
            with self.subTest(
                form_code=(definition.form_code),
            ):
                self.assertEqual(
                    get_engineering_type_code(definition.form_code),
                    definition.business_type_code,
                )

                self.assertEqual(
                    get_engineering_type_code(definition.form_code),
                    expected_code,
                )

    def test_legacy_business_codes_are_preserved(
        self,
    ):
        expected = {
            "form_2_1": "01",
            "form_2_2": "02",
            "form_2_3": "03",
            "form_2_4": "04",
        }

        self.assertEqual(
            LEGACY_ENGINEERING_TYPE_CODES,
            expected,
        )

        for (
            form_code,
            expected_code,
        ) in expected.items():
            with self.subTest(
                form_code=form_code,
            ):
                self.assertEqual(
                    get_engineering_type_code(form_code),
                    expected_code,
                )

    def test_unknown_form_code_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "暂不支持调查表",
        ):
            get_engineering_type_code("form_2_99")


if __name__ == "__main__":
    unittest.main()
