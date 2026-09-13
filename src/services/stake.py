import re


def _format_stake(total_meters: float) -> str:
    """
    将米数转换成引大入秦工程标准桩号显示形式。

    例如：
    12350 -> CH12+350
    12005.5 -> CH12+005.5
    """
    km = int(total_meters // 1000)
    meters = total_meters - km * 1000

    if meters.is_integer():
        meter_text = f"{int(meters):03d}"
    else:
        meter_text = f"{meters:.3f}".rstrip("0").rstrip(".")

        integer_part, decimal_part = meter_text.split(".")
        meter_text = f"{int(integer_part):03d}.{decimal_part}"

    return f"CH{km}+{meter_text}"


def parse_stake(value: str) -> tuple[str | None, float | None]:
    """
    解析常见桩号输入。

    正式标准格式：
    CH12+350

    为提高录入效率并兼容开发阶段旧数据，同时支持：
    CH12+350
    K12+350
    12+350
    12350

    无论采用哪种有效输入形式，均统一返回 CH 格式。

    返回：
    (标准显示值, 米数)

    例如：
    ("CH12+350", 12350.0)
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
        meters = float(match.group(2))

        if meters >= 1000:
            raise ValueError("桩号加号后的数值必须小于1000。")

        total = km * 1000 + meters

        return _format_stake(total), total

    # 直接输入总米数，例如 12350
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        total = float(text)

        return _format_stake(total), total

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
