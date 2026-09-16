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
