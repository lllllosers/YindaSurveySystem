"""Single console operations facade; deployment adapters never form a second console."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

from deployment.config import DeploymentConfig, atomic_write, safe_error
from deployment.service import LEGACY_TASK_NOTICE, SERVICE_ID, ServiceManager, health, lan_ipv4, run
from branding import product_version

CONSOLE_VERSION = product_version()


def resolve_home() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def tail(path: Path, lines: int = 100) -> str:
    if not path.is_file():
        return "暂无日志。"
    with path.open("rb") as source:
        source.seek(0, 2)
        source.seek(max(0, source.tell() - 65536))
        return "\n".join(source.read().decode("utf-8", errors="replace").splitlines()[-lines:])


class ServerManager:
    def __init__(self, home: Path | None = None):
        self.home = (home or resolve_home()).resolve()

    @property
    def config(self) -> DeploymentConfig | None:
        return DeploymentConfig.load(self.home) if (self.home / "config/deployment.json").is_file() else None

    def require_config(self) -> DeploymentConfig:
        config = self.config
        if config is None:
            raise RuntimeError("请先完成首次安装。")
        return config

    def _log(self, message: str, name: str = "operations") -> None:
        config = self.config
        if config:
            folder = config.data_root / "logs"
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / f"{name}.log").open("a", encoding="utf-8") as output:
                output.write(datetime.now().astimezone().isoformat() + " " + message + "\n")

    def _control(self, action: str) -> str:
        try:
            message = ServiceManager(self.require_config()).control(action)
            self._log(message)
            return message
        except Exception as exc:
            self._log(safe_error(exc))
            raise

    def start(self):
        return self._control("start")

    def stop(self):
        return self._control("stop")

    def restart(self):
        return self._control("restart")

    def install(self):
        return ServiceManager(self.require_config()).install()

    def install_autostart(self):
        message = ServiceManager(self.require_config()).install_autostart()
        self._log(message)
        return message

    def preflight(self) -> dict:
        config = self.require_config()
        result = json.loads(ServiceManager(config).server_action("--diagnose"))
        result["checked_at"] = datetime.now().astimezone().isoformat()
        atomic_write(config.data_root / "config/preflight.status.json", json.dumps(result, ensure_ascii=False, indent=2))
        self._log("\n".join(f"{row['level']}: {row['name']} · {row['detail']}" for row in result["checks"]), "preflight")
        return result

    def backup(self) -> str:
        """Quiesce Web writes while dumping DB and copying its referenced files."""
        config = self.require_config()
        manager = ServiceManager(config)
        state = manager.status()
        if not state["owned"] or state["state"] not in {"running", "stopped"}:
            raise RuntimeError("仅能备份此目录已确认归属的正式服务；请先安装服务或等待状态稳定。")
        resume = state["state"] == "running"
        if resume:
            manager.control("stop")
        message = ""
        failure = None
        try:
            message = manager.server_action("--backup")
            if not message.startswith("备份完成："):
                raise RuntimeError("备份未返回完成标识，请检查备份日志。")
            self._log(message, "backup")
        except Exception as exc:
            failure = exc
            self._log(safe_error(exc), "backup")
        finally:
            if resume:
                try:
                    manager.control("start")
                except Exception:
                    raise RuntimeError((message or "备份未完成。") + "\n备份后 Web 未恢复运行，请在运行管理中检查并启动服务。") from None
        if failure:
            raise failure
        return message + ("\nWeb 服务已恢复运行。" if resume else "")

    def deploy(self, config, mode, username, password, database_admin=None, *, progress=None):
        from deployment.installer import deploy
        try:
            message = deploy(self.home, config, mode, username, password, database_admin=database_admin, progress=progress)
        except Exception:
            if (config.install_root / "config/deployment.json").is_file():
                self.home = config.install_root
            raise
        self.home = config.install_root
        self._log("部署完成。")
        return message

    def backup_status(self, config) -> dict:
        for path in sorted((config.data_root / "backups").glob("*/manifest.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("complete") is not False and data.get("database") == config.db_name and data.get("storage_included") and (path.parent / "database.dump").is_file() and (path.parent / "storage").is_dir():
                    return {"created_at": data["created_at"], "path": str(path.parent), "legacy": data.get("complete") is not True}
            except (OSError, ValueError, KeyError):
                pass
        return {}

    def status(self) -> dict:
        config = self.config
        result = {"config": config, "addresses": lan_ipv4(), "version": CONSOLE_VERSION, "checked_at": datetime.now().strftime("%H:%M:%S")}
        if not config:
            return result
        manager = ServiceManager(config)
        service = manager.status()
        result.update(service=service, web=service["owned"] and service["state"] == "running" and health(config.local_url),
            backup=self.backup_status(config), urls=self.access_urls(config, result["addresses"]))
        try:
            result["database"] = json.loads(manager.server_action("--status"))
        except Exception as exc:
            result["database"] = {"connected": False, "detail": safe_error(exc)}
        result["postgres_service"] = "未指定服务名"
        if config.postgres_service_name:
            query = run(["sc.exe", "query", config.postgres_service_name])
            result["postgres_service"] = "运行中" if query.returncode == 0 and "RUNNING" in query.stdout else "未确认运行"
        try:
            result["preflight"] = json.loads((config.data_root / "config/preflight.status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            result["preflight"] = {}
        result["disk"] = f"{shutil.disk_usage(config.data_root).free / 1024**3:.1f} GB"
        result["public"] = "未配置"
        if config.public_base_url:
            result["public"] = "本机检查通过" if health(config.public_base_url) else "未验证通过"
        return result

    @staticmethod
    def access_urls(config, addresses):
        hosts = {h.strip() for h in config.allowed_hosts.split(",")}
        return [f"http://{ip}:{config.web_port}" for ip in addresses if ip in hosts and config.listen_host in {"0.0.0.0", ip}]

    def logs(self, name: str) -> str:
        root = self.require_config().data_root / "logs"
        if name in {"operations", "preflight", "backup"}:
            return tail(root / f"{name}.log")
        files = sorted((p for p in root.glob("*.log") if p.stem not in {"operations", "preflight", "backup"}), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
        return "\n\n".join(p.name + "\n" + tail(p) for p in files) or "暂无服务日志。"
