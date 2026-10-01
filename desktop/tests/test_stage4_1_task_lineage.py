import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from services.survey_task_lineage import (
    CURRENT_TASK_SCHEMA_VERSION,
    LEGACY_TASK_SCHEMA_VERSION,
    SUPPORTED_TASK_SCHEMA_VERSIONS,
    build_child_task_lineage,
    build_root_task_lineage,
    normalize_task_lineage,
)


class Stage41TaskLineageTestCase(
    unittest.TestCase,
):
    def test_supported_versions_include_v2_and_v3(self):
        self.assertEqual(
            CURRENT_TASK_SCHEMA_VERSION,
            "3.0",
        )
        self.assertEqual(
            LEGACY_TASK_SCHEMA_VERSION,
            "2.0",
        )
        self.assertEqual(
            SUPPORTED_TASK_SCHEMA_VERSIONS,
            frozenset({"2.0", "3.0"}),
        )

    def test_root_lineage_is_self_rooted(self):
        lineage = build_root_task_lineage(
            "task-root"
        )

        self.assertIsNone(
            lineage.parent_task_uid
        )
        self.assertEqual(
            lineage.root_task_uid,
            "task-root",
        )
        self.assertEqual(
            lineage.depth,
            0,
        )
        self.assertTrue(
            lineage.is_root
        )

    def test_legacy_v2_task_is_normalized_as_root(self):
        lineage = normalize_task_lineage(
            {
                "task_schema_version": "2.0",
                "task_uid": "legacy-task",
            },
            manifest={
                "task_schema_version": "2.0",
            },
        )

        self.assertIsNone(
            lineage.parent_task_uid
        )
        self.assertEqual(
            lineage.root_task_uid,
            "legacy-task",
        )
        self.assertEqual(
            lineage.depth,
            0,
        )

    def test_v3_root_lineage_must_match_manifest(self):
        task = {
            "task_schema_version": "3.0",
            "task_uid": "root-task",
            "lineage": {
                "parent_task_uid": None,
                "root_task_uid": "root-task",
                "depth": 0,
            },
        }

        lineage = normalize_task_lineage(
            task,
            manifest={
                "task_schema_version": "3.0",
                "parent_task_uid": None,
                "root_task_uid": "root-task",
                "task_depth": 0,
            },
        )

        self.assertTrue(
            lineage.is_root
        )

        with self.assertRaisesRegex(
            ValueError,
            "任务血缘不一致",
        ):
            normalize_task_lineage(
                task,
                manifest={
                    "task_schema_version": "3.0",
                    "parent_task_uid": "wrong",
                    "root_task_uid": "root-task",
                    "task_depth": 0,
                },
            )

    def test_child_lineage_is_derived_from_parent(self):
        child = build_child_task_lineage(
            task_uid="child-task",
            parent_task_uid="parent-task",
            root_task_uid="root-task",
            parent_depth=1,
        )

        self.assertEqual(
            child.parent_task_uid,
            "parent-task",
        )
        self.assertEqual(
            child.root_task_uid,
            "root-task",
        )
        self.assertEqual(
            child.depth,
            2,
        )
        self.assertFalse(
            child.is_root
        )


if __name__ == "__main__":
    unittest.main()
