import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ResultPackageWordingContractTestCase(unittest.TestCase):
    def test_existing_result_package_button_uses_business_wording(self):
        source = (
            PROJECT_ROOT
            / "src/pages/components/survey_result_package_panel.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn(
            '"检查已有 .ydresult"',
            source,
        )
        self.assertIn(
            '"检查已有成果包"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
