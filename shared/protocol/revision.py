"""Pure revision and conflict classification shared by import workflows."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from typing import Any


def safe_revision(value: object, default: int = 1) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(0, parsed)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def classify_revision_values(
    *,
    same_identity: bool,
    same_content: bool,
    incoming_revision: object,
    local_revision: object,
    source_revision: object,
) -> tuple[str, dict[str, int | bool] | None]:
    """Classify an incoming entity using the desktop V1.2 merge contract."""

    if not same_identity:
        return "identity_conflict", None

    incoming = safe_revision(incoming_revision, 1)
    local = safe_revision(local_revision, 1)
    source = safe_revision(source_revision, 0)
    metadata: dict[str, int | bool] = {
        "incoming_revision": incoming,
        "local_revision": local,
        "source_revision": source,
        "same_content": same_content,
    }

    if same_content:
        return "existing", metadata
    if incoming < source:
        return "stale", metadata
    if incoming == source:
        return "same_revision_conflict", metadata
    if local > source:
        return "diverged", metadata
    return "update", metadata


def classify_revision(
    local_item: Mapping[str, Any],
    incoming_item: Mapping[str, Any],
    *,
    identity_signature: Callable[[Mapping[str, Any]], object],
    content_signature: Callable[[Mapping[str, Any]], object],
) -> tuple[str, dict[str, int | bool] | None]:
    """Classify two serialized entities without knowing either database."""

    return classify_revision_values(
        same_identity=(
            canonical_json(identity_signature(local_item))
            == canonical_json(identity_signature(incoming_item))
        ),
        same_content=(
            canonical_json(content_signature(local_item))
            == canonical_json(content_signature(incoming_item))
        ),
        incoming_revision=incoming_item.get("revision_no"),
        local_revision=local_item.get("revision_no"),
        source_revision=local_item.get("source_revision_no"),
    )
