from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)
from services.aqueduct_export import (
    export_aqueduct_original_form,
)


class AqueductListPage(
    EngineeringSurveyListPage,
):
    """
    附表2.3渡槽（座槽）当前批次调查列表。

    公共列表行为由
    EngineeringSurveyListPage 提供。

    本类只保留附表2.3自己的显示和导出差异。
    """

    FORM_CODE = "form_2_3"

    PAGE_TITLE = "附表2.3 渡槽（座槽）工程状况调查记录"

    NEW_BUTTON_TEXT = "新增渡槽（座槽）调查"

    KEYWORD_PLACEHOLDER = "业务编号 / 工程名称 / 桩号"

    POSITION_LABEL = "桩号"

    TABLE_HEADERS = (
        "业务编号",
        "工程名称",
        "基层处",
        "水管所",
        "渠系",
        "桩号",
        "工程状况类别",
        "调查时间",
        "状态",
        "修改时间",
    )

    TABLE_WIDTHS = (
        155,
        180,
        130,
        130,
        150,
        120,
        105,
        110,
        90,
        160,
    )

    SHOW_GRADE_STATISTICS = True

    EXPORT_FILENAME_PREFIX = "附表2.3_" "渡槽（座槽）工程状况调查表"

    EXPORT_FALLBACK_ASSET_NAME = "渡槽"

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

        return [
            record["business_code"],
            record["asset_name"],
            record["department_name"],
            record["office_name"],
            record["canal_name"],
            record["engineering_position"],
            record["overall_grade"] or "",
            record["survey_date"],
            status_text,
            record["updated_at"],
        ]

    def _export_original_form(
        self,
        survey_record_id,
        file_path,
    ):
        return export_aqueduct_original_form(
            survey_record_id=(survey_record_id),
            file_path=file_path,
        )
