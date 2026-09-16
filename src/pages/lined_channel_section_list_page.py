from forms.engineering.form_2_1 import (
    FORM_2_1,
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

    数据加载、筛选和删除统一使用
    EngineeringSurveyListPage
    的公共工程调查能力。

    本类只保留：
    - 表格表现；
    - 区间位置表现；
    - 正式原表导出。
    """

    FORM_CODE = FORM_2_1.form_code

    PAGE_TITLE = (
        f"{FORM_2_1.display_name.removesuffix('表')}"
        "记录"
    )

    NEW_BUTTON_TEXT = (
        "新增渠道渠段调查"
    )

    KEYWORD_PLACEHOLDER = (
        "业务编号 / 渠道名称 / 起止桩号"
    )

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

    SHOW_GRADE_STATISTICS = False

    EXPORT_FILENAME_PREFIX = (
        "附表2.1_防渗衬砌渠道渠段"
        "工程状况调查表"
    )

    EXPORT_FALLBACK_ASSET_NAME = (
        "渠道渠段"
    )

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

    def _position_text(
        self,
        record,
    ):
        start_stake = str(
            record[
                "start_stake_text"
            ]
            or ""
        )

        end_stake = str(
            record[
                "end_stake_text"
            ]
            or ""
        )

        if (
            start_stake
            and end_stake
        ):
            return (
                f"{start_stake} ～ "
                f"{end_stake}"
            )

        return (
            start_stake
            or end_stake
        )

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

        record_data = (
            record["record_data"]
            or {}
        )

        section_length = (
            record_data.get(
                "section_length"
            )
        )

        section_length_text = (
            ""
            if section_length is None
            else str(
                section_length
            )
        )

        return [
            record["business_code"],
            record["asset_name"],
            record["department_name"],
            record["office_name"],
            record["canal_name"],
            record["start_stake_text"],
            record["end_stake_text"],
            section_length_text,
            record["overall_grade"]
            or "",
            status_text,
            record["updated_at"],
        ]

    def _export_original_form(
        self,
        survey_record_id,
        file_path,
    ):
        return (
            export_lined_channel_original_form(
                survey_record_id=(
                    survey_record_id
                ),
                file_path=file_path,
            )
        )
