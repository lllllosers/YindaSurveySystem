"""Reset Web business data for a new installation, retaining schema and official baseline."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from sqlalchemy import func, inspect, select, text

from app.core.config import BACKEND_DIR, settings
from app.db.session import SessionLocal, engine
from app.services.master_data_service import ensure_seeded


TABLES = (
    "auth_sessions", "audit_events", "central_engineering_assets",
    "central_survey_records", "central_inspection_results", "central_survey_media",
    "result_submissions", "online_survey_entries", "survey_tasks",
    "survey_batches", "projects", "registration_invites", "users",
    "master_management_scopes", "master_canals", "master_offices",
    "master_departments", "master_data_state",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="清空 Web 中心数据并恢复正式基础资料初始基线")
    parser.add_argument("--execute", action="store_true", help="执行清空；默认仅预览数量")
    parser.add_argument("--confirm", help="必须填写当前数据库名称，防止误操作")
    args = parser.parse_args()

    with engine.connect() as connection:
        existing = set(inspect(connection).get_table_names())
        missing = set(TABLES) - existing
        if missing:
            raise SystemExit(f"数据库结构不完整，停止清空：{sorted(missing)}")
        print(f"数据库：{settings.db_host}:{settings.db_port}/{settings.db_name}")
        for table in TABLES:
            count = connection.scalar(select(func.count()).select_from(text(table)))
            print(f"{table}: {count}")

    if not args.execute:
        print("仅预览；如确认要重置，请使用 --execute --confirm <数据库名称>。执行时会先完整备份。")
        return
    if args.confirm != settings.db_name:
        raise SystemExit("确认值与当前数据库名称不一致，未执行清空。")

    subprocess.run([sys.executable, "-m", "app.cli.backup_web_center"], check=True, cwd=BACKEND_DIR)
    with SessionLocal() as db:
        db.execute(text("TRUNCATE TABLE " + ", ".join(TABLES) + " RESTART IDENTITY"))
        ensure_seeded(db)

    storage = (BACKEND_DIR / "storage").resolve()
    if not storage.is_relative_to(BACKEND_DIR.resolve()) or storage == BACKEND_DIR.resolve():
        raise RuntimeError("存储目录超出 Web 后端目录，拒绝清理。")
    if storage.exists():
        shutil.rmtree(storage)
    print("Web 业务数据、账号及上传文件已清空；正式基础资料已恢复初始基线，数据库迁移记录保留。")
    print("请运行 python -m app.cli.create_admin 创建新的首位管理员。")


if __name__ == "__main__":
    main()
