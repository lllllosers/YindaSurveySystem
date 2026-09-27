"""Keep a reserve on the filesystem used by upload storage."""

from pathlib import Path
import shutil

from app.core.config import settings


class InsufficientStorageError(OSError):
    pass


def require_free_space(storage_path: Path, incoming_bytes: int) -> None:
    free = shutil.disk_usage(storage_path).free
    if free - max(incoming_bytes, 0) < settings.min_free_disk_bytes:
        raise InsufficientStorageError("服务器存储空间不足，请联系管理员。")
