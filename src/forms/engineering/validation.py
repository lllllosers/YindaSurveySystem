from collections import Counter
from typing import Any

from forms.engineering.models import (
    EngineeringFormDefinition,
)


def _is_blank(
    value: Any,
) -> bool:
    if value is None:
        return True

    if isinstance(
        value,
        str,
    ):
        return not value.strip()

    return False


def validate_completion(
    definition: EngineeringFormDefinition,
    payload: dict,
) -> list[str]:
    """
    校验工程调查是否满足“完成调查”条件。

    本函数只负责业务规则判断，
    不负责：
    - 弹窗；
    - 数据库写入；
    - 页面状态切换。

    返回：
        []              -> 校验通过
        ["错误1", ...]  -> 校验失败
    """

    errors: list[str] = []

    record_data = payload.get("record_data") or {}

    # =========================================================
    # 1. 正式字段必填检查
    # =========================================================

    for field in definition.fields:
        if not field.required:
            continue

        value = record_data.get(field.key)

        if _is_blank(value):
            errors.append(f"{field.label}不能为空。")

    # =========================================================
    # 2. 工程位置
    # =========================================================

    position_data = payload.get("position") or {}

    actual_kind = position_data.get("kind")

    if actual_kind != (definition.position.kind):
        errors.append("工程位置数据类型" "与当前表单定义不一致。")

    elif actual_kind == "point":
        stake_text = position_data.get("single_stake_text")

        stake_value = position_data.get("single_stake_value")

        # 必填性主要由正式字段检查负责。
        # 这里只检查解析结果是否内部一致。
        if not _is_blank(stake_text) and stake_value is None:
            errors.append("工程桩号解析结果不完整。")

    elif actual_kind == "range":
        start_text = position_data.get("start_stake_text")

        start_value = position_data.get("start_stake_value")

        end_text = position_data.get("end_stake_text")

        end_value = position_data.get("end_stake_value")

        if not _is_blank(start_text) and start_value is None:
            errors.append("起始桩号解析结果不完整。")

        if not _is_blank(end_text) and end_value is None:
            errors.append("终止桩号解析结果不完整。")

        if (
            start_value is not None
            and end_value is not None
            and end_value < start_value
        ):
            errors.append("终止桩号不能小于起始桩号。")

    # =========================================================
    # 3. 分项评价
    # =========================================================

    inspection_results = payload.get("inspection_results") or []

    result_codes = [
        result.get("item_code")
        for result in inspection_results
        if result.get("item_code")
    ]

    code_counts = Counter(result_codes)

    result_map = {}

    for result in inspection_results:
        item_code = result.get("item_code")

        if not item_code:
            continue

        # 重复项单独报错，
        # result_map保留第一项即可。
        if item_code not in result_map:
            result_map[item_code] = result

    for item in definition.evaluation_items:
        item_code = item["item_code"]

        item_name = item["item_name"]

        if code_counts[item_code] > 1:
            errors.append(f"{item_name}存在重复评价结果。")

        result = result_map.get(item_code)

        if result is None:
            errors.append(f"{item_name}未完成评价。")
            continue

        grade = result.get("grade")

        if _is_blank(grade):
            errors.append(f"{item_name}未完成评价。")

        elif grade not in (definition.grade_options):
            errors.append(f"{item_name}评价等级无效。")

    # =========================================================
    # 4. 工程状况类别
    # =========================================================

    overall_grade = payload.get("overall_grade")

    if _is_blank(overall_grade):
        errors.append("请选择工程状况类别。")

    elif overall_grade not in (definition.grade_options):
        errors.append("工程状况类别无效。")

    # =========================================================
    # 5. 调查时间
    # =========================================================

    if _is_blank(payload.get("survey_date")):
        errors.append("请填写调查时间。")

    # =========================================================
    # 6. 调查意见与建议
    # =========================================================

    if _is_blank(payload.get("survey_comment")):
        errors.append("请填写调查意见与建议。")

    return errors
