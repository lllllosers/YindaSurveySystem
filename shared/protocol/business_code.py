"""Pure construction and parsing rules for engineering business codes."""

import re


CANAL_LEVEL_CODES = {
    "01": "干渠",
    "02": "分干渠",
    "03": "支渠",
    "04": "分支渠",
}


def build_business_code(
    department_code: str,
    water_office_code: str,
    canal_level_code: str,
    engineering_type_code: str,
    sequence: int,
) -> str:
    department_code = str(department_code).strip()
    water_office_code = str(water_office_code).strip()
    canal_level_code = str(canal_level_code).strip()
    engineering_type_code = str(engineering_type_code).strip()

    if not re.fullmatch(r"\d+", department_code):
        raise ValueError("基层处业务代码必须为数字。")
    if not re.fullmatch(r"\d{2}", water_office_code):
        raise ValueError("水管所业务代码必须为2位数字，例如01。")
    if canal_level_code not in CANAL_LEVEL_CODES:
        raise ValueError("无效的渠道层级代码。")
    if not re.fullmatch(r"\d{2}", engineering_type_code):
        raise ValueError("工程类型代码必须为2位数字。")
    if sequence < 1 or sequence > 999:
        raise ValueError("顺序号必须在1～999之间。")

    return (
        f"{department_code}-{water_office_code}-{canal_level_code}-"
        f"{engineering_type_code}-{sequence:03d}"
    )


def parse_business_code(business_code: str) -> dict[str, str | int]:
    match = re.fullmatch(
        r"(\d+)-(\d{2})-(\d{2})-(\d{2})-(\d{3})",
        business_code.strip(),
    )
    if match is None:
        raise ValueError("业务编号格式不正确。")

    department_code, office_code, canal_level_code, type_code, sequence = match.groups()
    if canal_level_code not in CANAL_LEVEL_CODES:
        raise ValueError("业务编号中的渠道层级代码无效。")
    return {
        "department_code": department_code,
        "water_office_code": office_code,
        "canal_level_code": canal_level_code,
        "engineering_type_code": type_code,
        "sequence": int(sequence),
    }


def suggest_next_sequence(
    existing_codes: list[str],
    department_code: str,
    water_office_code: str,
    canal_level_code: str,
    engineering_type_code: str,
) -> int:
    sequences: list[int] = []
    for code in existing_codes:
        try:
            parsed = parse_business_code(code)
        except ValueError:
            continue
        if (
            parsed["department_code"] == department_code
            and parsed["water_office_code"] == water_office_code
            and parsed["canal_level_code"] == canal_level_code
            and parsed["engineering_type_code"] == engineering_type_code
        ):
            sequences.append(int(parsed["sequence"]))

    next_sequence = max(sequences, default=0) + 1
    if next_sequence > 999:
        raise ValueError("当前编号前缀下的顺序号已超过999。")
    return next_sequence
