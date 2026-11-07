"""Back up the Web center database and optionally its file storage."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import locale
import os
from pathlib import Path
import shutil

from app.core.config import BACKEND_DIR, settings
from app.core.windows_subprocess import hidden_run


def create_backup(*, database_only: bool = False, output: Path | None = None) -> Path:
    if settings.data_root and not database_only and not settings.storage_dir.is_dir():
        raise RuntimeError("成果目录丢失，拒绝生成缺少成果文件的完整备份。")
    if settings.data_root:
        from deployment.postgres import dump_executable
        pg_dump = str(dump_executable(settings.pg_bin))
    else:
        pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("没有找到 PostgreSQL 备份工具。")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = (output or settings.backups_dir / stamp).resolve()
    expected_parent = target.parent.resolve()
    target.mkdir(parents=True, exist_ok=False)
    dump_path = target / "database.dump"
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.db_password
    env["LC_MESSAGES"] = "C"
    env["LANG"] = "C"
    command = [
        pg_dump,
        "--host", settings.db_host,
        "--port", str(settings.db_port),
        "--username", settings.db_user,
        "--dbname", settings.db_name,
        "--format", "custom",
        "--no-password",
        "--file", str(dump_path),
    ]
    try:
        result = hidden_run(
            command, env=env, capture_output=True, text=True,
            encoding="mbcs" if os.name == "nt" else locale.getpreferredencoding(False),
            errors="replace", timeout=3600,
        )
        if result.returncode:
            raise RuntimeError(f"数据库备份失败（pg_dump 退出码 {result.returncode}），请检查数据库连接与备份工具版本。")
        storage = settings.storage_dir
        if not database_only and storage.exists():
            shutil.copytree(storage, target / "storage")
        (target / "manifest.json").write_text(
            json.dumps({
                "created_at": datetime.now().astimezone().isoformat(),
                "database": settings.db_name,
                "database_only": database_only,
                "storage_included": not database_only and storage.exists(),
                "complete": True,
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        if target.resolve() == target and target.parent.resolve() == expected_parent and not target.is_symlink():
            shutil.rmtree(target, ignore_errors=True)
        raise
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="备份 Web 中心 PostgreSQL 与文件存储")
    parser.add_argument("--database-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = create_backup(database_only=args.database_only, output=args.output)
    print(f"备份完成：{target}")


if __name__ == "__main__":
    main()
