import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class EngineeringLedgerDensityContractTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(encoding="utf-8")

    def test_database_returns_current_survey_date(self):
        source = self._read("src/database.py")
        self.assertIn(") AS survey_date", source)

    def test_ledger_shows_grade_and_survey_date(self):
        source = self._read("src/pages/engineering_asset_page.py")

        self.assertIn('"工程状况类别"', source)
        self.assertIn('"调查时间"', source)
        self.assertIn('asset["overall_grade"]', source)
        self.assertIn('asset["survey_date"]', source)
        self.assertIn(
            "self.table.horizontalHeader().setStretchLastSection(True)",
            source,
        )


if __name__ == "__main__":
    unittest.main()
