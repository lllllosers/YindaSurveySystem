import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class UiTerminologyContractTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(
            encoding="utf-8"
        )

    def test_current_survey_batch_wording_is_consistent(self):
        task_page = self._read(
            "src/pages/survey_task_page.py"
        )
        list_page = self._read(
            "src/pages/components/"
            "engineering_survey_list_page.py"
        )
        asset_page = self._read(
            "src/pages/engineering_asset_page.py"
        )
        project_batch = self._read(
            "src/pages/project_batch_page.py"
        )

        self.assertNotIn(
            '"当前批次："',
            task_page,
        )
        self.assertNotIn(
            "当前批次录入管理",
            list_page,
        )
        self.assertNotIn(
            "当前批次共",
            list_page,
        )
        self.assertNotIn(
            "本批次",
            asset_page,
        )
        self.assertNotIn(
            "自动设为当前批次",
            project_batch,
        )

        self.assertIn(
            '"当前调查批次："',
            task_page,
        )
        self.assertIn(
            "当前调查批次",
            asset_page,
        )

    def test_task_workflow_uses_business_terms(self):
        issue_page = self._read(
            "src/pages/survey_task_page.py"
        )
        receive_page = self._read(
            "src/pages/survey_task_receive_page.py"
        )
        receive_panel = self._read(
            "src/pages/components/"
            "survey_task_receive_panel.py"
        )

        self.assertNotIn(
            "任务下发用于",
            issue_page,
        )
        self.assertNotIn(
            "下发的调查任务包",
            receive_page,
        )
        self.assertNotIn(
            "项目 / 批次：",
            receive_panel,
        )

        self.assertIn(
            "任务分发用于",
            issue_page,
        )
        self.assertIn(
            "选择并接收任务包",
            receive_panel,
        )
        self.assertIn(
            "项目/批次：",
            receive_panel,
        )

    def test_result_receive_uses_current_module_name(self):
        receive_panel = self._read(
            "src/pages/components/"
            "survey_result_receive_panel.py"
        )

        self.assertNotIn(
            "返回工程台账、数据查询或成果导出时",
            receive_panel,
        )
        self.assertIn(
            "返回工程台账、数据查询或成果提交时",
            receive_panel,
        )

    def test_record_status_labels_use_record_status_vocabulary(self):
        home_page = self._read(
            "src/pages/home_page.py"
        )
        query_page = self._read(
            "src/pages/data_query_page.py"
        )
        list_page = self._read(
            "src/pages/components/"
            "engineering_survey_list_page.py"
        )

        self.assertIn(
            "录入完成",
            home_page,
        )
        self.assertIn(
            "录入完成",
            query_page,
        )
        self.assertIn(
            "录入完成",
            list_page,
        )

    def test_terminology_document_exists(self):
        path = (
            PROJECT_ROOT
            / "docs"
            / "07_术语与界面文案规范.md"
        )

        self.assertTrue(
            path.exists()
        )

        text = path.read_text(
            encoding="utf-8"
        )

        for term in (
            "当前调查批次",
            "项目/批次",
            "任务分发",
            "任务接收",
            "成果提交",
            "成果接收",
            "录入完成",
        ):
            self.assertIn(
                term,
                text,
            )


if __name__ == "__main__":
    unittest.main()
