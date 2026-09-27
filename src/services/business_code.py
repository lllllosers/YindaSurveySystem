"""Desktop adapter for the shared business-code contract."""

from forms.engineering.registry import get_engineering_form_definition
from shared.protocol.business_code import (
    CANAL_LEVEL_CODES,
    build_business_code,
    parse_business_code,
    suggest_next_sequence,
)


def get_engineering_type_code(form_code: str) -> str:
    """Resolve the form-specific type code through the desktop registry."""

    definition = get_engineering_form_definition(form_code)
    if definition is None:
        raise ValueError(f"暂不支持调查表：{form_code}")
    return definition.business_type_code


__all__ = [
    "CANAL_LEVEL_CODES",
    "build_business_code",
    "get_engineering_type_code",
    "parse_business_code",
    "suggest_next_sequence",
]
