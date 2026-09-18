import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from services.engineering_result_preflight import (
    inspect_batch_export_plan,
)


def _definition():
    return SimpleNamespace(
        form_code="form_2_2",
        evaluation_items=(
            {
                "category": "闸门",
                "item_name": "闸门状况",
                "item_code": "gate_body",
            },
        ),
    )


def _record(
    *,
    survey_record_id=1,
    business_code="1-01-03-02-001",
):
    return {
        "survey_record_id": (
            survey_record_id
        ),
        "business_code": business_code,
        "form_code": "form_2_2",
        "asset_name": "测试水闸",
        "canal_name": "测试支渠",
        "engineering_position": (
            "K1+000"
        ),
    }


def _plan(
    records,
):
    return SimpleNamespace(
        records=tuple(records),
        groups=(
            SimpleNamespace(
                definition=_definition(),
            ),
        ),
    )


class EngineeringResultPreflightTestCase(
    unittest.TestCase,
):
    @patch(
        "services.engineering_result_preflight."
        "get_survey_media",
        return_value=[],
    )
    def test_no_media_is_warning_not_error(
        self,
        mock_get_media,
    ):
        report = inspect_batch_export_plan(
            _plan([_record()])
        )

        self.assertEqual(
            report.error_count,
            0,
        )
        self.assertEqual(
            report.warning_count,
            1,
        )
        self.assertTrue(
            report.can_export
        )

        self.assertEqual(
            report.issues[0].code,
            "NO_MEDIA",
        )

    @patch(
        "services.engineering_result_preflight."
        "get_survey_media"
    )
    def test_missing_file_blocks_export(
        self,
        mock_get_media,
    ):
        mock_get_media.return_value = [
            {
                "id": 7,
                "media_uid": "uid-7",
                "media_kind": "photo",
                "media_role": "overview",
                "part_name": "闸室",
                "item_code": None,
                "sequence_no": 1,
                "original_filename": (
                    "missing.jpg"
                ),
                "absolute_path": Path(
                    "Z:/definitely-not-exist/"
                    "missing.jpg"
                ),
                "file_size": 10,
            }
        ]

        report = inspect_batch_export_plan(
            _plan([_record()])
        )

        self.assertEqual(
            report.error_count,
            1,
        )
        self.assertFalse(
            report.can_export
        )
        self.assertEqual(
            report.issues[0].code,
            "MISSING_MANAGED_FILE",
        )

    @patch(
        "services.engineering_result_preflight."
        "get_survey_media"
    )
    def test_missing_part_and_problem_link_are_warnings(
        self,
        mock_get_media,
    ):
        with tempfile.TemporaryDirectory() as temp:
            path = (
                Path(temp)
                / "managed.jpg"
            )
            path.write_bytes(b"image")

            mock_get_media.return_value = [
                {
                    "id": 1,
                    "media_uid": "uid-1",
                    "media_kind": "photo",
                    "media_role": "problem",
                    "part_name": None,
                    "item_code": None,
                    "sequence_no": 1,
                    "original_filename": (
                        "problem.jpg"
                    ),
                    "absolute_path": path,
                    "file_size": 5,
                }
            ]

            report = (
                inspect_batch_export_plan(
                    _plan([_record()])
                )
            )

        codes = {
            issue.code
            for issue in report.issues
        }

        self.assertEqual(
            report.error_count,
            0,
        )
        self.assertIn(
            "MISSING_PART_NAME",
            codes,
        )
        self.assertIn(
            "PROBLEM_WITHOUT_ITEM",
            codes,
        )

    @patch(
        "services.engineering_result_preflight."
        "get_survey_media"
    )
    def test_size_mismatch_is_error(
        self,
        mock_get_media,
    ):
        with tempfile.TemporaryDirectory() as temp:
            path = (
                Path(temp)
                / "managed.jpg"
            )
            path.write_bytes(b"12345")

            mock_get_media.return_value = [
                {
                    "id": 1,
                    "media_uid": "uid-1",
                    "media_kind": "photo",
                    "media_role": "overview",
                    "part_name": "闸室",
                    "item_code": None,
                    "sequence_no": 1,
                    "original_filename": (
                        "overview.jpg"
                    ),
                    "absolute_path": path,
                    "file_size": 999,
                }
            ]

            report = (
                inspect_batch_export_plan(
                    _plan([_record()])
                )
            )

        self.assertEqual(
            report.error_count,
            1,
        )
        self.assertEqual(
            report.issues[0].code,
            "FILE_SIZE_MISMATCH",
        )

    @patch(
        "services.engineering_result_preflight."
        "get_survey_media"
    )
    def test_duplicate_sequence_is_warning(
        self,
        mock_get_media,
    ):
        with tempfile.TemporaryDirectory() as temp:
            first = (
                Path(temp)
                / "one.jpg"
            )
            second = (
                Path(temp)
                / "two.jpg"
            )

            first.write_bytes(b"1")
            second.write_bytes(b"2")

            mock_get_media.return_value = [
                {
                    "id": 1,
                    "media_uid": "uid-1",
                    "media_kind": "photo",
                    "media_role": "detail",
                    "part_name": "闸门",
                    "item_code": "gate_body",
                    "sequence_no": 1,
                    "original_filename": (
                        "one.jpg"
                    ),
                    "absolute_path": first,
                    "file_size": 1,
                },
                {
                    "id": 2,
                    "media_uid": "uid-2",
                    "media_kind": "photo",
                    "media_role": "detail",
                    "part_name": "启闭机",
                    "item_code": None,
                    "sequence_no": 1,
                    "original_filename": (
                        "two.jpg"
                    ),
                    "absolute_path": second,
                    "file_size": 1,
                },
            ]

            report = (
                inspect_batch_export_plan(
                    _plan([_record()])
                )
            )

        codes = [
            issue.code
            for issue in report.issues
        ]

        self.assertIn(
            "DUPLICATE_SEQUENCE",
            codes,
        )
        self.assertEqual(
            report.error_count,
            0,
        )

    @patch(
        "services.engineering_result_preflight."
        "get_survey_media"
    )
    def test_duplicate_archive_path_is_error(
        self,
        mock_get_media,
    ):
        with tempfile.TemporaryDirectory() as temp:
            first = (
                Path(temp)
                / "one.jpg"
            )
            second = (
                Path(temp)
                / "two.jpg"
            )

            first.write_bytes(b"1")
            second.write_bytes(b"2")

            common = {
                "media_kind": "photo",
                "media_role": "detail",
                "part_name": "闸门",
                "item_code": "gate_body",
                "sequence_no": 1,
                "file_size": 1,
            }

            mock_get_media.return_value = [
                {
                    **common,
                    "id": 1,
                    "media_uid": "uid-1",
                    "original_filename": (
                        "one.jpg"
                    ),
                    "absolute_path": first,
                },
                {
                    **common,
                    "id": 2,
                    "media_uid": "uid-2",
                    "original_filename": (
                        "two.jpg"
                    ),
                    "absolute_path": second,
                },
            ]

            report = (
                inspect_batch_export_plan(
                    _plan([_record()])
                )
            )

        codes = {
            issue.code
            for issue in report.issues
        }

        self.assertIn(
            "DUPLICATE_ARCHIVE_PATH",
            codes,
        )
        self.assertFalse(
            report.can_export
        )

    @patch(
        "services.engineering_result_preflight."
        "get_survey_media"
    )
    def test_clean_media_passes_preflight(
        self,
        mock_get_media,
    ):
        with tempfile.TemporaryDirectory() as temp:
            path = (
                Path(temp)
                / "clean.jpg"
            )
            path.write_bytes(b"clean")

            mock_get_media.return_value = [
                {
                    "id": 1,
                    "media_uid": "uid-1",
                    "media_kind": "photo",
                    "media_role": "problem",
                    "part_name": "闸门",
                    "item_code": "gate_body",
                    "sequence_no": 1,
                    "original_filename": (
                        "clean.jpg"
                    ),
                    "absolute_path": path,
                    "file_size": 5,
                }
            ]

            report = (
                inspect_batch_export_plan(
                    _plan([_record()])
                )
            )

        self.assertEqual(
            report.error_count,
            0,
        )
        self.assertEqual(
            report.warning_count,
            0,
        )
        self.assertTrue(
            report.can_export
        )


if __name__ == "__main__":
    unittest.main()
