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


from shared.forms.engineering.formatters import (
    _format_dimension_value,
    format_dimension_pair,
    format_dimension_pair_asterisk,
    format_stake_range_spaced,
    format_stake_range_compact,
    format_side_slope,
    format_opening_size,
)
