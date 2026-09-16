from openpyxl import Workbook, load_workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter

from database import (
    get_app_root,
    get_engineering_asset_detail,
    get_inspection_results,
)

from forms.engineering.form_2_1 import (
    FORM_2_1,
)

from forms.engineering.persistence import (
    get_engineering_record,
)

from services.engineering_summary_export import (
    export_engineering_summary,
)

from services.original_form_export_common import (
    display_value,
    fill_original_form_ownership_header,
)


def export_lined_channel_summary(
    records,
    file_path,
):
    """
    详细汇总导出的兼容入口。

    实际执行统一交给工程调查通用汇总导出器。
    """

    return export_engineering_summary(
        FORM_2_1,
        records=records,
        file_path=file_path,
    )

def _format_stake_range(
    start_stake,
    end_stake,
):
    start_text = str(start_stake or "").strip()

    end_text = str(end_stake or "").strip()

    if start_text and end_text:
        return f"{start_text} ～ " f"{end_text}"

    return start_text or end_text


def _format_side_slope(
    record_data,
):
    """
    按原表“渠道边坡（内/外）”格式输出。

    例如：
    内坡 6、外坡 6 -> 6/6
    """

    inner = display_value(record_data.get("inner_slope"))

    outer = display_value(record_data.get("outer_slope"))

    if not inner and not outer:
        return ""

    return f"{inner}/{outer}"


def _get_original_form_template_path():
    """
    获取附表2.1 Excel模板路径。
    """

    return get_app_root() / "templates" / "excel" / "form_2_1_V1.xlsx"


def export_lined_channel_original_form(
    survey_record_id,
    file_path,
):
    """
    将一条附表2.1渠道渠段调查记录
    填入正式原表模板。
    """

    # =========================================================
    # 模板
    # =========================================================

    template_path = _get_original_form_template_path()

    if not template_path.exists():
        raise FileNotFoundError(
            "未找到附表2.1 Excel 模板。\n\n" f"应存在于：\n{template_path}"
        )

    # =========================================================
    # 数据
    # =========================================================

    record = get_engineering_record(FORM_2_1, survey_record_id=survey_record_id)

    if record is None:
        raise ValueError("没有找到需要导出的" "渠道渠段调查记录。")

    asset = get_engineering_asset_detail(record["engineering_asset_id"])

    if asset is None:
        raise ValueError("没有找到调查记录对应的" "工程对象。")

    inspection_results = get_inspection_results(survey_record_id)

    evaluation_map = {
        result["item_code"]: result["grade"] for result in inspection_results
    }

    record_data = record["record_data"] or {}

    # =========================================================
    # 打开模板
    # =========================================================

    workbook = load_workbook(template_path)

    if "附表2.1" in workbook.sheetnames:
        worksheet = workbook["附表2.1"]
    else:
        worksheet = workbook.active

    if worksheet is None:
        raise ValueError("附表2.1 Excel模板中" "没有可用工作表。")

    # =========================================================
    # 顶部归属和编号
    # =========================================================

    fill_original_form_ownership_header(
        worksheet,
        asset=asset,
        canal_id=record["canal_unit_id"],
        business_code=record["business_code"],
    )

    # =========================================================
    # 基本信息
    # =========================================================

    worksheet["B5"] = record["asset_name"] or ""

    worksheet["H5"] = _format_stake_range(
        record["start_stake_text"],
        record["end_stake_text"],
    )

    worksheet["B6"] = record_data.get("section_length")
    worksheet["D6"] = record_data.get("build_date") or ""
    worksheet["F6"] = record_data.get("renovation_date") or ""
    worksheet["H6"] = record_data.get("longitudinal_slope") or ""
    worksheet["J6"] = record_data.get("design_flow")

    worksheet["B7"] = record_data.get("channel_grade") or ""
    worksheet["D7"] = record_data.get("cross_section_form") or ""
    worksheet["F7"] = record_data.get("embankment_top_width")
    worksheet["H7"] = _format_side_slope(record_data)
    worksheet["J7"] = record_data.get("increased_flow")

    worksheet["B8"] = record_data.get("bed_soil") or ""
    worksheet["D8"] = record_data.get("lining_structure") or ""
    worksheet["F8"] = record_data.get("freeboard")
    worksheet["H8"] = record_data.get("bottom_width")
    worksheet["J8"] = record_data.get("water_conveyance_loss")

    worksheet["B9"] = record_data.get("lining_material") or ""
    worksheet["D9"] = record_data.get("lining_thickness")
    worksheet["F9"] = record_data.get("concrete_strength") or ""
    worksheet["H9"] = record_data.get("channel_depth")
    worksheet["J9"] = record_data.get("channel_bottom_elevation")

    # =========================================================
    # 12项评价
    # =========================================================
    #
    # 模板第11～22行，
    # 项目类别位于H列。
    # =========================================================

    for row_number, item in enumerate(
        FORM_2_1.evaluation_items,
        start=11,
    ):
        grade = evaluation_map.get(
            item["item_code"],
            "",
        )

        worksheet[f"E{row_number}"] = grade or ""

    # =========================================================
    # 调查结论
    # =========================================================

    worksheet["C23"] = record["survey_comment"] or ""

    worksheet["J23"] = record["overall_grade"] or ""

    worksheet["J24"] = record["survey_date"] or ""

    # 签字栏当前不进入系统数据，
    # 保持模板空白。

    # =========================================================
    # 打印
    # =========================================================

    worksheet.print_area = "A1:J24"

    worksheet.page_setup.orientation = "landscape"

    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4

    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 1

    page_setup_properties = worksheet.sheet_properties.pageSetUpPr

    if page_setup_properties is not None:
        page_setup_properties.fitToPage = True

    worksheet.sheet_view.showGridLines = False

    workbook.save(file_path)

    return {
        "file_path": file_path,
        "survey_record_id": (survey_record_id),
        "business_code": (record["business_code"]),
        "asset_name": (record["asset_name"]),
    }
