import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import (
    QApplication,
    QLabel,
)

from forms.engineering.models import (
    FieldDefinition,
)
from forms.engineering.registry import (
    get_engineering_form_definitions,
)
from forms.engineering.value_normalizers import (
    normalize_concrete_strength,
    normalize_structure_grade,
)
from pages.components.engineering_field_runtime import (
    create_engineering_field_runtime,
)
from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)
from pages.survey_page import (
    SurveyPage,
)


class EngineeringDomainInputsTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_structure_grade_normalization(
        self,
    ):
        cases = {
            "3": "3级",
            "3级": "3级",
            " 3 级 ": "3级",
            4: "4级",
            "03": "3级",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(
                    normalize_structure_grade(raw),
                    expected,
                )

    def test_concrete_strength_normalization(
        self,
    ):
        cases = {
            "30": "C30",
            "c30": "C30",
            "C30": "C30",
            " c 30 ": "C30",
            25: "C25",
            "030": "C30",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(
                    normalize_concrete_strength(raw),
                    expected,
                )

    def test_invalid_domain_values_are_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "建筑物等级",
        ):
            normalize_structure_grade(
                "三级"
            )

        with self.assertRaisesRegex(
            ValueError,
            "混凝土强度",
        ):
            normalize_concrete_strength(
                "M30"
            )

    def test_structure_grade_runtime_stores_canonical_value(
        self,
    ):
        runtime = (
            create_engineering_field_runtime(
                FieldDefinition(
                    key="structure_grade",
                    label="建筑物等级",
                    input_type="structure_grade",
                )
            )
        )

        try:
            runtime.widget.setText("3")

            self.assertEqual(
                runtime.get_value(),
                "3级",
            )

            runtime.set_value(
                "04级"
            )

            self.assertEqual(
                runtime.widget.text(),
                "4级",
            )

            runtime.clear()

            self.assertTrue(
                runtime.is_blank()
            )

        finally:
            runtime.widget.deleteLater()

    def test_concrete_strength_runtime_stores_canonical_value(
        self,
    ):
        runtime = (
            create_engineering_field_runtime(
                FieldDefinition(
                    key="concrete_strength",
                    label="混凝土强度",
                    input_type="concrete_strength",
                )
            )
        )

        try:
            runtime.widget.setText(
                "c30"
            )

            self.assertEqual(
                runtime.get_value(),
                "C30",
            )

            runtime.set_value(
                "40"
            )

            self.assertEqual(
                runtime.widget.text(),
                "C40",
            )

        finally:
            runtime.widget.deleteLater()

    def test_registered_special_fields_use_domain_input_types(
        self,
    ):
        structure_count = 0
        strength_count = 0

        for definition in (
            get_engineering_form_definitions()
        ):
            for field in definition.fields:
                if (
                    field.label
                    == "建筑物等级"
                ):
                    structure_count += 1

                    self.assertEqual(
                        field.input_type,
                        "structure_grade",
                    )

                if field.label in (
                    "混凝土强度",
                    "钢筋混凝土强度",
                ):
                    strength_count += 1

                    self.assertEqual(
                        field.input_type,
                        "concrete_strength",
                    )

        self.assertGreater(
            structure_count,
            0,
        )
        self.assertGreater(
            strength_count,
            0,
        )

    def test_engineering_home_has_no_registry_implementation_note(
        self,
    ):
        with patch.object(
            EngineeringSurveyListPage,
            "load_data",
            return_value=None,
        ):
            page = SurveyPage()

        try:
            texts = {
                label.text()
                for label
                in page.engineering_home_page
                .findChildren(QLabel)
            }

            self.assertFalse(
                any(
                    "Registry" in text
                    or "自动生成" in text
                    for text in texts
                )
            )

        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
