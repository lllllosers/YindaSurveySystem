import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class VisualPolishPassOneContractTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(encoding="utf-8")

    def test_theme_uses_native_combo_box_arrow(self):
        source = self._read("src/styles/app_theme.py")
        self.assertIn("VISUAL_POLISH_PASS_QSS", source)
        self.assertIn("NATIVE_COMBO_ARROW", source)
        self.assertNotIn("QComboBox::down-arrow", source)

    def test_survey_page_uses_compact_entry_styling(self):
        source = self._read("src/pages/survey_page.py")
        self.assertIn('setObjectName("surveyEntrySectionTitle")', source)
        self.assertIn('setObjectName("surveyEntryLead")', source)
        self.assertIn('setObjectName("surveyEntryPrimary")', source)
        self.assertIn('setObjectName("surveyEntrySecondary")', source)
        self.assertIn("使用提示", source)
        self.assertIn("工程现状调查用于附表2系列录入管理", source)


if __name__ == "__main__":
    unittest.main()
