from __future__ import annotations

from dataclasses import dataclass, field, asdict
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse

from dotenv import dotenv_values


def validate_admin(username: str, password: str) -> str:
    username = username.strip().lower()
    if not 1 <= len(username) <= 80 or not username.replace("_", "").replace("-", "").isalnum():
        raise ValueError("管理员账号请使用字母、数字、中文、下划线或连字符，最多 80 个字符。")
    if not 8 <= len(password) <= 128:
        raise ValueError("系统管理员密码需要 8 至 128 个字符。")
    return username


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".yinda-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass
class DeploymentConfig:
    install_root: Path
    data_root: Path
    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "yinda_web_center"
    db_user: str = "yinda_web_user"
    db_password: str = field(default="", repr=False)
    listen_host: str = "0.0.0.0"
    web_port: int = 8000
    allowed_hosts: str = "127.0.0.1,localhost"
    transport_mode: str = "lan_http"
    pg_bin: str = ""
    postgres_service_name: str = ""
    public_base_url: str = ""
    data_layout: str = "flat"

    @property
    def file_base(self) -> Path:
        return self.data_root / "data" if self.data_layout == "legacy" else self.data_root

    @property
    def storage_dir(self) -> Path:
        return self.file_base / "storage"

    @property
    def config_file(self) -> Path:
        return self.data_root / "config" / "runtime.env"

    @property
    def state_file(self) -> Path:
        return self.data_root / "config" / "deployment-state.json"

    @property
    def local_url(self) -> str:
        host = "127.0.0.1" if self.listen_host == "0.0.0.0" else self.listen_host
        return f"http://{host}:{self.web_port}"

    def validate(self) -> None:
        if not self.install_root.is_absolute() or not self.data_root.is_absolute():
            raise ValueError("安装目录和持久化目录必须使用绝对路径。")
        if self.install_root.resolve().is_relative_to(self.data_root.resolve()):
            raise ValueError("数据存储目录不能等于或包含程序安装目录；建议使用安装目录下的 data 文件夹。")
        for root in (self.install_root, self.data_root):
            if any(c in str(root) for c in ('\n', '\r', '"', '%')):
                raise ValueError("目录不能含引号、百分号或换行。")
        # Never put persistent files inside a replaceable executable directory.
        if any(self.data_root.resolve().is_relative_to(self.install_root / part)
               for part in ("console", "_internal", "service", "releases")):
            raise ValueError("持久化目录不能位于程序发布目录内。")
        if not 1 <= self.web_port <= 65535 or not 1 <= self.db_port <= 65535:
            raise ValueError("端口必须在 1 至 65535 之间。")
        ip = ipaddress.IPv4Address(self.listen_host)
        if ip.is_multicast or ip.is_link_local or (not ip.is_unspecified and not ip.is_private):
            raise ValueError("本批仅支持本机或内网 IPv4 监听地址。")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", self.db_name):
            raise ValueError("数据库名只能使用字母、数字、下划线，不能以数字开头。")
        if self.transport_mode != "lan_http":
            raise ValueError("本批向导支持明确的内网 HTTP；HTTPS 请由后续部署流程配置。")
        if self.data_layout not in {"flat", "legacy"}:
            raise ValueError("无法识别数据存储布局，不能自动调整已有成果目录。")
        if self.pg_bin and not Path(self.pg_bin).is_absolute():
            raise ValueError("PostgreSQL 工具目录必须为绝对路径。")
        if self.public_base_url:
            parsed = urlparse(self.public_base_url)
            if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("外部访问地址应为不含账号或参数的 HTTPS 网站根地址。")
        if any('\n' in str(v) or '\r' in str(v) or '\x00' in str(v) for v in asdict(self).values()):
            raise ValueError("配置项不能含换行或空字符。")
        if len(self.db_password) < 12 or self.db_password.lower() in {"replace-with-local-password", "<strong-password>", "password123456", "changeme123456"}:
            raise ValueError("数据库密码必须为至少 12 位的非示例密码。")
        if not self.allowed_hosts or any(not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", h.strip().lower())
                or ".." in h or h.endswith(".") for h in self.allowed_hosts.split(",")):
            raise ValueError("允许的主机必须为精确主机名或 IPv4，不能使用通配符。")
        hosts = {h.strip().lower() for h in self.allowed_hosts.split(",")}
        if "127.0.0.1" not in hosts or (self.listen_host != "0.0.0.0" and self.listen_host not in hosts):
            raise ValueError("允许的主机必须包含 127.0.0.1 及实际监听地址。")

    def save(self) -> None:
        self.validate()
        values = {k.upper(): str(v) for k, v in asdict(self).items() if k not in {"install_root"}}
        values.update(APP_ENV="production", SESSION_COOKIE_SECURE="false", ENABLE_HSTS="false",
                      REGISTRATION_MODE="invite_only")
        # JSON strings are dotenv-compatible; escape backslashes and quotes in secrets/paths.
        atomic_write(self.config_file, "".join(f"{k}={json.dumps(v, ensure_ascii=False)}\n" for k, v in values.items()))
        atomic_write(self.install_root / "config" / "deployment.json",
                     json.dumps({"schema": 1, "config_file": str(self.config_file)}, ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, install_root: Path) -> "DeploymentConfig":
        pointer = json.loads((install_root / "config" / "deployment.json").read_text(encoding="utf-8"))
        path = Path(pointer["config_file"])
        if not path.is_absolute():
            raise ValueError("配置文件必须为绝对路径。")
        values = dotenv_values(path, interpolate=False)
        kwargs = {k: values[k.upper()] for k in cls.__dataclass_fields__ if k != "install_root" and k.upper() in values}
        kwargs["data_root"] = Path(kwargs["data_root"])
        kwargs["data_layout"] = values.get("DATA_LAYOUT", "legacy")
        for key in ("db_port", "web_port"):
            kwargs[key] = int(kwargs[key])
        result = cls(install_root=install_root.resolve(), **kwargs)
        result.validate()
        return result

    def ensure_directories(self) -> None:
        for name in ("config", "backups", "logs", "packages"):
            (self.data_root / name).mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        (self.install_root / "releases").mkdir(parents=True, exist_ok=True)


def safe_error(exc: Exception) -> str:
    if type(exc).__name__ == "DeploymentError" and type(exc).__module__ == "deployment.installer":
        return str(exc)
    if isinstance(exc, ModuleNotFoundError):
        return f"程序资源缺少模块：{exc.name}。请重新构建完整交付包。"
    if type(exc).__name__ == "OperationalError":
        return "数据库连接失败。请检查 PostgreSQL 17 是否运行、数据库是否已建立，以及地址、端口、用户名、密码和访问权限。"
    # Database/validation exceptions can embed a DSN or password. Show no raw input.
    if isinstance(exc, (ValueError, RuntimeError)) and type(exc).__module__ == "builtins":
        return str(exc)
    return f"操作失败（{type(exc).__name__}）。请核对配置、权限和数据库状态后重试。"
