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
    get_sluice_gate_record,
    get_canal_lineage,
)

from services.sluice_gate_evaluation import (
    SLUICE_GATE_EVALUATION_ITEMS,
)


def export_sluice_gate_summary(
    records,
    file_path,
):
    """
    将当前筛选后的附表2.2记录导出为数据汇总 Excel。

    一条 SurveyRecord 对应 Excel 中的一行。
    """

    if not records:
        raise ValueError("当前没有可导出的调查记录。")

    workbook = Workbook()

    worksheet = workbook.active

    if worksheet is None:
        worksheet = workbook.create_sheet("水闸调查汇总")
    else:
        worksheet.title = "水闸调查汇总"

    # =========================
    # 表头
    # =========================

    basic_headers = [
        "序号",
        "业务编号",
        "工程名称",
        "基层处",
        "水管所",
        "渠系",
        "桩号",
        "设计流量（m³/s）",
        "建筑物等级",
        "建成年月",
        "加固改造年月",
        "加大流量（m³/s）",
        "孔数",
        "孔宽",
        "孔高",
        "主要构件材料",
        "混凝土强度",
        "钢筋混凝土强度",
        "保护层厚度",
        "裂缝限宽",
    ]

    evaluation_headers = [
        (f"{item['category']}" f"-{item['item_name']}")
        for item in SLUICE_GATE_EVALUATION_ITEMS
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

    # =========================
    # 数据
    # =========================

    exported_count = 0

    for index, summary_record in enumerate(
        records,
        start=1,
    ):
        survey_record_id = summary_record["survey_record_id"]

        record = get_sluice_gate_record(survey_record_id)

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
            record_data.get("stake"),
            record_data.get("design_flow"),
            record_data.get("structure_grade"),
            record_data.get("build_date"),
            record_data.get("renovation_date"),
            record_data.get("increased_flow"),
            record_data.get("opening_count"),
            record_data.get("opening_width"),
            record_data.get("opening_height"),
            record_data.get("main_component_material"),
            record_data.get("concrete_strength"),
            record_data.get("reinforced_concrete_strength"),
            record_data.get("cover_thickness"),
            record_data.get("crack_width_limit"),
        ]

        # 14项分项评价
        for item in SLUICE_GATE_EVALUATION_ITEMS:
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

    # =========================
    # 样式
    # =========================

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

    # 表头
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

    # 数据区
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

    # 居中显示的列
    center_columns = {
        1,  # 序号
        7,  # 桩号
        8,  # 设计流量
        9,  # 建筑物等级
        10,  # 建成年月
        11,  # 加固改造年月
        12,  # 加大流量
        13,  # 孔数
        14,  # 孔宽
        15,  # 孔高
        19,  # 保护层厚度
        20,  # 裂缝限宽
    }

    # 14个评价列
    evaluation_start_column = 21
    evaluation_end_column = (
        evaluation_start_column + len(SLUICE_GATE_EVALUATION_ITEMS) - 1
    )

    center_columns.update(
        range(
            evaluation_start_column,
            evaluation_end_column + 1,
        )
    )

    # 工程状况类别、调查时间、状态
    overall_grade_column = evaluation_end_column + 1
    survey_date_column = evaluation_end_column + 2
    status_column = evaluation_end_column + 4

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

    # =========================
    # 列宽
    # =========================

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
        12: 16,
        13: 10,
        14: 10,
        15: 10,
        16: 18,
        17: 16,
        18: 20,
        19: 14,
        20: 14,
    }

    for column_index in range(
        evaluation_start_column,
        evaluation_end_column + 1,
    ):
        widths[column_index] = 20

    widths[overall_grade_column] = 14

    widths[survey_date_column] = 14

    # 调查意见
    comment_column = evaluation_end_column + 3
    widths[comment_column] = 36

    widths[status_column] = 12

    # 修改时间
    updated_at_column = evaluation_end_column + 5
    widths[updated_at_column] = 20

    for column_index, width in widths.items():
        column_letter = get_column_letter(column_index)

        worksheet.column_dimensions[column_letter].width = width

    # =========================
    # Excel 使用体验
    # =========================

    # 冻结表头
    worksheet.freeze_panes = "A2"

    # 自动筛选
    worksheet.auto_filter.ref = worksheet.dimensions

    # 页面设置
    worksheet.sheet_view.showGridLines = False

    worksheet.page_setup.orientation = "landscape"

    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0

    # =========================
    # 保存
    # =========================

    workbook.save(file_path)

    return {
        "file_path": file_path,
        "exported_count": exported_count,
    }


def _strip_trailing_suffix(
    value,
    suffix,
):
    """
    原表顶部已经固定显示“处、所、干渠、支渠”，
    因此填入名称时去掉重复的末尾单位名称。
    """

    text = str(value or "").strip()

    if suffix and text.endswith(suffix):
        text = text[: -len(suffix)].strip()

    return text


def _display_value(value):
    """
    将数据库值转换为适合原表显示的文本。
    """

    if value is None:
        return ""

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

    return str(value)


def _format_opening_size(record_data):
    """
    将孔数、孔宽、孔高组合为原表要求的：
    孔数/宽×高
    """

    count = _display_value(record_data.get("opening_count"))

    width = _display_value(record_data.get("opening_width"))

    height = _display_value(record_data.get("opening_height"))

    if not count and not width and not height:
        return ""

    if width or height:
        size_text = f"{width}×{height}"
    else:
        size_text = ""

    if count and size_text:
        return f"{count}/{size_text}"

    if count:
        return count

    return size_text


def _get_original_form_template_path():
    """
    获取附表2.2 Excel 模板路径。

    开发环境：
        项目根目录/templates/excel/

    PyInstaller 环境：
        exe 所在目录/templates/excel/
    """

    return get_app_root() / "templates" / "excel" / "form_2_2_V1.xlsx"


def export_sluice_gate_original_form(
    survey_record_id,
    file_path,
):
    """
    将一条附表2.2调查记录填入正式原表模板。
    """

    # =========================
    # 1. 查找模板
    # =========================

    template_path = _get_original_form_template_path()

    if not template_path.exists():
        raise FileNotFoundError(
            "未找到附表2.2 Excel 模板。\n\n" f"应存在于：\n{template_path}"
        )

    # =========================
    # 2. 加载调查记录
    # =========================

    record = get_sluice_gate_record(survey_record_id)

    if record is None:
        raise ValueError("没有找到需要导出的水闸调查记录。")

    asset = get_engineering_asset_detail(record["engineering_asset_id"])

    if asset is None:
        raise ValueError("没有找到该调查记录对应的工程对象。")

    inspection_results = get_inspection_results(survey_record_id)

    evaluation_map = {
        result["item_code"]: result["grade"] for result in inspection_results
    }

    record_data = record["record_data"] or {}

    # =========================
    # 3. 打开模板
    # =========================

    workbook = load_workbook(template_path)
    if "附表2.2" in workbook.sheetnames:
        worksheet = workbook["附表2.2"]
    else:
        worksheet = workbook.active

    if worksheet is None:
        raise ValueError("附表2.2 Excel 模板中没有可用工作表。")

    # =========================
    # 4. 顶部归属和业务编号
    # =========================

    # 原表格式：
    #
    # xxxx 处
    # xxxx 所
    # xxxx 干渠
    # xxxx 支渠
    # 编号：xxxx
    #
    # 因此固定单位文字放在偶数列，
    # 实际名称放在前一个单元格。

    worksheet["B3"] = "处"
    worksheet["D3"] = "所"
    worksheet["F3"] = "干渠"
    worksheet["H3"] = "支渠"
    worksheet["I3"] = "编号："

    # -------------------------
    # 基层处
    # -------------------------

    department_name = asset["department_name"] or ""

    worksheet["A3"] = _strip_trailing_suffix(
        department_name,
        "处",
    )

    # -------------------------
    # 水管所
    # -------------------------

    office_name = asset["office_name"] or ""

    # 数据库通常保存：
    # “清水水管所”
    #
    # 原表已经固定显示“所”，
    # 因此这里只输出“清水”。

    worksheet["C3"] = _strip_trailing_suffix(
        office_name,
        "所",
    )

    # -------------------------
    # 渠系层级
    # -------------------------

    worksheet["E3"] = ""
    worksheet["G3"] = ""

    canal_lineage = get_canal_lineage(record["canal_id"])

    main_canal_name = ""
    branch_canal_name = ""

    for canal in canal_lineage:

        canal_level = canal["canal_level"]

        canal_name = canal["name"] or ""

        # 01 干渠
        # 02 分干渠
        #
        # 如果存在多级，
        # 取距离当前工程最近的一个。
        if canal_level in (
            "01",
            "02",
        ):
            main_canal_name = canal_name

        # 03 支渠
        # 04 分支渠
        #
        # 同样取最接近当前工程的节点。
        elif canal_level in (
            "03",
            "04",
        ):
            branch_canal_name = canal_name

    # 原表单元格后面已经固定写“干渠”，
    # 所以去掉名称末尾重复的“干渠”。
    #
    # 例如：
    # 东二干渠 -> 东二 + 干渠
    # 某某分干渠 -> 某某分 + 干渠

    worksheet["E3"] = _strip_trailing_suffix(
        main_canal_name,
        "干渠",
    )

    # 同理：
    # 某某支渠 -> 某某 + 支渠
    # 某某分支渠 -> 某某分 + 支渠

    worksheet["G3"] = _strip_trailing_suffix(
        branch_canal_name,
        "支渠",
    )

    # -------------------------
    # 业务编号
    # -------------------------

    worksheet["J3"] = record["business_code"] or ""

    # =========================
    # 5. 工程基本信息
    # =========================

    # 名称
    worksheet["B5"] = record["asset_name"] or ""

    # 桩号
    worksheet["H5"] = record_data.get("stake") or ""

    # 设计流量
    worksheet["J5"] = record_data.get("design_flow")

    # 建筑物等级
    worksheet["B6"] = record_data.get("structure_grade") or ""

    # 建成年月
    worksheet["D6"] = record_data.get("build_date") or ""

    # 加固改造年月
    worksheet["F6"] = record_data.get("renovation_date") or ""

    # 孔数/宽×高
    worksheet["H6"] = _format_opening_size(record_data)

    # 加大流量
    worksheet["J6"] = record_data.get("increased_flow")

    # 主要构件材料
    worksheet["B7"] = record_data.get("main_component_material") or ""

    # 混凝土强度
    worksheet["D7"] = record_data.get("concrete_strength") or ""

    # 钢筋混凝土强度
    worksheet["F7"] = record_data.get("reinforced_concrete_strength") or ""

    # 保护层厚度
    worksheet["H7"] = record_data.get("cover_thickness")

    # 裂缝限宽
    worksheet["J7"] = record_data.get("crack_width_limit")

    # =========================
    # 6. 14项分项评价
    # =========================
    #
    # 模板第9～22行，
    # 项目类别位于 E 列。

    for row_number, item in enumerate(
        SLUICE_GATE_EVALUATION_ITEMS,
        start=9,
    ):
        grade = evaluation_map.get(
            item["item_code"],
            "",
        )

        worksheet[f"E{row_number}"] = grade or ""

    # =========================
    # 7. 调查结论
    # =========================

    # 调查意见与建议
    worksheet["C23"] = record["survey_comment"] or ""

    # 工程状况类别
    worksheet["J23"] = record["overall_grade"] or ""

    # 调查时间
    worksheet["J24"] = record["survey_date"] or ""

    # =========================
    # 8. 打印设置
    # =========================

    worksheet.print_area = "A1:J27"

    worksheet.page_setup.orientation = "landscape"

    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4

    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 1

    page_setup_properties = worksheet.sheet_properties.pageSetUpPr

    if page_setup_properties is not None:
        page_setup_properties.fitToPage = True

    worksheet.sheet_view.showGridLines = False

    # =========================
    # 9. 保存
    # =========================

    workbook.save(file_path)

    return {
        "file_path": file_path,
        "survey_record_id": survey_record_id,
        "business_code": record["business_code"],
        "asset_name": record["asset_name"],
    }
