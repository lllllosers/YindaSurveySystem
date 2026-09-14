from database import (
    delete_lined_channel_section_record,
    get_lined_channel_section_records,
)
from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)
from services.lined_channel_export import (
    export_lined_channel_original_form,
)


class LinedChannelSectionListPage(
    EngineeringSurveyListPage,
):
    """
    附表2.1防渗衬砌渠道渠段
    当前批次调查列表。

    公共列表行为由
    EngineeringSurveyListPage 提供。

    本类只保留附表2.1自己的：
    - 专属数据库查询；
    - 专属删除接口；
    - 区间桩号查询和显示；
    - 表格显示；
    - 正式原表导出函数。
    """

    FORM_CODE = "form_2_1"

    PAGE_TITLE = "附表2.1 防渗衬砌渠道渠段" "工程状况调查记录"

    NEW_BUTTON_TEXT = "新增渠道渠段调查"

    KEYWORD_PLACEHOLDER = "业务编号 / 渠道名称 / 起止桩号"

    # 区间工程不显示“桩号”，
    # 删除确认统一显示为“渠段”。
    POSITION_LABEL = "渠段"

    TABLE_HEADERS = (
        "业务编号",
        "渠道名称",
        "基层处",
        "水管所",
        "渠系",
        "起始桩号",
        "终止桩号",
        "渠段长度(m)",
        "工程状况类别",
        "状态",
        "修改时间",
    )

    TABLE_WIDTHS = (
        150,
        180,
        130,
        130,
        160,
        110,
        110,
        110,
        110,
        90,
        160,
    )

    # 保持原2.1当前批次列表行为：
    # 只显示录入进度统计，
    # A/B/C/D成果统计由数据查询模块负责。
    SHOW_GRADE_STATISTICS = False

    EXPORT_FILENAME_PREFIX = "附表2.1_防渗衬砌渠道渠段" "工程状况调查表"

    EXPORT_FALLBACK_ASSET_NAME = "渠道渠段"

    # =========================================================
    # 数据
    # =========================================================

    def _load_records(self):
        """
        暂时继续使用附表2.1现有专属查询。

        本次只统一列表层，
        不同时修改数据库访问层。
        """

        current_context = self.current_context

        if current_context is None:
            return []

        return get_lined_channel_section_records(
            project_id=(current_context["project_id"]),
            survey_batch_id=(current_context["batch_id"]),
        )

    # =========================================================
    # 关键词
    # =========================================================

    def _keyword_values(
        self,
        record,
    ):
        return [
            record["business_code"],
            record["asset_name"],
            record["start_stake_text"],
            record["end_stake_text"],
        ]

    # =========================================================
    # 工程位置
    # =========================================================

    def _position_text(
        self,
        record,
    ):
        start_stake = str(record["start_stake_text"] or "")

        end_stake = str(record["end_stake_text"] or "")

        if start_stake and end_stake:
            return f"{start_stake} ～ {end_stake}"

        return start_stake or end_stake

    # =========================================================
    # 表格
    # =========================================================

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

        record_data = record.get("record_data") or {}

        section_length = record_data.get("section_length")

        if section_length is None:
            section_length_text = ""
        else:
            section_length_text = str(section_length)

        return [
            record["business_code"],
            record["asset_name"],
            record["department_name"],
            record["office_name"],
            record["canal_name"],
            record["start_stake_text"],
            record["end_stake_text"],
            section_length_text,
            record["overall_grade"] or "",
            status_text,
            record["updated_at"],
        ]

    # =========================================================
    # 删除
    # =========================================================

    def _delete_record(
        self,
        survey_record_id,
    ):
        return delete_lined_channel_section_record(int(survey_record_id))

    # =========================================================
    # 正式原表导出
    # =========================================================

    def _export_original_form(
        self,
        survey_record_id,
        file_path,
    ):
        return export_lined_channel_original_form(
            survey_record_id=(survey_record_id),
            file_path=file_path,
        )
