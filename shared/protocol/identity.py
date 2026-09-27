"""Stable identity rules for official master data."""

from hashlib import sha256


MASTER_IDENTITY_NAMESPACE = "yinda-survey-official-master-v1"
SUPPORTED_MASTER_ENTITY_KINDS = frozenset(
    {"organization", "canal", "canal_management_scope"}
)


def deterministic_master_uid(
    entity_kind: str,
    master_key: str,
    *,
    namespace: str = MASTER_IDENTITY_NAMESPACE,
) -> str:
    """Return the same 32-character UID on desktop and Web."""

    cleaned_kind = str(entity_kind or "").strip().lower()
    cleaned_key = str(master_key or "").strip()
    cleaned_namespace = str(namespace or "").strip()

    if cleaned_kind not in SUPPORTED_MASTER_ENTITY_KINDS:
        raise ValueError("不支持的正式主数据实体类型。")
    if not cleaned_key:
        raise ValueError("master_key 不能为空。")
    if not cleaned_namespace:
        raise ValueError("identity namespace 不能为空。")

    payload = f"{cleaned_namespace}:{cleaned_kind}:{cleaned_key}".encode("utf-8")
    return sha256(payload).hexdigest()[:32]
