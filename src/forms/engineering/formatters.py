"""工程调查声明式展示/导出使用的公共纯格式化函数。"""


def format_record_status(value):
    """
    将 SurveyRecord 状态转换为界面/Excel统一中文显示。

    未知状态保持原值，避免吞掉未来新增状态。
    """
    return {
        "draft": "草稿",
        "completed": "录入完成",
    }.get(
        value,
        value,
    )


def _format_dimension_value(
    value,
):
    """把断面尺寸单值转换为稳定的展示文本。"""

    if value is None:
        return ""

    if (
        isinstance(value, float)
        and value.is_integer()
    ):
        return str(int(value))

    return str(value)


def format_dimension_pair(
    width,
    height,
):
    """
    将宽、高组合为“宽×高”。

    保持旧正式原表/详细汇总的数值展示规则：
    None 显示为空，整数型浮点数不保留 .0。
    """

    width_text = _format_dimension_value(
        width
    )
    height_text = _format_dimension_value(
        height
    )

    if not width_text and not height_text:
        return ""

    return (
        f"{width_text}×{height_text}"
    )

def format_dimension_pair_asterisk(
    width,
    height,
):
    """
    按隧洞既有汇总/原表口径组合“宽*高”。

    这里故意保留旧实现的 str() 行为，
    不把 3.0 自动改成 3，以保证既有导出兼容。
    """

    if (
        width in (None, "")
        and height in (None, "")
    ):
        return ""

    width_text = (
        ""
        if width is None
        else str(width)
    )

    height_text = (
        ""
        if height is None
        else str(height)
    )

    if width_text and height_text:
        return (
            f"{width_text}*"
            f"{height_text}"
        )

    return width_text or height_text
