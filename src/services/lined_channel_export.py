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

from services.original_form_export_common import (
    display_value,
    fill_original_form_ownership_header,
)


def export_lined_channel_summary(
    records,
    file_path,
):
    """
    将当前筛选后的附表2.1记录导出为数据汇总 Excel。

    一条 SurveyRecord 对应一行。
    """

    if not records:
        raise ValueError("当前没有可导出的调查记录。")

    workbook = Workbook()

    worksheet = workbook.active

    if worksheet is None:
        worksheet = workbook.create_sheet("渠道渠段调查汇总")
    else:
        worksheet.title = "渠道渠段调查汇总"

    # =========================================================
    # 表头
    # =========================================================

    basic_headers = [
        "序号",
        "业务编号",
        "渠道名称",
        "基层处",
        "水管所",
        "渠系",
        "起始桩号",
        "终止桩号",
        "渠段长度（m）",
        "建成时间",
        "加固改造时间",
        "纵比降",
        "设计流量（m³/s）",
        "渠道等级",
        "渠道断面形式",
        "堤顶宽度（m）",
        "渠道边坡（内）",
        "渠道边坡（外）",
        "加大流量（m³/s）",
        "渠床土质",
        "防渗衬砌结构",
        "安全超高（m）",
        "渠底宽度（m）",
        "输水损失（m³/km）",
        "衬砌材料",
        "衬砌厚度（cm）",
        "混凝土强度",
        "渠深（m）",
        "渠底高程（m）",
    ]

    evaluation_headers = [
        (f"{item['category']}" f"-{item['item_name']}")
        for item in FORM_2_1.evaluation_items
    ]

    conclusion_headers = [
        "工程状况类别",
        "调查时间",
        "调查意见与建议",
        "状态",
        "修改时间",
    ]

    headers = basic_headers + evaluation_headers + conclusion_headers

    worksheet.append(headers)

    # =========================================================
    # 数据
    # =========================================================

    exported_count = 0

    for index, summary_record in enumerate(
        records,
        start=1,
    ):
        survey_record_id = summary_record["survey_record_id"]

        record = get_engineering_record(FORM_2_1, survey_record_id=survey_record_id)

        if record is None:
            raise ValueError("导出过程中发现调查记录不存在：" f"{survey_record_id}")

        record_data = record["record_data"] or {}

        inspection_results = get_inspection_results(survey_record_id)

        evaluation_map = {
            result["item_code"]: result["grade"] for result in inspection_results
        }

        status_text = {
            "draft": "草稿",
            "completed": "录入完成",
        }.get(
            record["record_status"],
            record["record_status"],
        )

        row = [
            index,
            record["business_code"],
            record["asset_name"],
            summary_record["department_name"],
            summary_record["office_name"],
            summary_record["canal_name"],
            record["start_stake_text"],
            record["end_stake_text"],
            record_data.get("section_length"),
            record_data.get("build_date"),
            record_data.get("renovation_date"),
            record_data.get("longitudinal_slope"),
            record_data.get("design_flow"),
            record_data.get("channel_grade"),
            record_data.get("cross_section_form"),
            record_data.get("embankment_top_width"),
            record_data.get("inner_slope"),
            record_data.get("outer_slope"),
            record_data.get("increased_flow"),
            record_data.get("bed_soil"),
            record_data.get("lining_structure"),
            record_data.get("freeboard"),
            record_data.get("bottom_width"),
            record_data.get("water_conveyance_loss"),
            record_data.get("lining_material"),
            record_data.get("lining_thickness"),
            record_data.get("concrete_strength"),
            record_data.get("channel_depth"),
            record_data.get("channel_bottom_elevation"),
        ]

        # 12项评价
        for item in FORM_2_1.evaluation_items:
            row.append(
                evaluation_map.get(
                    item["item_code"],
                    "",
                )
            )

        row.extend(
            [
                record["overall_grade"],
                record["survey_date"],
                record["survey_comment"],
                status_text,
                summary_record["updated_at"],
            ]
        )

        worksheet.append(row)

        exported_count += 1

    # =========================================================
    # 样式
    # =========================================================

    header_fill = PatternFill(
        fill_type="solid",
        fgColor="D9EAF7",
    )

    header_font = Font(
        bold=True,
    )

    thin_side = Side(
        style="thin",
        color="D9DEE3",
    )

    border = Border(
        left=thin_side,
        right=thin_side,
        top=thin_side,
        bottom=thin_side,
    )

    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )
        cell.border = border

    worksheet.row_dimensions[1].height = 38

    for row_cells in worksheet.iter_rows(
        min_row=2,
        max_row=worksheet.max_row,
    ):
        for cell in row_cells:
            cell.alignment = Alignment(
                vertical="center",
                wrap_text=True,
            )
            cell.border = border

    # =========================================================
    # 居中列
    # =========================================================

    center_columns = {
        1,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        22,
        23,
        24,
        26,
        28,
        29,
    }

    evaluation_start_column = 30

    evaluation_end_column = (
        evaluation_start_column + len(FORM_2_1.evaluation_items) - 1
    )

    center_columns.update(
        range(
            evaluation_start_column,
            evaluation_end_column + 1,
        )
    )

    overall_grade_column = evaluation_end_column + 1

    survey_date_column = evaluation_end_column + 2

    comment_column = evaluation_end_column + 3

    status_column = evaluation_end_column + 4

    updated_at_column = evaluation_end_column + 5

    center_columns.update(
        {
            overall_grade_column,
            survey_date_column,
            status_column,
        }
    )

    for column_index in center_columns:
        for row_index in range(
            2,
            worksheet.max_row + 1,
        ):
            worksheet.cell(
                row=row_index,
                column=column_index,
            ).alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )

    # =========================================================
    # 列宽
    # =========================================================

    widths = {
        1: 8,
        2: 22,
        3: 20,
        4: 15,
        5: 15,
        6: 18,
        7: 14,
        8: 14,
        9: 14,
        10: 14,
        11: 16,
        12: 14,
        13: 16,
        14: 12,
        15: 18,
        16: 14,
        17: 14,
        18: 14,
        19: 16,
        20: 16,
        21: 22,
        22: 14,
        23: 14,
        24: 18,
        25: 16,
        26: 14,
        27: 14,
        28: 12,
        29: 14,
    }

    for column_index in range(
        evaluation_start_column,
        evaluation_end_column + 1,
    ):
        widths[column_index] = 20

    widths[overall_grade_column] = 14

    widths[survey_date_column] = 14

    widths[comment_column] = 36

    widths[status_column] = 12

    widths[updated_at_column] = 20

    for column_index, width in widths.items():
        worksheet.column_dimensions[get_column_letter(column_index)].width = width

    # =========================================================
    # 使用体验 / 打印
    # =========================================================

    worksheet.freeze_panes = "A2"

    worksheet.auto_filter.ref = worksheet.dimensions

    worksheet.sheet_view.showGridLines = False

    worksheet.page_setup.orientation = "landscape"

    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0

    workbook.save(file_path)

    return {
        "file_path": file_path,
        "exported_count": exported_count,
    }


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
