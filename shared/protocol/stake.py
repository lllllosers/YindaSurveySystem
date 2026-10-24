import re
from decimal import Decimal, ROUND_HALF_UP


def display_stake(value):
    """Normalize a read-only view, preserving unknown legacy text."""
    text = str(value or "").strip()
    try:
        return parse_stake(text)[0] or ""
    except ValueError:
        return text


def normalize_stake_fields(record):
    result = dict(record)
    for key in ("stake", "single_stake", "start_stake", "end_stake",
                "single_stake_text", "start_stake_text", "end_stake_text"):
        if key in result:
            result[key] = display_stake(result[key])
    return result


def normalize_stake_parts(text, numeric=None):
    """New writes share the parser's rounded text and numeric value."""
    if str(text or "").strip():
        return parse_stake(str(text))
    if numeric is not None:
        return parse_stake(str(numeric))
    return None, None


def _format_stake(total_meters: float) -> str:
    """
    将米数转换成引大入秦工程标准桩号显示形式。

    例如：
    12350 -> CH12+350.000
    12005.5 -> CH12+005.500
    """
    total = Decimal(str(total_meters)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    km = int(total // 1000)
    meters = total - km * 1000
    return f"CH{km}+{meters:07.3f}"


def parse_stake(value: str) -> tuple[str | None, float | None]:
    """
    解析常见桩号输入。

    正式标准格式：
    CH12+350.000

    为提高录入效率并兼容开发阶段旧数据，同时支持：
    CH12+350
    K12+350
    12+350
    12350

    无论采用哪种有效输入形式，均统一返回 CH 格式。

    返回：
    (标准显示值, 米数)

    例如：
    ("CH12+350.000", 12350.0)
    """

    text = value.strip().upper().replace(" ", "")

    if not text:
        return None, None

    # CH12+350、K12+350 或 12+350
    #
    # K 前缀仅用于兼容开发阶段已经存在的旧格式，
    # 新数据统一标准化为 CH。
    match = re.fullmatch(
        r"(?:(?:CH|K))?(\d+)\+(\d+(?:\.\d+)?)",
        text,
    )

    if match:
        km = int(match.group(1))
        meters = Decimal(match.group(2))

        if meters >= 1000:
            raise ValueError("桩号加号后的数值必须小于1000。")

        total = (km * 1000 + meters).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

        return _format_stake(total), float(total)

    # 直接输入总米数，例如 12350
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        total = Decimal(text).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

        return _format_stake(total), float(total)

    raise ValueError("桩号格式不正确，请输入例如 CH12+350。")


if __name__ == "__main__":
    examples = [
        "CH12+350",
        "ch12+350",
        "K12+350",
        "12+350",
        "12350",
        "CH1+005.5",
    ]

    for example in examples:
        print(
            example,
            "->",
            parse_stake(example),
        )
