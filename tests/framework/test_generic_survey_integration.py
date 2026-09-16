import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


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

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)

from pages.survey_page import (
    ENGINEERING_SURVEY_FORMS,
    prepare_engineering_new_page,
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

    def test_all_forms_use_generic_production_page(
        self,
    ):
        definitions = (
            FORM_2_1,
            FORM_2_2,
            FORM_2_3,
            FORM_2_4,
            FORM_2_5,
            FORM_2_6,
        )

        self.assertEqual(
            tuple(
                item["form_code"]
                for item
                in ENGINEERING_SURVEY_FORMS
            ),
            tuple(
                definition.form_code
                for definition
                in definitions
            ),
        )

        for definition in definitions:
            with self.subTest(
                form_code=definition.form_code
            ):
                registration = next(
                    item
                    for item
                    in ENGINEERING_SURVEY_FORMS
                    if (
                        item["form_code"]
                        == definition.form_code
                    )
                )

                self.assertEqual(
                    registration[
                        "button_text"
                    ],
                    (
                        definition
                        .display_name
                        .removesuffix("表")
                    ),
                )

                page = registration[
                    "edit_page_factory"
                ]()

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

    def test_new_page_prefers_generic_initializer(
        self,
    ):
        page = Mock()

        page.initialize_new_record = Mock()
        page.prepare_new = Mock()

        prepare_engineering_new_page(
            page
        )

        (
            page
            .initialize_new_record
            .assert_called_once_with()
        )

        (
            page
            .prepare_new
            .assert_not_called()
        )

    def test_legacy_compatibility_path_still_works(
        self,
    ):
        class LegacyPage:
            def __init__(
                self,
            ):
                self.prepare_new = Mock()

        page = LegacyPage()

        prepare_engineering_new_page(
            page
        )

        (
            page
            .prepare_new
            .assert_called_once_with()
        )


if __name__ == "__main__":
    unittest.main()
