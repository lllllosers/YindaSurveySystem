import re
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

SRC_DIR = (
    PROJECT_ROOT
    / "src"
)

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


class Stage45ATaskDistributionUIContractTestCase(
    unittest.TestCase,
):
    def test_page_wires_hierarchical_task_services(
        self,
    ):
        path = (
            SRC_DIR
            / "pages"
            / "survey_task_page.py"
        )

        source = path.read_text(
            encoding="utf-8"
        )

        required = (
            "export_child_survey_task_package",
            "get_current_task_workspace",
            "_load_department_scopes",
            "_load_parent_workspace_scopes",
            "ChildSurveyTaskExportRequest",
        )

        for token in required:
            self.assertIn(
                token,
                source,
            )

        # 不依赖源码换行/缩进格式，只验证字典契约中确实
        # 存在 department / water_office 两种 target_unit_type。
        self.assertRegex(
            source,
            re.compile(
                r'["\']target_unit_type["\']'
                r'\s*:\s*'
                r'\(?\s*'
                r'["\']department["\']',
                re.MULTILINE,
            ),
        )

        self.assertRegex(
            source,
            re.compile(
                r'["\']target_unit_type["\']'
                r'\s*:\s*'
                r'\(?\s*'
                r'["\']water_office["\']',
                re.MULTILINE,
            ),
        )


if __name__ == "__main__":
    unittest.main()
