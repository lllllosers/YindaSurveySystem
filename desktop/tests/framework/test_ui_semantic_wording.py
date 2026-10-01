import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class UiSemanticWordingTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(encoding="utf-8")

    def test_channel_page_uses_channel_for_single_entity(self):
        source = self._read("src/pages/canal_page.py")

        for stale in (
            "请选择渠系",
            "选中的渠系已经不存在",
            "该渠系已有业务数据引用",
            "当前渠系尚未产生工程或调查数据",
            "渠系资料已更新",
            "渠系基础资料已永久删除",
            "请通过“管理范围”配置",
        ):
            self.assertNotIn(stale, source)

        for expected in (
            "请选择渠道",
            "选中的渠道已经不存在",
            "分管范围",
            "管理分管段",
        ):
            self.assertIn(expected, source)

    def test_home_metric_name_is_explicit(self):
        source = self._read("src/pages/home_page.py")
        self.assertNotIn("已录完成率", source)
        self.assertIn("已录记录完成率", source)

    def test_result_primary_action_uses_business_wording(self):
        source = self._read(
            "src/pages/components/survey_result_package_panel.py"
        )

        self.assertNotIn(
            '"导出当前范围 .ydresult"',
            source,
        )
        self.assertIn(
            '"生成调查成果包"',
            source,
        )

    def test_result_copy_uses_record_status_vocabulary(self):
        source = self._read(
            "src/pages/components/survey_result_package_panel.py"
        )
        self.assertNotIn("已完成工程调查记录", source)
        self.assertIn("录入完成", source)

    def test_stale_development_placeholder_is_removed(self):
        source = self._read(
            "src/pages/components/generic_engineering_survey_page.py"
        )
        self.assertNotIn(
            "完成调查将在下一阶段接入",
            source,
        )


if __name__ == "__main__":
    unittest.main()
