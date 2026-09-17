def get_worst_grade(
    grade_options,
    grades,
):
    """
    按 grade_options 从好到差的顺序，
    返回已评价项目中的最差等级。

    例如：
        ("A", "B", "C", "D")
        A, A, B -> B
        A, C, B -> C

    空 grades 返回 None。
    出现定义外等级时抛出 ValueError。
    """
    options = tuple(
        str(grade).strip()
        for grade in grade_options
    )

    if not options:
        raise ValueError(
            "评价等级不能为空。"
        )

    if (
        any(not grade for grade in options)
        or len(options) != len(set(options))
    ):
        raise ValueError(
            "评价等级定义无效。"
        )

    rank = {
        grade: index
        for index, grade
        in enumerate(options)
    }

    normalized = []

    for grade in grades:
        if grade is None:
            continue

        value = str(grade).strip()

        if not value:
            continue

        if value not in rank:
            raise ValueError(
                "存在定义外评价等级："
                f"{value}"
            )

        normalized.append(
            value
        )

    if not normalized:
        return None

    return max(
        normalized,
        key=rank.__getitem__,
    )
