from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener
from xml.etree import ElementTree as ET

from deployment.config import DeploymentConfig

SERVICE_ID = "YindaWebCenterService"
SERVICE_NAME = "Yinda Web Center"
LEGACY_TASK_NAME = "YindaWebCenter"
LEGACY_TASK_NOTICE = (
    "旧版 YindaWebCenter 计划任务存在时（包括已禁用），部署和启动均会被阻止。"
    "请先确认旧 Web 服务/进程已停止，必要时导出旧任务配置，再由维护人员移除该任务。"
    "本程序不会自动删除历史任务。"
)


def run(args, **kwargs):
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    encoding = kwargs.pop("encoding", "mbcs" if os.name == "nt" else "utf-8")
    timeout = kwargs.pop("timeout", 120)
    return subprocess.run([str(a) for a in args], capture_output=True, text=True,
                          encoding=encoding, errors="replace", timeout=timeout, **options, **kwargs)


def lan_ipv4() -> list[str]:
    # Enumerates active adapter unicast addresses; no outbound internet probe.
    if os.name != "nt":
        return []
    class SocketAddress(ctypes.Structure):
        _fields_ = [("address", ctypes.c_void_p), ("length", ctypes.c_int)]
    class Unicast(ctypes.Structure):
        pass
    Unicast._fields_ = [("header", ctypes.c_ulonglong), ("next", ctypes.POINTER(Unicast)), ("socket", SocketAddress)]
    class Adapter(ctypes.Structure):
        pass
    Adapter._fields_ = [("length", wintypes.ULONG), ("index", wintypes.ULONG), ("next", ctypes.POINTER(Adapter)),
        ("name", ctypes.c_char_p), ("unicast", ctypes.POINTER(Unicast)), ("anycast", ctypes.c_void_p),
        ("multicast", ctypes.c_void_p), ("dns", ctypes.c_void_p), ("suffix", ctypes.c_wchar_p),
        ("description", ctypes.c_wchar_p), ("friendly", ctypes.c_wchar_p), ("physical", ctypes.c_ubyte * 8),
        ("physical_length", wintypes.ULONG), ("flags", wintypes.ULONG), ("mtu", wintypes.ULONG),
        ("type", wintypes.ULONG), ("status", ctypes.c_int)]
    api = ctypes.WinDLL("iphlpapi").GetAdaptersAddresses
    api.argtypes = [wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG)]
    api.restype = wintypes.ULONG
    size = wintypes.ULONG(15360)
    for _ in range(3):
        buffer = ctypes.create_string_buffer(size.value)
        result = api(socket.AF_INET, 14, None, buffer, ctypes.byref(size))
        if result != 111:
            break
    if result != 0:
        raise RuntimeError("无法读取有效局域网网卡地址。")
    addresses = []
    adapter = ctypes.cast(buffer, ctypes.POINTER(Adapter))
    while adapter:
        item = adapter.contents
        unicast = item.unicast if item.status == 1 else None
        while unicast:
            address = unicast.contents.socket
            raw = ctypes.string_at(address.address, address.length)
            ip = ipaddress.IPv4Address(raw[4:8])
            if ip.is_private and not (ip.is_loopback or ip.is_link_local or ip.is_unspecified):
                addresses.append(str(ip))
            unicast = unicast.contents.next
        adapter = item.next
    return sorted(set(addresses))


def health(url: str, route: str = "/api/v1/health") -> bool:
    try:
        with build_opener(ProxyHandler({})).open(url + route, timeout=2) as response:
            return response.status == 200 and json.loads(response.read(4096)).get("status") == "ok"
    except (OSError, ValueError):
        return False


def port_available(host: str, port: int) -> bool:
    sock = socket.socket()
    try:
        if os.name == "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


class ServiceManager:
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.wrapper = config.install_root / "service" / "YindaWebService.exe"
        self.server = config.install_root / "service" / "YindaWebServer" / "YindaWebServer.exe"

    def server_command(self, *args) -> list[str]:
        if self.server.is_file():
            return [str(self.server), "--config", str(self.config.config_file), *args]
        if not getattr(sys, "frozen", False):
            return [sys.executable, str(Path(__file__).resolve().parents[1] / "server_entry.py"),
                    "--config", str(self.config.config_file), *args]
        raise RuntimeError("交付包缺少独立 Web Server 程序。")

    def server_action(self, action: str, *, payload: dict | None = None) -> str:
        stream = {"input": json.dumps(payload)} if payload is not None else {"stdin": subprocess.DEVNULL}
        result = run(self.server_command(action), **stream, encoding="utf-8", timeout=3700 if action == "--backup" else 120)
        if result.returncode:
            # server_entry emits only sanitized operational errors.
            raise RuntimeError(result.stdout.strip()[-1800:] or "服务程序检查失败，请查看日志与诊断。")
        return result.stdout.strip()

    def status(self) -> dict:
        if os.name != "nt":
            return {"state": "unsupported", "owned": False}
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SYSTEM\CurrentControlSet\Services\{SERVICE_ID}") as key:
                image = winreg.QueryValueEx(key, "ImagePath")[0].strip()
                account = winreg.QueryValueEx(key, "ObjectName")[0]
                startup = winreg.QueryValueEx(key, "Start")[0]
        except FileNotFoundError:
            return {"state": "absent", "owned": False}
        # Only our exact registered wrapper may be controlled. No PID killing.
        owned = os.path.normcase(image.strip('"')) == os.path.normcase(str(self.wrapper))
        result = run(["sc.exe", "query", SERVICE_ID])
        match = re.search(r":\s*(\d+)\s+(STOPPED|START_PENDING|STOP_PENDING|RUNNING|CONTINUE_PENDING|PAUSE_PENDING|PAUSED)\b", result.stdout)
        state = {1: "stopped", 2: "starting", 3: "stopping", 4: "running"}.get(int(match[1]), "unknown") if match else "unknown"
        return {"state": state, "owned": owned, "account": account, "automatic": startup == 2}

    def install_autostart(self) -> str:
        if not self.status()["owned"]:
            raise RuntimeError("请先安装此目录的正式 Windows 服务。")
        result = run(["sc.exe", "config", SERVICE_ID, "start=", "delayed-auto"])
        if result.returncode:
            raise RuntimeError("设置开机自启失败，请以管理员身份运行控制台。")
        return "已设置 Windows 服务开机延迟自动启动，无需登录或打开控制台。"

    def legacy_task(self) -> bool:
        result = run(["schtasks.exe", "/Query", "/TN", LEGACY_TASK_NAME, "/XML"])
        if result.returncode == 0:
            return True
        # Missing task is distinguished from denied/failed query through exit + text.
        if any(t in (result.stderr + result.stdout).lower() for t in ("cannot find", "找不到", "不存在")):
            return False
        raise RuntimeError("无法确认旧版 YindaWebCenter 计划任务状态；请用管理员权限检查。")

    def write_xml(self) -> None:
        cfg = self.config
        root = ET.Element("service")
        def add(key, value):
            ET.SubElement(root, key).text = str(value)
        add("id", SERVICE_ID)
        add("name", SERVICE_NAME)
        add("description", "引大调查 Web 中心正式后台服务")
        add("executable", self.server)
        add("startarguments", subprocess.list2cmdline(["--config", str(cfg.config_file), "--serve"]))
        add("stopexecutable", self.server)
        add("stoparguments", subprocess.list2cmdline(["--config", str(cfg.config_file), "--stop"]))
        add("workingdirectory", self.server.parent)
        add("startmode", "Automatic")
        add("delayedAutoStart", "true")
        add("stoptimeout", "45 sec")
        account = ET.SubElement(root, "serviceaccount")
        ET.SubElement(account, "domain").text = "NT AUTHORITY"
        ET.SubElement(account, "user").text = "LocalService"
        for delay in (10, 30, 60):
            ET.SubElement(root, "onfailure", action="restart", delay=f"{delay} sec")
        ET.SubElement(root, "onfailure", action="none")
        add("resetfailure", "1 hour")
        add("logpath", cfg.data_root / "logs")
        ET.SubElement(root, "log", mode="roll-by-size")
        from deployment.config import atomic_write
        atomic_write(self.wrapper.with_suffix(".xml"), ET.tostring(root, encoding="unicode"))

    def install(self) -> str:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise RuntimeError("安装 Windows 服务需要管理员权限，请右键以管理员身份运行控制台。")
        status = self.status()
        if status["state"] != "absent":
            if not status["owned"]:
                raise RuntimeError("同名服务不属于此安装目录，拒绝修改。")
            return "此安装目录的服务已安装。"
        if self.legacy_task():
            raise RuntimeError(LEGACY_TASK_NOTICE)
        if not self.wrapper.is_file() or not self.server.is_file():
            raise RuntimeError("缺少正式交付程序或 WinSW，请使用完整交付包。")
        self.server_action("--check")
        # Restrict credentials and persistent writes to administrator + SYSTEM + LocalService.
        # Program files only grant LocalService read/execute; never full-control on program root.
        for path, grants in ((self.config.data_root, ["*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F", "*S-1-5-19:(OI)(CI)M"]),):
            result = run(["icacls.exe", path, "/inheritance:r", "/grant:r", *grants, "/T", "/Q"])
            if result.returncode:
                raise RuntimeError("持久化目录权限设置失败，未安装服务。")
        result = run(["icacls.exe", self.config.install_root, "/grant", "*S-1-5-19:(OI)(CI)RX", "/T", "/Q"])
        if result.returncode:
            raise RuntimeError("程序读取权限设置失败，未安装服务。")
        self.write_xml()
        result = run([self.wrapper, "install"])
        if result.returncode:
            raise RuntimeError("Windows 服务安装失败，请查看 WinSW 日志。")
        return "Windows 服务已安装，低权限 LocalService，开机自动启动。"

    def control(self, action: str) -> str:
        if action not in {"start", "stop", "restart"}:
            raise ValueError("不支持的服务操作。")
        status = self.status()
        if not status["owned"]:
            raise RuntimeError("服务未安装或不属于此目录，拒绝操作。")
        if action == "start" and status["state"] == "running":
            return "服务已运行，不会重复启动。"
        if action in {"start", "restart"}:
            if self.legacy_task():
                raise RuntimeError(LEGACY_TASK_NOTICE)
            self.server_action("--check")
            if status["state"] == "stopped" and not port_available(self.config.listen_host, self.config.web_port):
                raise RuntimeError("Web 监听端口已被占用；不会停止占用端口的其他程序。")
        result = run([self.wrapper, action])
        if result.returncode:
            raise RuntimeError("服务操作失败。请检查管理员权限及运行日志。")
        expected = "stopped" if action == "stop" else "running"
        for _ in range(40):
            state = self.status()["state"]
            if state == expected and (expected == "stopped" or health(self.config.local_url)):
                return "服务已停止。" if expected == "stopped" else "服务已运行，本机 HTTP 健康检查通过。"
            time.sleep(0.5)
        raise RuntimeError("服务操作已提交，但尚未验证就绪。请刷新状态并查看日志。")


def event_name(config: DeploymentConfig, kind: str) -> str:
    token = hashlib.sha256(str(config.config_file.resolve()).lower().encode()).hexdigest()[:24]
    return rf"Global\{SERVICE_ID}-{kind}-{token}"
