"""Structured diagnostics shared by the CLI and the unified console."""
import shutil
import tempfile

from alembic.script import ScriptDirectory
from deployment.database import connect_engine, inspect_database, migration_config, preflight


def database_status(config) -> dict:
    engine = connect_engine(config)
    try:
        with engine.connect() as connection:
            snapshot = inspect_database(connection)
        return {"connected": True, "version": snapshot["version"], "revision": snapshot["revision"],
                "head": ScriptDirectory.from_config(migration_config()).get_current_head()}
    finally:
        engine.dispose()


def diagnose(config) -> dict:
    from app.core.config import settings
    from deployment.config import safe_error
    from deployment.postgres import dump_executable
    checks = []
    def check(label, operation):
        try:
            detail = operation()
            checks.append({"name": label, "level": "pass", "detail": str(detail)})
        except Exception as exc:
            checks.append({"name": label, "level": "error", "detail": safe_error(exc)})
    check("生产配置", lambda: config.validate() or "生产模式；精确访问地址；登录与请求保护保持启用")
    check("数据库与结构", lambda: preflight(config))
    def frontend():
        if not (settings.frontend_dist / "index.html").is_file():
            raise RuntimeError("缺少编译后的管理页面。")
        return "正式页面已就绪"
    check("管理页面", frontend)
    for label, folder in (("成果文件夹", settings.storage_dir), ("备份文件夹", settings.backups_dir)):
        def writable(path=folder):
            if not path.is_dir():
                raise RuntimeError("目录不存在；不创建空目录替代已有数据。")
            with tempfile.TemporaryFile(dir=path):
                pass
            return str(path)
        check(label, writable)
    def disk():
        free = shutil.disk_usage(settings.file_base).free
        if free <= settings.min_free_disk_bytes:
            raise RuntimeError("数据盘剩余空间低于保留额度。")
        return f"剩余 {free / 1024**3:.1f} GB"
    check("磁盘空间", disk)
    check("备份工具", lambda: dump_executable(config.pg_bin))
    checks.append({"name": "网络边界", "level": "notice", "detail": "内网 HTTP 传输不加密；其他电脑访问仍须现场确认。"})
    return {"ok": not any(row["level"] == "error" for row in checks), "checks": checks}
