import gc
import tempfile
import time
import unittest
from pathlib import Path

import database

from forms.engineering.persistence import (
    complete_engineering_record,
    get_engineering_record,
)


def build_saved_engineering_payload(
    definition,
    survey_record_id,
):
    """
    根据数据库中已经保存的记录，
    重建 framework completion 所需 payload。

    用于 workflow 测试：
    - 测试可以先直接准备数据库状态；
    - 完成调查时仍然必须经过
      EngineeringFormDefinition +
      generic validation +
      generic persistence。
    """

    record = get_engineering_record(
        definition,
        survey_record_id=(
            survey_record_id
        ),
    )

    if record is None:
        raise ValueError(
            "没有找到该调查记录。"
        )

    inspections = (
        database.get_inspection_results(
            survey_record_id
        )
    )

    if (
        definition.position.kind
        == "point"
    ):
        position = {
            "kind": "point",
            "single_stake_text": (
                record[
                    "single_stake_text"
                ]
            ),
            "single_stake_value": (
                record[
                    "single_stake_value"
                ]
            ),
        }

    elif (
        definition.position.kind
        == "range"
    ):
        position = {
            "kind": "range",
            "start_stake_text": (
                record[
                    "start_stake_text"
                ]
            ),
            "start_stake_value": (
                record[
                    "start_stake_value"
                ]
            ),
            "end_stake_text": (
                record[
                    "end_stake_text"
                ]
            ),
            "end_stake_value": (
                record[
                    "end_stake_value"
                ]
            ),
        }

    else:
        raise ValueError(
            "暂不支持的工程位置类型："
            f"{definition.position.kind}"
        )

    return {
        "asset_name": (
            record["asset_name"]
        ),
        "record_data": (
            record["record_data"]
            or {}
        ),
        "position": position,
        "inspection_results": [
            dict(row)
            for row in inspections
        ],
        "survey_date": (
            record["survey_date"]
        ),
        "overall_grade": (
            record["overall_grade"]
        ),
        "survey_comment": (
            record["survey_comment"]
        ),
    }


def complete_saved_engineering_record(
    definition,
    survey_record_id,
):
    """
    使用正式 framework
    完成一条已经保存的工程调查记录。
    """

    payload = (
        build_saved_engineering_payload(
            definition,
            survey_record_id,
        )
    )

    return complete_engineering_record(
        definition,
        survey_record_id=(
            survey_record_id
        ),
        payload=payload,
    )


class EngineeringWorkflowTestCaseBase(
    unittest.TestCase,
):
    """
    附表2工程调查 workflow 测试公共基类。

    只负责建立测试所需的基础上下文：
    - 独立临时 SQLite 数据库；
    - 项目；
    - 调查批次；
    - 基层处；
    - 水管所；
    - 渠系；
    - 当前表单版本。

    不负责：
    - 各附表正式字段；
    - 工程身份规则；
    - 完成调查规则；
    - 分项评价内容；
    - Excel 坐标；
    - 各附表自己的业务断言。
    """

    FORM_CODE = None

    TEST_DB_FILENAME = (
        "test_engineering_workflow.db"
    )

    PROJECT_NAME = (
        "工程调查自动测试项目"
    )

    PROJECT_SHORT_NAME = (
        "工程测试"
    )

    BATCH_NAME = (
        "工程调查自动测试批次"
    )

    BATCH_CODE = (
        "ENGINEERING_TEST"
    )

    BATCH_START_DATE = None
    BATCH_END_DATE = None

    DEPARTMENT_NAME = (
        "测试基层处"
    )

    DEPARTMENT_CODE = "01"

    OFFICE_NAME = "测试水管所"
    OFFICE_CODE = "01"

    CANAL_NAME = "测试干渠"
    CANAL_LEVEL = "01"

    CANAL_DESCRIPTION = (
        "自动测试"
    )

    def setUp(
        self,
    ):
        super().setUp()

        if not self.FORM_CODE:
            raise ValueError(
                "工程调查 workflow "
                "测试必须设置 FORM_CODE。"
            )

        # =====================================================
        # 独立临时数据库
        # =====================================================

        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        self.temp_data_dir = (
            Path(
                self.temp_directory.name
            )
            / "local_data"
        )

        self.temp_db_path = (
            self.temp_data_dir
            / self.TEST_DB_FILENAME
        )

        self.original_data_dir = (
            database.DATA_DIR
        )

        self.original_db_path = (
            database.DB_PATH
        )

        database.DATA_DIR = (
            self.temp_data_dir
        )

        database.DB_PATH = (
            self.temp_db_path
        )

        database.init_database()

        database.create_initial_forms()

        # =====================================================
        # 项目
        # =====================================================

        project_result = (
            database.create_project(
                name=self.PROJECT_NAME,
                short_name=(
                    self.PROJECT_SHORT_NAME
                ),
            )
        )

        self.project_id = int(
            project_result[
                "project_id"
            ]
        )

        # =====================================================
        # 调查批次
        # =====================================================

        batch_result = (
            database.create_survey_batch(
                project_id=(
                    self.project_id
                ),
                batch_name=(
                    self.BATCH_NAME
                ),
                batch_code=(
                    self.BATCH_CODE
                ),
                start_date=(
                    self.BATCH_START_DATE
                ),
                end_date=(
                    self.BATCH_END_DATE
                ),
            )
        )

        self.batch_id = int(
            batch_result[
                "batch_id"
            ]
        )

        # =====================================================
        # 基层处
        # =====================================================

        department_id = (
            database
            .create_organization_unit(
                name=(
                    self.DEPARTMENT_NAME
                ),
                unit_type=(
                    "department"
                ),
                business_code=(
                    self.DEPARTMENT_CODE
                ),
            )
        )

        self.assertIsNotNone(
            department_id
        )

        assert (
            department_id
            is not None
        )

        self.department_id = int(
            department_id
        )

        # =====================================================
        # 水管所
        # =====================================================

        office_id = (
            database
            .create_organization_unit(
                name=self.OFFICE_NAME,
                unit_type=(
                    "water_office"
                ),
                business_code=(
                    self.OFFICE_CODE
                ),
                parent_id=(
                    self.department_id
                ),
            )
        )

        self.assertIsNotNone(
            office_id
        )

        assert office_id is not None

        self.office_id = int(
            office_id
        )

        # =====================================================
        # 渠系
        # =====================================================

        canal_id = (
            database.create_canal_unit(
                name=self.CANAL_NAME,
                canal_level=(
                    self.CANAL_LEVEL
                ),
                parent_id=None,
                organization_unit_id=(
                    self.office_id
                ),
                description=(
                    self.CANAL_DESCRIPTION
                ),
            )
        )

        self.assertIsNotNone(
            canal_id
        )

        assert canal_id is not None

        self.canal_id = int(
            canal_id
        )

        # =====================================================
        # 当前表单版本
        # =====================================================

        self.form_version = (
            database
            .get_current_form_version(
                self.FORM_CODE
            )
        )

        self.assertIsNotNone(
            self.form_version
        )

        assert (
            self.form_version
            is not None
        )

    def tearDown(
        self,
    ):
        database.DATA_DIR = (
            self.original_data_dir
        )

        database.DB_PATH = (
            self.original_db_path
        )

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

        super().tearDown()
