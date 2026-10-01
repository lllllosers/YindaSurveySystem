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


def main() -> None:
    parser = argparse.ArgumentParser(description="备份 Web 中心 PostgreSQL 与文件存储")
    parser.add_argument("--database-only", action="store_true", help="仅备份数据库，用于迁移前快速快照")
    parser.add_argument("--output", type=Path, help="指定新的备份目录")
    args = parser.parse_args()

    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise SystemExit("没有找到 pg_dump，请安装 PostgreSQL 客户端并加入 PATH。")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = (args.output or BACKEND_DIR / "backups" / stamp).resolve()
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
        "--file", str(dump_path),
    ]
    try:
        result = hidden_run(
            command, env=env, capture_output=True, text=True,
            encoding="mbcs" if os.name == "nt" else locale.getpreferredencoding(False),
            errors="replace", timeout=3600,
        )
        if result.returncode:
            raise RuntimeError("pg_dump 失败：" + result.stderr.strip()[-500:])
        storage = BACKEND_DIR / "storage"
        if not args.database_only and storage.exists():
            shutil.copytree(storage, target / "storage")
        (target / "manifest.json").write_text(
            json.dumps({
                "created_at": datetime.now().astimezone().isoformat(),
                "database": settings.db_name,
                "database_only": args.database_only,
                "storage_included": not args.database_only and storage.exists(),
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    print(f"备份完成：{target}")


if __name__ == "__main__":
    main()
