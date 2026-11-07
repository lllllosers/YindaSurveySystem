"""Copy only the immutable application payload, never runtime data."""
from __future__ import annotations

import hashlib
import ctypes
import os
from pathlib import Path
import shutil

from deployment.config import DeploymentConfig
from deployment.service import LEGACY_TASK_NOTICE, ServiceManager


def install_payload(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        return
    if destination.resolve().is_relative_to(source / "console") or destination.resolve().is_relative_to(source / "service"):
        raise ValueError("安装目录不能位于程序文件目录中。")
    files = []
    for name in ("console", "service"):
        if not (source / name).is_dir():
            raise RuntimeError("请选择完整 EXE 交付包运行部署向导。")
        files.extend(p for p in (source / name).rglob("*") if p.is_file() and p.suffix.lower() not in {".xml", ".log"})
    # Check all targets before copying. V1 does not replace installed releases.
    for path in files:
        target = destination / path.relative_to(source)
        if target.exists():
            with path.open("rb") as original, target.open("rb") as installed:
                if hashlib.file_digest(original, "sha256").digest() != hashlib.file_digest(installed, "sha256").digest():
                    raise RuntimeError("目标包含不同版本程序，第一批向导不会覆盖；请选择空目录。")
    for path in files:
        target = destination / path.relative_to(source)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def deploy(source: Path, config: DeploymentConfig, mode: str, username: str, password: str, *, database_admin: dict | None = None) -> str:
    config.validate()
    if database_admin is not None and mode != "new":
        raise ValueError("接续已有部署时不能创建新库。")
    if os.name == "nt" and not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError("首次部署和服务安装需要管理员权限，请右键以管理员身份运行控制台。")
    pointer = config.install_root / "config" / "deployment.json"
    if pointer.exists():
        existing = DeploymentConfig.load(config.install_root)
        if existing.state_file.exists() and (existing.data_root.resolve(), existing.db_host, existing.db_port, existing.db_name) != (
                config.data_root.resolve(), config.db_host, config.db_port, config.db_name):
            raise RuntimeError("该安装目录已绑定其他数据库或数据目录，不能由首次部署向导改绑。")
    manager = ServiceManager(config)
    status = manager.status()
    if status["state"] not in {"absent", "stopped"}:
        raise RuntimeError("请先停止已安装服务，再修改部署配置。")
    if status["state"] != "absent" and not status["owned"]:
        raise RuntimeError("同名服务属于其他安装目录，拒绝部署。")
    if manager.legacy_task():
        raise RuntimeError(LEGACY_TASK_NOTICE)
    install_payload(source, config.install_root)
    config.save()
    if database_admin is not None:
        manager.server_action("--provision", payload=database_admin)
    message = manager.server_action("--initialize", payload={"mode": mode, "username": username, "password": password})
    message += "\n" + manager.install()
    message += "\n" + manager.control("start")
    return message
