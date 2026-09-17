import re


def normalize_structure_grade(
    value,
    field_name="建筑物等级",
):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    compact = re.sub(
        r"\s+",
        "",
        text,
    )

    match = re.fullmatch(
        r"(\d+)级?",
        compact,
    )

    if match is None:
        raise ValueError(
            f"{field_name}应填写数字，"
            "例如：3；系统将自动保存为“3级”。"
        )

    number = int(
        match.group(1)
    )

    if number <= 0:
        raise ValueError(
            f"{field_name}必须大于0。"
        )

    return f"{number}级"


def normalize_concrete_strength(
    value,
    field_name="混凝土强度",
):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    compact = re.sub(
        r"\s+",
        "",
        text,
    )

    match = re.fullmatch(
        r"[cC]?(\d+)",
        compact,
    )

    if match is None:
        raise ValueError(
            f"{field_name}应填写数字或C+数字，"
            "例如：30、c30、C30；"
            "系统将统一保存为“C30”。"
        )

    number = int(
        match.group(1)
    )

    if number <= 0:
        raise ValueError(
            f"{field_name}必须大于0。"
        )

    return f"C{number}"
