"""Explicit new/continue deployment. Never creates a database or resets user data."""
from __future__ import annotations

import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.pool import NullPool

from deployment.config import DeploymentConfig, atomic_write


def migration_config() -> Config:
    from app.core.config import BACKEND_DIR
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def connect_engine(config: DeploymentConfig):
    from sqlalchemy import URL
    return create_engine(URL.create("postgresql+psycopg", username=config.db_user,
        password=config.db_password, host=config.db_host, port=config.db_port, database=config.db_name),
        connect_args={"connect_timeout": 5}, poolclass=NullPool)


def inspect_database(connection) -> dict:
    version = int(connection.scalar(text("SHOW server_version_num")))
    if version // 10000 != 17:
        raise RuntimeError("本批正式部署需要 PostgreSQL 17。")
    return {"tables": set(inspect(connection).get_table_names()),
            "revision": MigrationContext.configure(connection).get_current_revision(), "version": version}


def check_adoption(config: DeploymentConfig, mode: str, snapshot: dict) -> None:
    if mode not in {"new", "continue"}:
        raise ValueError("请选择新部署或接续已有部署。")
    if mode == "new":
        if config.state_file.exists() or snapshot["tables"] or any((config.data_root / "data" / "storage").rglob("*")):
            raise RuntimeError("发现已有部署、数据库表或成果文件；禁止初始化，请选择接续。")
    else:
        # No automatic copy or guessing of old storage paths.
        if not config.state_file.is_file():
            raise RuntimeError("缺少部署标识。旧源码/便携部署须先离线迁移数据库和完整 storage，并由维护人员登记；不能直接接管。")
        state = json.loads(config.state_file.read_text(encoding="utf-8"))
        identity = [config.db_host, config.db_port, config.db_name]
        if state.get("database") != identity or state.get("data_root") != str(config.data_root.resolve()):
            raise RuntimeError("数据库或数据目录与部署标识不匹配，拒绝接续。")
        if not (config.data_root / "data" / "storage").is_dir():
            raise RuntimeError("登记部署的 storage 目录丢失，拒绝创建空目录替代。")
        if not snapshot["revision"]:
            # A failed new deployment may resume only if the database remains empty.
            if state.get("phase") != "initializing" or snapshot["tables"]:
                raise RuntimeError("已有数据库没有可识别的 Alembic 版本，拒绝初始化。")
        elif snapshot["revision"] not in {r.revision for r in ScriptDirectory.from_config(migration_config()).walk_revisions()}:
            raise RuntimeError("数据库版本不属于本程序，拒绝迁移。")


def initialize(config: DeploymentConfig, mode: str, username: str, password: str) -> str:
    config.validate()
    if len(password) < 12 or len(password) > 128:
        raise ValueError("首次管理员密码需要 12 至 128 个字符。")
    engine = connect_engine(config)
    try:
        with engine.connect() as connection:
            if not connection.scalar(text("SELECT pg_try_advisory_lock(719240137)")):
                raise RuntimeError("另一个部署操作正在运行。")
            try:
                snapshot = inspect_database(connection)
                check_adoption(config, mode, snapshot)
                config.ensure_directories()
                state = {"schema": 1, "database": [config.db_host, config.db_port, config.db_name],
                         "data_root": str(config.data_root.resolve()), "phase": "initializing"}
                atomic_write(config.state_file, json.dumps(state, ensure_ascii=False, indent=2))
                connection.commit()
                cfg = migration_config()
                cfg.attributes["connection"] = connection
                command.upgrade(cfg, "head")
                connection.commit()
                from sqlalchemy.orm import Session
                from app.models.auth import User
                from app.schemas.auth import UserCreate
                from app.services.auth_service import create_user
                from app.services.master_data_service import ensure_seeded
                with Session(bind=connection, expire_on_commit=False) as db:
                    ensure_seeded(db)
                    if db.scalar(select(User).where(User.role == "admin", User.is_active.is_(True))) is None:
                        create_user(db, UserCreate(username=username, display_name="系统管理员",
                                    password=password, role="admin", is_active=True))
                state["phase"] = "ready"
                atomic_write(config.state_file, json.dumps(state, ensure_ascii=False, indent=2))
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(719240137)"))
                connection.commit()
    finally:
        engine.dispose()
    return "数据库迁移和管理员检查完成；已有管理员及业务数据保留。"


def preflight(config: DeploymentConfig) -> str:
    engine = connect_engine(config)
    try:
        with engine.connect() as connection:
            snapshot = inspect_database(connection)
            check_adoption(config, "continue", snapshot)
            if snapshot["revision"] != ScriptDirectory.from_config(migration_config()).get_current_head():
                raise RuntimeError("数据库迁移未到当前版本，请通过部署向导接续。")
        if json.loads(config.state_file.read_text(encoding="utf-8")).get("phase") != "ready":
            raise RuntimeError("部署尚未完成，请重试部署向导。")
    finally:
        engine.dispose()
    return "PostgreSQL 17 连接正常，结构为当前版本。"
