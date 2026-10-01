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
)

from forms.engineering.registry import (
    get_engineering_form_definitions,
)

from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)

from pages.components.generic_engineering_list_page import (
    GenericEngineeringListPage,
)

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)

import pages.survey_page as survey_page_module
from pages.survey_page import (
    SurveyPage,
)


class SurveyPageRegistryTestCase(
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

    def test_survey_page_builds_engineering_pages_from_registry(
        self,
    ):
        with patch.object(
            EngineeringSurveyListPage,
            "load_data",
            return_value=None,
        ):
            page = SurveyPage()

        try:
            definitions = (
                get_engineering_form_definitions()
            )

            self.assertEqual(
                tuple(
                    page.engineering_pages.keys()
                ),
                tuple(
                    definition.form_code
                    for definition
                    in definitions
                ),
            )

            for definition in definitions:
                pages = (
                    page.engineering_pages[
                        definition.form_code
                    ]
                )

                self.assertIsInstance(
                    pages["list_page"],
                    GenericEngineeringListPage,
                )

                self.assertIs(
                    pages["list_page"].definition,
                    definition,
                )

                self.assertIsInstance(
                    pages["edit_page"],
                    GenericEngineeringSurveyPage,
                )

                self.assertIs(
                    pages["edit_page"].definition,
                    definition,
                )

        finally:
            page.deleteLater()

    def test_appendix1_reserved_entry_remains_visible(
        self,
    ):
        # Appendix 1 is outside the current production implementation scope,
        # but the visible reserved business entry must remain.
        from PySide6.QtWidgets import (
            QLabel,
            QPushButton,
        )

        with patch.object(
            EngineeringSurveyListPage,
            "load_data",
            return_value=None,
        ):
            page = SurveyPage()

        try:
            button_texts = {
                widget.text()
                for widget in page.findChildren(
                    QPushButton
                )
            }
            label_texts = {
                widget.text()
                for widget in page.findChildren(
                    QLabel
                )
            }

            self.assertIn(
                "灌区综合与水土资源调查（附表1系列·预留）",
                button_texts,
            )

            self.assertTrue(
                any(
                    "附表1.1～1.15业务入口已预留"
                    in value
                    for value in label_texts
                )
            )

            self.assertTrue(
                any(
                    "本版本暂不启用附表1软件录入"
                    in value
                    for value in label_texts
                )
            )

        finally:
            page.deleteLater()



if __name__ == "__main__":
    unittest.main()
