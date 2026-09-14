from database import (
    get_canal_lineage,
)


def strip_trailing_suffix(
    value,
    suffix,
):
    """
    原表顶部已经固定显示
    “处、所、干渠、支渠”等单位文字，
    因此填入名称时去掉重复末尾单位名称。
    """

    text = str(value or "").strip()

    if suffix and text.endswith(suffix):
        text = text[: -len(suffix)].strip()

    return text


def display_value(
    value,
):
    """
    将数据库值转换为适合正式原表显示的文本。
    """

    if value is None:
        return ""

    if isinstance(
        value,
        float,
    ):
        if value.is_integer():
            return str(int(value))

    return str(value)


def fill_original_form_ownership_header(
    worksheet,
    *,
    asset,
    canal_id,
    business_code,
):
    """
    填写工程调查正式原表共有的顶部归属信息：

    基层处 / 水管所 / 干渠 / 支渠 / 编号

    当前附表2.1、2.2、2.3顶部结构一致。
    """

    # =========================================================
    # 固定文字
    # =========================================================

    worksheet["B3"] = "处"
    worksheet["D3"] = "所"
    worksheet["F3"] = "干渠"
    worksheet["H3"] = "支渠"
    worksheet["I3"] = "编号："

    # =========================================================
    # 基层处
    # =========================================================

    worksheet["A3"] = strip_trailing_suffix(
        asset["department_name"] or "",
        "处",
    )

    # =========================================================
    # 水管所
    # =========================================================

    worksheet["C3"] = strip_trailing_suffix(
        asset["office_name"] or "",
        "所",
    )

    # =========================================================
    # 渠系层级
    # =========================================================

    main_canal_name = ""
    branch_canal_name = ""

    canal_lineage = get_canal_lineage(canal_id)

    for canal in canal_lineage:
        canal_level = canal["canal_level"]

        canal_name = canal["name"] or ""

        # 01 干渠
        # 02 分干渠
        if canal_level in (
            "01",
            "02",
        ):
            main_canal_name = canal_name

        # 03 支渠
        # 04 分支渠
        elif canal_level in (
            "03",
            "04",
        ):
            branch_canal_name = canal_name

    worksheet["E3"] = strip_trailing_suffix(
        main_canal_name,
        "干渠",
    )

    worksheet["G3"] = strip_trailing_suffix(
        branch_canal_name,
        "支渠",
    )

    # =========================================================
    # 业务编号
    # =========================================================

    worksheet["J3"] = business_code or ""
