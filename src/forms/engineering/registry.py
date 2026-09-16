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
# 这里只注册已经完成声明式迁移
# 并进入正式运行入口的表单。
#
# 当前：
# - 附表2.5 已迁移；
# - 附表2.6 已迁移；
# - 附表2.1～2.4 仍属于 legacy 页面。
#
# 后续每完成一张表迁移，
# 只需要把对应 FORM_2_X
# 加入此处。
# =============================================================

_ENGINEERING_FORM_DEFINITIONS: tuple[
    EngineeringFormDefinition,
    ...,
] = (
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
    检查业务定义 Registry 中
    必须全局唯一的身份字段。

    EngineeringFormDefinition 自身的
    字段、位置、评价等级和评价项目合法性
    已由其 __post_init__ 在对象创建时完成校验。

    Registry 这里只负责跨表单唯一性。
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
                "EngineeringFormRegistry 中存在重复的 " f"{display_name}。"
            )


_validate_registry(
    _ENGINEERING_FORM_DEFINITIONS,
)


_ENGINEERING_FORM_BY_CODE = {
    definition.form_code: definition for definition in _ENGINEERING_FORM_DEFINITIONS
}


def get_engineering_form_definition(
    form_code: str,
) -> EngineeringFormDefinition | None:
    """
    根据 form_code 获取已经迁移到新框架的
    EngineeringFormDefinition。

    尚未迁移的 legacy 表单返回 None。
    """

    return _ENGINEERING_FORM_BY_CODE.get(
        form_code,
    )


def get_engineering_form_definitions() -> tuple[
    EngineeringFormDefinition,
    ...,
]:
    """
    返回所有已经迁移到新框架的正式表单定义。

    返回不可变 tuple，
    避免调用方修改 Registry。
    """

    return _ENGINEERING_FORM_DEFINITIONS
