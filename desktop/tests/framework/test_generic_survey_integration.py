import os
import sys
import unittest
from pathlib import Path


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
)

from forms.engineering.form_2_2 import (
    FORM_2_2,
)
from forms.engineering.form_2_3 import (
    FORM_2_3,
)
from forms.engineering.registry import (
    get_engineering_form_definitions,
)

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)


class GenericSurveyIntegrationTestCase(
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

    def test_all_registered_forms_build_generic_production_page(
        self,
    ):
        """
        Registry 是工程调查表唯一注册事实。

        每个已经注册的 EngineeringFormDefinition
        都必须能够直接构造统一生产录入页。
        """

        definitions = (
            get_engineering_form_definitions()
        )

        self.assertGreater(
            len(definitions),
            0,
        )

        for definition in definitions:
            with self.subTest(
                form_code=definition.form_code
            ):
                page = (
                    GenericEngineeringSurveyPage(
                        definition
                    )
                )

                try:
                    self.assertIsInstance(
                        page,
                        GenericEngineeringSurveyPage,
                    )

                    self.assertIs(
                        page.definition,
                        definition,
                    )

                finally:
                    page.deleteLater()

    def test_form_2_3_evaluation_note_is_rendered(
        self,
    ):
        page = (
            GenericEngineeringSurveyPage(
                FORM_2_3
            )
        )

        try:
            self.assertIsNotNone(
                page.evaluation_note_label
            )

            self.assertEqual(
                (
                    page
                    .evaluation_note_label
                    .text()
                ),
                FORM_2_3.evaluation_note,
            )

        finally:
            page.deleteLater()

    def test_form_without_note_does_not_create_note_label(
        self,
    ):
        page = (
            GenericEngineeringSurveyPage(
                FORM_2_2
            )
        )

        try:
            self.assertIsNone(
                page.evaluation_note_label
            )

        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
