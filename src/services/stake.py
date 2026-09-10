import re


def _format_stake(total_meters: float) -> str:
    """
    将米数转换成标准桩号显示形式。

    例如：
    12350 -> K12+350
    12005.5 -> K12+005.5
    """
    km = int(total_meters // 1000)
    meters = total_meters - km * 1000

    if meters.is_integer():
        meter_text = f"{int(meters):03d}"
    else:
        meter_text = f"{meters:.3f}".rstrip("0").rstrip(".")

        integer_part, decimal_part = meter_text.split(".")
        meter_text = f"{int(integer_part):03d}." f"{decimal_part}"

    return f"K{km}+{meter_text}"


def parse_stake(value: str) -> tuple[str | None, float | None]:
    """
    解析常见桩号输入。

    支持：
    K12+350
    12+350
    12350

    返回：
    (标准显示值, 米数)

    例如：
    ("K12+350", 12350.0)
    """

    text = value.strip().upper().replace(" ", "")

    if not text:
        return None, None

    # K12+350 或 12+350
    match = re.fullmatch(
        r"K?(\d+)\+(\d+(?:\.\d+)?)",
        text,
    )

    if match:
        km = int(match.group(1))
        meters = float(match.group(2))

        if meters >= 1000:
            raise ValueError("桩号加号后的数值必须小于1000。")

        total = km * 1000 + meters

        return _format_stake(total), total

    # 直接输入总米数，例如 12350
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        total = float(text)

        return _format_stake(total), total

    raise ValueError("桩号格式不正确，请输入例如 K12+350。")


if __name__ == "__main__":
    examples = [
        "K12+350",
        "12+350",
        "12350",
        "K1+005.5",
    ]

    for example in examples:
        print(
            example,
            "->",
            parse_stake(example),
        )
