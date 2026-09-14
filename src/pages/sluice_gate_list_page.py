from database import (
    delete_sluice_gate_record,
    get_sluice_gate_records,
)
from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)
from services.sluice_gate_export import (
    export_sluice_gate_original_form,
)


class SluiceGateListPage(
    EngineeringSurveyListPage,
):
    """
    附表2.2水闸当前批次调查列表。

    公共列表行为由
    EngineeringSurveyListPage 提供。

    本类只保留附表2.2自己的：
    - 专属数据库查询；
    - 专属删除接口；
    - 表格显示；
    - 正式原表导出函数。
    """

    FORM_CODE = "form_2_2"

    PAGE_TITLE = "附表2.2 水闸工程状况调查记录"

    NEW_BUTTON_TEXT = "新增水闸调查"

    KEYWORD_PLACEHOLDER = "业务编号 / 工程名称 / 桩号"

    POSITION_LABEL = "桩号"

    TABLE_HEADERS = (
        "业务编号",
        "工程名称",
        "基层处",
        "水管所",
        "渠系",
        "桩号",
        "设计流量",
        "状态",
        "修改时间",
    )

    TABLE_WIDTHS = (
        150,
        180,
        140,
        140,
        160,
        110,
        100,
        90,
        160,
    )

    # 保持原2.2列表统计方式：
    # 当前批次列表仅显示录入进度。
    SHOW_GRADE_STATISTICS = False

    EXPORT_FILENAME_PREFIX = "附表2.2_水闸工程状况调查表"

    EXPORT_FALLBACK_ASSET_NAME = "水闸"

    def _load_records(self):
        """
        暂时继续使用附表2.2现有专属查询。

        本次只统一列表层，
        不同时修改数据库访问层。
        """

        current_context = self.current_context

        if current_context is None:
            return []

        return get_sluice_gate_records(
            project_id=(current_context["project_id"]),
            survey_batch_id=(current_context["batch_id"]),
        )

    def _keyword_values(
        self,
        record,
    ):
        return [
            record["business_code"],
            record["asset_name"],
            record["stake"],
        ]

    def _position_text(
        self,
        record,
    ):
        return str(record["stake"] or "")

    def _build_table_values(
        self,
        record,
    ):
        status_text = {
            "draft": "草稿",
            "completed": "录入完成",
        }.get(
            record["record_status"],
            record["record_status"],
        )

        design_flow = record["design_flow"]

        if design_flow is None:
            design_flow_text = ""
        else:
            design_flow_text = str(design_flow)

        return [
            record["business_code"],
            record["asset_name"],
            record["department_name"],
            record["office_name"],
            record["canal_name"],
            record["stake"],
            design_flow_text,
            status_text,
            record["updated_at"],
        ]

    def _delete_record(
        self,
        survey_record_id,
    ):
        return delete_sluice_gate_record(int(survey_record_id))

    def _export_original_form(
        self,
        survey_record_id,
        file_path,
    ):
        return export_sluice_gate_original_form(
            survey_record_id=(survey_record_id),
            file_path=file_path,
        )
