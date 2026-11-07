"""Explicit creation of a new dedicated database; never alters an existing name."""
import json
import re

import psycopg
from psycopg import sql

from deployment.config import atomic_write


def create_dedicated_database(config, credentials: dict) -> str:
    config.validate()
    if credentials.get("create_dedicated") is not True:
        raise ValueError("未选择创建本系统专用数据库。")
    if config.db_host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("自动创建仅支持本机 PostgreSQL；远程数据库请由维护人员配置。")
    for value in (config.db_name, config.db_user):
        if not re.fullmatch(r"yinda_[a-z0-9_]{1,57}", value):
            raise ValueError("自动创建的数据库与账号名称需以 yinda_ 开头，使用小写字母、数字或下划线。")
    if config.state_file.exists() or any((config.data_root / "data/storage").rglob("*")):
        raise RuntimeError("已有部署或成果文件，不能创建新的数据库替代。")
    progress_file = config.data_root / "config/database-creation.json"
    identity = [config.db_host, config.db_port, config.db_name, config.db_user]
    with psycopg.connect(host=config.db_host, port=config.db_port, dbname="postgres",
            user=credentials["username"], password=credentials["password"], connect_timeout=5, autocommit=True) as connection:
        if connection.info.server_version // 10000 != 17:
            raise RuntimeError("需要 PostgreSQL 17。")
        if not connection.execute("SELECT pg_try_advisory_lock(719240138)").fetchone()[0]:
            raise RuntimeError("另一个数据库创建操作正在运行。")
        try:
            database = connection.execute("SELECT oid,datdba FROM pg_database WHERE datname=%s", (config.db_name,)).fetchone()
            role = connection.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (config.db_user,)).fetchone()
            if progress_file.exists():
                previous = json.loads(progress_file.read_text(encoding="utf-8"))
                if previous.get("identity") == identity and previous.get("phase") == "ready" and database and role and previous.get("database_oid") == database[0] and previous.get("role_oid") == role[0] == database[1]:
                    return "本次部署的专用数据库已创建，未更改账号或已有内容。"
                raise RuntimeError("上次创建未完成或名称不匹配。已保留进度，请维护人员核对；不会自动删除或覆盖任何对象。")
            if database or role:
                raise RuntimeError("数据库或账号名称已存在，未作任何修改。请选择新的专用名称，或使用接续已有部署。")
            progress = {"identity": identity, "phase": "creating"}
            atomic_write(progress_file, json.dumps(progress, ensure_ascii=False, indent=2))
            connection.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Identifier(config.db_user), sql.Literal(config.db_password)))
            progress["phase"] = "role_created"
            atomic_write(progress_file, json.dumps(progress, ensure_ascii=False, indent=2))
            connection.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(config.db_name), sql.Identifier(config.db_user)))
            connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(config.db_name)))
            progress.update(phase="ready", database_oid=connection.execute("SELECT oid FROM pg_database WHERE datname=%s", (config.db_name,)).fetchone()[0], role_oid=connection.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (config.db_user,)).fetchone()[0])
            atomic_write(progress_file, json.dumps(progress, ensure_ascii=False, indent=2))
        finally:
            connection.execute("SELECT pg_advisory_unlock(719240138)")
    return "已创建本系统专用数据库和普通运行账号；数据库管理密码未保存。"
