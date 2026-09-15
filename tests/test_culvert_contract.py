import gc
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


import database

from services.business_code import (
    get_engineering_type_code,
)

from services.culvert_evaluation import (
    CULVERT_EVALUATION_ITEMS,
)


class CulvertContractTestCase(unittest.TestCase):
    """
    附表2.6涵洞（暗涵）
    A0/B1表单合同回归测试。
    """

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()

        self.temp_data_dir = Path(self.temp_directory.name) / "local_data"

        self.temp_db_path = self.temp_data_dir / "test_culvert_contract.db"

        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_data_dir
        database.DB_PATH = self.temp_db_path

        database.init_database()
        database.create_initial_forms()

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

    def test_form_metadata_and_business_type_code(self):
        form_version = database.get_current_form_version("form_2_6")

        self.assertIsNotNone(form_version)

        self.assertEqual(
            get_engineering_type_code("form_2_6"),
            "06",
        )

        with database.get_connection() as connection:
            form = connection.execute(
                """
                SELECT
                    form_code,
                    form_number,
                    form_name,
                    series,
                    record_type,
                    asset_type,
                    sort_order
                FROM form_definitions
                WHERE form_code = ?
                """,
                ("form_2_6",),
            ).fetchone()

        self.assertIsNotNone(form)

        assert form is not None

        self.assertEqual(
            form["form_number"],
            "2.6",
        )

        self.assertEqual(
            form["form_name"],
            "涵洞（暗涵）工程状况调查表",
        )

        self.assertEqual(
            form["series"],
            "series_2",
        )

        self.assertEqual(
            form["record_type"],
            "engineering",
        )

        self.assertEqual(
            form["asset_type"],
            "culvert",
        )

        self.assertEqual(
            int(form["sort_order"]),
            206,
        )

    def test_evaluation_contract(self):
        self.assertEqual(
            len(CULVERT_EVALUATION_ITEMS),
            11,
        )

        expected_categories = (
            ["水力条件"] * 4 + ["结构变形"] * 2 + ["结构破损"] * 4 + ["地基基础"]
        )

        self.assertEqual(
            [item["category"] for item in CULVERT_EVALUATION_ITEMS],
            expected_categories,
        )

        expected_item_names = [
            "进、出口流态",
            "进、出口水位",
            "过流能力",
            "冲淤情况",
            "洞身衬砌结构变形",
            "其它部位结构变形",
            "洞身结构",
            "其它结构",
            "混凝土碳化深度",
            "混凝土强度",
            "地基基础",
        ]

        self.assertEqual(
            [item["item_name"] for item in CULVERT_EVALUATION_ITEMS],
            expected_item_names,
        )

        for item in CULVERT_EVALUATION_ITEMS:
            self.assertEqual(
                set(item["standards"].keys()),
                {
                    "A",
                    "B",
                    "C",
                    "D",
                },
            )

        # 正式源疑似文字问题必须原样保留，
        # 不允许开发过程中被“顺手修正”。
        self.assertTrue(CULVERT_EVALUATION_ITEMS[1]["standards"]["C"].startswith("②"))

        carbonation = CULVERT_EVALUATION_ITEMS[8]["standards"]

        self.assertEqual(
            carbonation["A"],
            carbonation["B"],
        )

        self.assertIn(
            "剥蚀脱离",
            CULVERT_EVALUATION_ITEMS[6]["standards"]["D"],
        )


if __name__ == "__main__":
    unittest.main()
