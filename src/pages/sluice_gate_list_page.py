from forms.engineering.form_2_2 import (
    FORM_2_2,
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

    数据加载、筛选和删除统一使用
    EngineeringSurveyListPage
    的公共工程调查能力。

    本类只保留：
    - 表格表现；
    - 正式原表导出。
    """

    FORM_CODE = FORM_2_2.form_code

    PAGE_TITLE = (
        f"{FORM_2_2.display_name.removesuffix('表')}"
        "记录"
    )

    NEW_BUTTON_TEXT = (
        "新增水闸调查"
    )

    KEYWORD_PLACEHOLDER = (
        "业务编号 / 工程名称 / 桩号"
    )

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

    SHOW_GRADE_STATISTICS = False

    EXPORT_FILENAME_PREFIX = (
        "附表2.2_水闸工程状况调查表"
    )

    EXPORT_FALLBACK_ASSET_NAME = (
        "水闸"
    )

    def _keyword_values(
        self,
        record,
    ):
        return [
            record["business_code"],
            record["asset_name"],
            record[
                "engineering_position"
            ],
        ]

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

        design_flow = (
            record_data.get(
                "design_flow"
            )
        )

        design_flow_text = (
            ""
            if design_flow is None
            else str(
                design_flow
            )
        )

        return [
            record["business_code"],
            record["asset_name"],
            record["department_name"],
            record["office_name"],
            record["canal_name"],
            record[
                "engineering_position"
            ],
            design_flow_text,
            status_text,
            record["updated_at"],
        ]

    def _export_original_form(
        self,
        survey_record_id,
        file_path,
    ):
        return (
            export_sluice_gate_original_form(
                survey_record_id=(
                    survey_record_id
                ),
                file_path=file_path,
            )
        )
