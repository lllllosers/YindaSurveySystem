"""The existing deployment pipeline with observable, non-silent stage results."""
from datetime import datetime
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil

from branding import PRODUCT_EXE
from deployment.config import atomic_write, safe_error, validate_admin
from deployment.service import LEGACY_TASK_NOTICE, ServiceManager, health, run

STEPS = (("environment", "检查安装环境"), ("postgres", "检查 PostgreSQL"),
         ("database", "准备专用数据库与运行账号"), ("initialize", "初始化 Web Center"),
         ("install", "安装 Windows 后台服务"), ("start", "启动 Web Center"), ("verify", "检查访问是否正常"))
REMEDIES = {
    "environment": "请确认目录可写，使用完整部署包，并右键主程序选择“以管理员身份运行”。",
    "postgres": "请确认已安装并启动 PostgreSQL 17，核对安装时的管理密码；自定义端口请到高级设置核对。",
    "database": "已有同名对象不会覆盖。请接续本系统已有安装，或由维护人员核对后在高级设置指定新的专用名称。",
    "initialize": "请保留数据和初始化阶段，修正配置后选择接续重试；不要清空数据库。",
    "install": "请使用 Windows 管理员权限，检查服务注册和目录权限；旧任务须先确认停止、必要时导出后人工移除。",
    "start": "请查看服务日志，检查数据库服务、端口占用和数据目录权限。",
    "verify": "请检查本机访问地址和服务日志。本机通过不代表其他办公室电脑可达。",
}


class DeploymentError(RuntimeError):
    def __init__(self, step, reason, log_path):
        self.step, self.reason, self.log_path = step, reason, str(log_path)
        super().__init__(f"{dict(STEPS)[step]}失败：{reason}\n{REMEDIES[step]}\n安装日志：{log_path}")


def install_payload(source: Path, destination: Path) -> None:
    source, destination = source.resolve(), destination.resolve()
    if source == destination:
        return
    if any(destination.is_relative_to(source / name) for name in ("_internal", "service")):
        raise ValueError("程序安装目录不能位于内部运行文件夹中。")
    if not (source / PRODUCT_EXE).is_file() or not (source / "_internal").is_dir() or not (source / "service").is_dir():
        raise RuntimeError("请选择完整 Web Center 部署包，不要只复制主程序。")
    files = [source / PRODUCT_EXE]
    for name in ("_internal", "service"):
        files.extend(p for p in (source / name).rglob("*") if p.is_file() and p.suffix.lower() not in {".xml", ".log"})
    files.extend(p for p in source.iterdir() if p.is_file() and p.suffix in {".md", ".json"})
    for path in files:
        target = destination / path.relative_to(source)
        if target.exists():
            with path.open("rb") as original, target.open("rb") as installed:
                if hashlib.file_digest(original, "sha256").digest() != hashlib.file_digest(installed, "sha256").digest():
                    raise RuntimeError("目标包含不同版本的程序；本安装向导不会覆盖，请选择新的程序目录。")
    for path in files:
        target = destination / path.relative_to(source)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def deploy(source, config, mode, username, password, *, database_admin=None, progress=None):
    stage = "environment"
    events = []
    validated = False
    log_path = config.data_root / "logs/install.log"
    def emit(step, state, detail=""):
        event = {"step": step, "state": state, "detail": detail, "time": datetime.now().astimezone().isoformat()}
        events.append(event)
        if progress:
            progress(step, state, detail)
    def record():
        if not validated:
            return
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(config.data_root / "config/install-status.json", json.dumps({"events": events}, ensure_ascii=False, indent=2))
            with log_path.open("a", encoding="utf-8") as output:
                for event in events:
                    output.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            if progress:
                progress(stage, "failed", "安装日志未能写入，请核对数据目录权限。")
    try:
        emit(stage, "running")
        config.validate()
        validated = True
        if database_admin is not None and mode != "new":
            raise ValueError("接续已有部署时不能创建新库。")
        validate_admin(username, password)
        if os.name != "nt" or not ctypes.windll.shell32.IsUserAnAdmin():
            raise RuntimeError("安装后台服务需要 Windows 管理员权限；请右键根目录主程序，选择“以管理员身份运行”后重试。")
        pointer = config.install_root / "config/deployment.json"
        if pointer.exists():
            from deployment.config import DeploymentConfig
            existing = DeploymentConfig.load(config.install_root)
            if existing.state_file.exists() and (existing.data_root.resolve(), existing.db_host, existing.db_port, existing.db_name, existing.data_layout) != (
                    config.data_root.resolve(), config.db_host, config.db_port, config.db_name, config.data_layout):
                raise RuntimeError("当前安装已绑定其他数据目录或数据库，不能改绑后创建空库替代。")
        manager = ServiceManager(config)
        state = manager.status()
        if state["state"] not in {"absent", "stopped"}:
            raise RuntimeError("请先停止已有 Web 服务，再调整安装配置。")
        if state["state"] != "absent" and not state["owned"]:
            raise RuntimeError("同名服务属于其他目录，拒绝操作。")
        if manager.legacy_task():
            raise RuntimeError(LEGACY_TASK_NOTICE)
        install_payload(source, config.install_root)
        folder = config.data_root / "config"
        folder.mkdir(parents=True, exist_ok=True)
        acl = run(["icacls.exe", folder, "/inheritance:r", "/grant:r", "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F", "*S-1-5-19:(OI)(CI)R", "/T", "/Q"])
        if acl.returncode:
            raise RuntimeError("无法保护运行账号配置，已停止安装；请核对数据目录权限。")
        config.save()
        emit(stage, "complete", "程序位置与运行配置已确认。")
        operations = (
            ("postgres", lambda: manager.server_action("--postgres-check", payload=database_admin)),
            ("database", lambda: manager.server_action("--provision", payload=database_admin) if database_admin is not None else "使用指定的现有数据库，不创建或重置账号。"),
            ("initialize", lambda: manager.server_action("--initialize", payload={"mode": mode, "username": username, "password": password})),
            ("install", manager.install), ("start", lambda: manager.control("start")),
        )
        for stage, operation in operations:
            emit(stage, "running")
            detail = operation()
            emit(stage, "complete", detail)
        stage = "verify"
        emit(stage, "running")
        if not health(config.local_url) or not health(config.local_url, "/api/v1/health/database"):
            raise RuntimeError("本机 Web 或数据库健康检查未通过。")
        emit(stage, "complete", "Web Center 已成功启动。")
        return {"ok": True, "local_url": config.local_url, "message": "Web Center 已成功启动", "log_path": str(log_path)}
    except Exception as exc:
        reason = safe_error(exc)
        emit(stage, "failed", reason)
        raise DeploymentError(stage, reason, log_path) from None
    finally:
        record()
