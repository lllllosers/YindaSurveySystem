"""The validated pre-monorepo public form contract must remain unchanged."""
from dataclasses import fields, is_dataclass
from hashlib import sha256
import json
from pathlib import Path

from shared.forms.engineering.registry import get_engineering_form_definitions


def canonical(value):
    if is_dataclass(value):
        return {field.name: canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [canonical(item) for item in value]
    if callable(value):
        return {"formatter": value.__name__}
    return value


def test_fourteen_official_contracts_match_validated_baseline():
    expected = json.loads((Path(__file__).parent / "fixtures/engineering_core_sha256.json").read_text(encoding="utf-8"))
    definitions = get_engineering_form_definitions()
    assert len(definitions) == 14
    actual = {}
    for definition in definitions:
        assert not hasattr(definition, "list_definition")
        assert not hasattr(definition, "summary_export_definition")
        content = json.dumps(canonical(definition), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        actual[definition.form_code] = sha256(content.encode("utf-8")).hexdigest()
    assert actual == expected
