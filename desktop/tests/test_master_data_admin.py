import gc
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import database
from services.application_bootstrap import initialize_application_database
from services.master_data_admin import (
    get_canal_sort_order_map,
    get_organization_sort_order_map,
)


class MasterDataAdminTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)
        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH
        database.DATA_DIR = self.temp_root / "local_data"
        database.DB_PATH = database.DATA_DIR / "master_admin.db"
        initialize_application_database()

    def tearDown(self):
        gc.collect()
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        self.temp_directory.cleanup()

    def test_official_sort_orders_are_available(self):
        organization_orders = get_organization_sort_order_map()
        canal_orders = get_canal_sort_order_map()
        self.assertEqual(len(organization_orders), 25)
        self.assertEqual(len(canal_orders), 68)
        self.assertTrue(any(value > 0 for value in organization_orders.values()))
        self.assertTrue(any(value > 0 for value in canal_orders.values()))


if __name__ == "__main__":
    unittest.main()
