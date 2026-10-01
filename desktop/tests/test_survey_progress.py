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
from services.survey_progress import (
    get_engineering_progress,
)


class SurveyProgressTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH

        database.DATA_DIR = (
            Path(self.temp_directory.name)
            / "local_data"
        )
        database.DB_PATH = (
            database.DATA_DIR
            / "test_progress.db"
        )

        database.init_database()
        database.create_initial_forms()

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path

        gc.collect()
        time.sleep(0.05)
        self.temp_directory.cleanup()

    def test_progress_aggregates_department_and_office(self):
        with database.get_connection() as connection:
            project_id = int(
                connection.execute(
                    '''
                    INSERT INTO projects (
                        name,
                        short_name,
                        status
                    )
                    VALUES (
                        '测试项目',
                        '测试',
                        'active'
                    )
                    '''
                ).lastrowid
            )

            batch_id = int(
                connection.execute(
                    '''
                    INSERT INTO survey_batches (
                        project_id,
                        batch_name,
                        batch_code,
                        status
                    )
                    VALUES (
                        ?,
                        '测试批次',
                        'B001',
                        'active'
                    )
                    ''',
                    (project_id,),
                ).lastrowid
            )

            department_id = int(
                connection.execute(
                    '''
                    INSERT INTO organization_units (
                        name,
                        unit_type,
                        status,
                        sort_order
                    )
                    VALUES (
                        '测试处',
                        'department',
                        'active',
                        100
                    )
                    '''
                ).lastrowid
            )

            office_1 = int(
                connection.execute(
                    '''
                    INSERT INTO organization_units (
                        parent_id,
                        name,
                        unit_type,
                        status,
                        sort_order
                    )
                    VALUES (
                        ?,
                        '一所',
                        'water_office',
                        'active',
                        101
                    )
                    ''',
                    (department_id,),
                ).lastrowid
            )

            office_2 = int(
                connection.execute(
                    '''
                    INSERT INTO organization_units (
                        parent_id,
                        name,
                        unit_type,
                        status,
                        sort_order
                    )
                    VALUES (
                        ?,
                        '二所',
                        'water_office',
                        'active',
                        102
                    )
                    ''',
                    (department_id,),
                ).lastrowid
            )

            form_version_id = int(
                connection.execute(
                    '''
                    SELECT fv.id
                    FROM form_versions AS fv
                    JOIN form_definitions AS fd
                      ON fd.id
                        = fv.form_definition_id
                    WHERE fd.series
                        = 'series_2'
                    ORDER BY
                        fd.sort_order,
                        fv.id
                    LIMIT 1
                    '''
                ).fetchone()["id"]
            )

            records = (
                (office_1, "completed", "A"),
                (office_1, "completed", "C"),
                (office_1, "draft", None),
                (office_2, "draft", None),
            )

            for (
                office_id,
                status,
                grade,
            ) in records:
                connection.execute(
                    '''
                    INSERT INTO survey_records (
                        project_id,
                        survey_batch_id,
                        form_version_id,
                        record_type,
                        organization_unit_id,
                        overall_grade,
                        record_status
                    )
                    VALUES (
                        ?,
                        ?,
                        ?,
                        'engineering',
                        ?,
                        ?,
                        ?
                    )
                    ''',
                    (
                        project_id,
                        batch_id,
                        form_version_id,
                        office_id,
                        grade,
                        status,
                    ),
                )

        result = get_engineering_progress(
            project_id,
            batch_id,
        )

        self.assertEqual(
            result["total_records"],
            4,
        )
        self.assertEqual(
            result["completed_records"],
            2,
        )
        self.assertEqual(
            result["draft_records"],
            2,
        )
        self.assertAlmostEqual(
            result["completion_rate"],
            50.0,
        )
        self.assertEqual(
            result["grades"],
            {
                "A": 1,
                "B": 0,
                "C": 1,
                "D": 0,
            },
        )

        department = (
            result["departments"][0]
        )

        self.assertEqual(
            department["department_name"],
            "测试处",
        )
        self.assertEqual(
            department["completed_records"],
            2,
        )
        self.assertEqual(
            len(department["offices"]),
            2,
        )
        self.assertAlmostEqual(
            department[
                "offices"
            ][0][
                "completion_rate"
            ],
            100.0 * 2 / 3,
        )
        self.assertEqual(
            department[
                "offices"
            ][1][
                "completed_records"
            ],
            0,
        )


if __name__ == "__main__":
    unittest.main()
