import re


# 当前附表2工程类型代码
ENGINEERING_TYPE_CODES = {
    "form_2_1": "01",  # 防渗衬砌渠道
    "form_2_2": "02",  # 水闸
}


# 当前渠道层级代码
CANAL_LEVEL_CODES = {
    "01": "干渠",
    "02": "分干渠",
    "03": "支渠",
    "04": "分支渠",
}


def get_engineering_type_code(form_code: str) -> str:
    """
    根据调查表代码获取业务编号中的工程类型代码。
    """
    try:
        return ENGINEERING_TYPE_CODES[form_code]
    except KeyError as error:
        raise ValueError(
            f"暂不支持调查表：{form_code}"
        ) from error


def build_business_code(
    department_code: str,
    water_office_code: str,
    canal_level_code: str,
    engineering_type_code: str,
    sequence: int,
) -> str:
    """
    生成五段式业务编号。

    格式：
    基层处-水管所-渠道层级-工程类型-顺序号

    示例：
    1-01-03-02-001
    """

    department_code = str(
        department_code
    ).strip()

    water_office_code = str(
        water_office_code
    ).strip()

    canal_level_code = str(
        canal_level_code
    ).strip()

    engineering_type_code = str(
        engineering_type_code
    ).strip()

    if not re.fullmatch(
        r"\d+",
        department_code,
    ):
        raise ValueError(
            "基层处业务代码必须为数字。"
        )

    if not re.fullmatch(
        r"\d{2}",
        water_office_code,
    ):
        raise ValueError(
            "水管所业务代码必须为2位数字，例如01。"
        )

    if canal_level_code not in CANAL_LEVEL_CODES:
        raise ValueError(
            "无效的渠道层级代码。"
        )

    if not re.fullmatch(
        r"\d{2}",
        engineering_type_code,
    ):
        raise ValueError(
            "工程类型代码必须为2位数字。"
        )

    if sequence < 1 or sequence > 999:
        raise ValueError(
            "顺序号必须在1～999之间。"
        )

    sequence_code = f"{sequence:03d}"

    return (
        f"{department_code}-"
        f"{water_office_code}-"
        f"{canal_level_code}-"
        f"{engineering_type_code}-"
        f"{sequence_code}"
    )


def parse_business_code(
    business_code: str,
) -> dict[str, str | int]:
    """
    解析完整业务编号。

    示例：
    1-01-03-02-001
    """

    business_code = business_code.strip()

    match = re.fullmatch(
        r"(\d+)-(\d{2})-(\d{2})-(\d{2})-(\d{3})",
        business_code,
    )

    if match is None:
        raise ValueError(
            "业务编号格式不正确。"
        )

    (
        department_code,
        water_office_code,
        canal_level_code,
        engineering_type_code,
        sequence_code,
    ) = match.groups()

    if canal_level_code not in CANAL_LEVEL_CODES:
        raise ValueError(
            "业务编号中的渠道层级代码无效。"
        )

    return {
        "department_code": department_code,
        "water_office_code": water_office_code,
        "canal_level_code": canal_level_code,
        "engineering_type_code": (
            engineering_type_code
        ),
        "sequence": int(sequence_code),
    }


def suggest_next_sequence(
    existing_codes: list[str],
    department_code: str,
    water_office_code: str,
    canal_level_code: str,
    engineering_type_code: str,
) -> int:
    """
    根据相同前四段编号，建议下一个顺序号。

    当前属于开发阶段默认逻辑。
    如果甲方后续确认顺序号需按具体渠道分别排序，
    只需修改这一层规则，不影响编号格式。
    """

    sequences = []

    for code in existing_codes:
        try:
            parsed = parse_business_code(code)
        except ValueError:
            continue

        if (
            parsed["department_code"]
            == department_code
            and parsed["water_office_code"]
            == water_office_code
            and parsed["canal_level_code"]
            == canal_level_code
            and parsed["engineering_type_code"]
            == engineering_type_code
        ):
            sequences.append(
                int(parsed["sequence"])
            )

    if not sequences:
        return 1

    next_sequence = max(sequences) + 1

    if next_sequence > 999:
        raise ValueError(
            "当前编号前缀下的顺序号已超过999。"
        )

    return next_sequence


if __name__ == "__main__":
    form_code = "form_2_2"

    engineering_type_code = (
        get_engineering_type_code(form_code)
    )

    code = build_business_code(
        department_code="1",
        water_office_code="01",
        canal_level_code="03",
        engineering_type_code=engineering_type_code,
        sequence=1,
    )

    print("生成编号：", code)
    print("解析结果：", parse_business_code(code))

    existing = [
        "1-01-03-02-001",
        "1-01-03-02-002",
        "1-01-03-02-003",
    ]

    next_number = suggest_next_sequence(
        existing_codes=existing,
        department_code="1",
        water_office_code="01",
        canal_level_code="03",
        engineering_type_code="02",
    )

    print("建议顺序号：", next_number)