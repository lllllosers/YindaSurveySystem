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


from services.engineering_numbering_finalization import (
    ERROR,
    WARNING,
    EngineeringNumberingFinalizationIssue,
    EngineeringNumberingFinalizationPreview,
)


class NumberingFinalizationUserMessagesTestCase(
    unittest.TestCase,
):
    def test_preview_hides_internal_issue_codes(
        self,
    ):
        preview = EngineeringNumberingFinalizationPreview(
            project_id=1,
            survey_batch_id=1,
            total_assets=2,
            group_count=1,
            changed_code_count=0,
            already_final_count=0,
            provisional_count=2,
            errors=(
                EngineeringNumberingFinalizationIssue(
                    severity=ERROR,
                    code="LINED_SECTION_OVERLAP",
                    message=(
                        "检测到同一渠系中有两个"
                        "防渗衬砌渠段范围重叠。"
                    ),
                    engineering_asset_id=8,
                ),
            ),
            warnings=(
                EngineeringNumberingFinalizationIssue(
                    severity=WARNING,
                    code="LINED_SECTION_GAP",
                    message=(
                        "检测到两个渠段之间存在空档。"
                    ),
                ),
            ),
        )

        text = preview.format_text()

        self.assertIn(
            "需要先处理",
            text,
        )
        self.assertIn(
            "请确认以下情况",
            text,
        )
        self.assertIn(
            "防渗衬砌渠段范围重叠",
            text,
        )
        self.assertIn(
            "记录ID：8",
            text,
        )

        self.assertNotIn(
            "LINED_SECTION_OVERLAP",
            text,
        )
        self.assertNotIn(
            "LINED_SECTION_GAP",
            text,
        )


if __name__ == "__main__":
    unittest.main()
