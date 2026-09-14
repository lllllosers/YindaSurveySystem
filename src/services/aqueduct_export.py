from openpyxl import Workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import (
    get_column_letter,
)

from database import (
    get_inspection_results,
    get_point_engineering_record,
)

from services.aqueduct_evaluation import (
    AQUEDUCT_EVALUATION_ITEMS,
)


def _display_value(value):
    """
    将数据库值转换为适合汇总表显示的文本。

    整数值的小数不显示无意义的 .0。
    """

    if value is None:
        return ""

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

    return str(value)


def _format_section_size(
    record_data,
):
    """
    将内部拆分保存的断面宽、高
    组合为正式字段“断面尺寸（宽×高）”。
    """

    width = _display_value(record_data.get("section_width"))

    height = _display_value(record_data.get("section_height"))

    if not width and not height:
        return ""

    return f"{width}×{height}"


def export_aqueduct_summary(
    records,
    file_path,
):
    """
    将当前筛选后的附表2.3记录
    导出为详细数据汇总 Excel。

    一条 SurveyRecord 对应 Excel 中的一行。
    """

    if not records:
        raise ValueError("当前没有可导出的调查记录。")

    workbook = Workbook()

    worksheet = workbook.active

    if worksheet is None:
        worksheet = workbook.create_sheet("渡槽调查汇总")
    else:
        worksheet.title = "渡槽调查汇总"

    # =========================================================
    # 表头
    # =========================================================

    basic_headers = [
        "序号",
        "业务编号",
        "名称",
        "基层处",
        "水管所",
        "渠系",
        "桩号",
        "设计流量（m³/s）",
        "建筑物等级",
        "建成年月",
        "加固改造年月",
        "长度",
        "加大流量（m³/s）",
        "结构形式",
        "断面尺寸（宽×高）",
        "槽身结构",
        "槽壁厚度",
        "止水形式",
        "槽底高程",
        "跨数",
        "下部支撑结构型式",
    ]

    evaluation_headers = [
        (f"{item['category']}" f"-{item['item_name']}")
        for item in AQUEDUCT_EVALUATION_ITEMS
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

        record = get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        if record is None:
            raise ValueError(
                "导出过程中发现" "附表2.3调查记录不存在：" f"{survey_record_id}"
            )

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
            record_data.get("stake"),
            record_data.get("design_flow"),
            record_data.get("structure_grade"),
            record_data.get("build_date"),
            record_data.get("renovation_date"),
            record_data.get("length"),
            record_data.get("increased_flow"),
            record_data.get("structure_form"),
            _format_section_size(record_data),
            record_data.get("trough_body_structure"),
            record_data.get("trough_wall_thickness"),
            record_data.get("waterstop_form"),
            record_data.get("trough_bottom_elevation"),
            record_data.get("span_count"),
            record_data.get("lower_support_structure_form"),
        ]

        # 12项分项评价
        for item in AQUEDUCT_EVALUATION_ITEMS:
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

    worksheet.row_dimensions[1].height = 36

    for row in worksheet.iter_rows(
        min_row=2,
        max_row=worksheet.max_row,
    ):
        for cell in row:
            cell.alignment = Alignment(
                vertical="center",
                wrap_text=True,
            )

            cell.border = border

    # =========================================================
    # 居中列
    # =========================================================

    center_columns = {
        1,  # 序号
        7,  # 桩号
        8,  # 设计流量
        9,  # 建筑物等级
        10,  # 建成年月
        11,  # 加固改造年月
        12,  # 长度
        13,  # 加大流量
        15,  # 断面尺寸
        17,  # 槽壁厚度
        19,  # 槽底高程
        20,  # 跨数
    }

    evaluation_start_column = 22

    evaluation_end_column = evaluation_start_column + len(AQUEDUCT_EVALUATION_ITEMS) - 1

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
        4: 16,
        5: 16,
        6: 18,
        7: 14,
        8: 16,
        9: 14,
        10: 14,
        11: 16,
        12: 12,
        13: 16,
        14: 18,
        15: 18,
        16: 18,
        17: 14,
        18: 16,
        19: 14,
        20: 10,
        21: 22,
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
    # Excel 使用体验
    # =========================================================

    worksheet.freeze_panes = "A2"

    worksheet.auto_filter.ref = worksheet.dimensions

    worksheet.sheet_view.showGridLines = False

    worksheet.page_setup.orientation = "landscape"

    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0

    # =========================================================
    # 保存
    # =========================================================

    workbook.save(file_path)

    return {
        "file_path": file_path,
        "exported_count": (exported_count),
    }
