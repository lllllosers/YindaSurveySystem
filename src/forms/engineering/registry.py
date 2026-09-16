from forms.engineering.form_2_1 import (
    FORM_2_1,
)

from forms.engineering.form_2_2 import (
    FORM_2_2,
)

from forms.engineering.form_2_3 import (
    FORM_2_3,
)

from forms.engineering.form_2_4 import (
    FORM_2_4,
)

from forms.engineering.form_2_5 import (
    FORM_2_5,
)

from forms.engineering.form_2_6 import (
    FORM_2_6,
)

from forms.engineering.models import (
    EngineeringFormDefinition,
)


# =============================================================
# 已迁移到 Engineering Form Framework 的正式表单定义
# =============================================================
#
# 附表2.1～2.6均已完成声明式迁移，
# 并由本 Registry 作为工程调查表身份的
# 唯一代码级事实来源。
# =============================================================

_ENGINEERING_FORM_DEFINITIONS: tuple[
    EngineeringFormDefinition,
    ...,
] = (
    FORM_2_1,
    FORM_2_2,
    FORM_2_3,
    FORM_2_4,
    FORM_2_5,
    FORM_2_6,
)


def _validate_registry(
    definitions: tuple[
        EngineeringFormDefinition,
        ...,
    ],
) -> None:
    """
    检查 Registry 中必须跨表唯一的身份字段。

    EngineeringFormDefinition 自身负责
    单张表内部合同校验；
    Registry 只负责跨表唯一性。
    """

    unique_attributes = (
        (
            "form_code",
            "form_code",
        ),
        (
            "form_number",
            "form_number",
        ),
        (
            "business_type_code",
            "business_type_code",
        ),
    )

    for (
        attribute_name,
        display_name,
    ) in unique_attributes:
        values = [
            getattr(
                definition,
                attribute_name,
            )
            for definition in definitions
        ]

        if len(values) != len(set(values)):
            raise ValueError(
                "EngineeringFormRegistry "
                "中存在重复的 "
                f"{display_name}。"
            )


_validate_registry(
    _ENGINEERING_FORM_DEFINITIONS,
)


_ENGINEERING_FORM_BY_CODE = {
    definition.form_code: definition
    for definition
    in _ENGINEERING_FORM_DEFINITIONS
}


def get_engineering_form_definition(
    form_code: str,
) -> EngineeringFormDefinition | None:
    """
    根据 form_code 获取正式
    EngineeringFormDefinition。
    """

    return _ENGINEERING_FORM_BY_CODE.get(
        form_code,
    )


def get_engineering_form_definitions() -> tuple[
    EngineeringFormDefinition,
    ...,
]:
    """
    返回所有已经迁移到工程调查框架的
    正式表单定义。

    使用不可变 tuple，
    避免调用方修改 Registry。
    """

    return _ENGINEERING_FORM_DEFINITIONS
