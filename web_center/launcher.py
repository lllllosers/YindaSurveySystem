from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


WEB_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = WEB_ROOT / "backend"
FRONTEND_DIR = WEB_ROOT / "frontend"
PYTHON_EXE = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
NPM_EXE = "npm.cmd"
LOG_DIR = WEB_ROOT / ".runtime" / "logs"
API_URL = "http://127.0.0.1:8000"
WEB_URL = "http://127.0.0.1:8848"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class ServiceLauncher:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("引大调查数据中心 · 服务控制台")
        self.root.geometry("1020x700")
        self.root.minsize(900, 620)
        self.root.configure(bg="#081225")

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.starting = False
        self.closing = False
        self.status_vars = {
            "database": tk.StringVar(value="检测中"),
            "backend": tk.StringVar(value="检测中"),
            "frontend": tk.StringVar(value="检测中"),
        }
        self.dot_labels: dict[str, tk.Label] = {}

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._configure_style()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_events)
        self.root.after(300, lambda: self._refresh_status(reschedule=True))
        self.root.after(650, self.start_all)

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#081225")
        style.configure(
            "Primary.TButton",
            background="#3478f6",
            foreground="#ffffff",
            borderwidth=0,
            padding=(18, 10),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map("Primary.TButton", background=[("active", "#4b8aff")])
        style.configure(
            "Secondary.TButton",
            background="#172844",
            foreground="#c8d8ef",
            borderwidth=0,
            padding=(15, 9),
            font=("Microsoft YaHei UI", 9),
        )
        style.map("Secondary.TButton", background=[("active", "#203657")])
        style.configure(
            "Danger.TButton",
            background="#402138",
            foreground="#ffb7c5",
            borderwidth=0,
            padding=(15, 9),
            font=("Microsoft YaHei UI", 9),
        )
        style.map("Danger.TButton", background=[("active", "#593047")])

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg="#081225", padx=28, pady=22)
        header.pack(fill="x")
        tk.Label(
            header,
            text="引",
            width=3,
            bg="#3478f6",
            fg="white",
            font=("Microsoft YaHei UI", 17, "bold"),
        ).pack(side="left", padx=(0, 14))
        title_box = tk.Frame(header, bg="#081225")
        title_box.pack(side="left")
        tk.Label(
            title_box,
            text="引大调查数据中心",
            bg="#081225",
            fg="#f5f8ff",
            font=("Microsoft YaHei UI", 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="WEB CENTER · LOCAL SERVICE CONSOLE",
            bg="#081225",
            fg="#6f86a8",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(3, 0))
        tk.Label(
            header,
            text="V1.2.0  PREVIEW",
            bg="#112443",
            fg="#87b8ff",
            padx=12,
            pady=6,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right")

        body = tk.Frame(self.root, bg="#081225", padx=28)
        body.pack(fill="both", expand=True)
        status_panel = tk.Frame(body, bg="#101d33", padx=18, pady=16)
        status_panel.pack(fill="x")
        tk.Label(
            status_panel,
            text="服务状态",
            bg="#101d33",
            fg="#e8f0fd",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 13))
        cards = tk.Frame(status_panel, bg="#101d33")
        cards.pack(fill="x")
        services = [
            ("database", "PostgreSQL", "127.0.0.1 : 5432"),
            ("backend", "FastAPI 后端", "127.0.0.1 : 8000"),
            ("frontend", "Vue 前端", "127.0.0.1 : 8848"),
        ]
        for index, (key, title, detail) in enumerate(services):
            cards.grid_columnconfigure(index, weight=1)
            card = tk.Frame(cards, bg="#14243d", padx=16, pady=13)
            card.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0 if index == 0 else 6, 0 if index == 2 else 6),
            )
            top = tk.Frame(card, bg="#14243d")
            top.pack(fill="x")
            dot = tk.Label(top, text="●", bg="#14243d", fg="#e5a93a", font=("Segoe UI", 12))
            dot.pack(side="left", padx=(0, 8))
            self.dot_labels[key] = dot
            tk.Label(top, text=title, bg="#14243d", fg="#eaf2ff", font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
            tk.Label(top, textvariable=self.status_vars[key], bg="#14243d", fg="#88a0c2", font=("Microsoft YaHei UI", 9)).pack(side="right")
            tk.Label(card, text=detail, bg="#14243d", fg="#7187a7", font=("Consolas", 9)).pack(anchor="w", pady=(9, 0))

        actions = tk.Frame(body, bg="#081225", pady=16)
        actions.pack(fill="x")
        self.start_button = ttk.Button(actions, text="启动全部服务", style="Primary.TButton", command=self.start_all)
        self.start_button.pack(side="left")
        ttk.Button(actions, text="停止本次服务", style="Danger.TButton", command=self.stop_all).pack(side="left", padx=(10, 0))
        ttk.Button(actions, text="打开 Web 页面", style="Secondary.TButton", command=lambda: webbrowser.open(WEB_URL)).pack(side="left", padx=(10, 0))
        ttk.Button(actions, text="打开 API 文档", style="Secondary.TButton", command=lambda: webbrowser.open(f"{API_URL}/docs")).pack(side="left", padx=(10, 0))
        ttk.Button(actions, text="立即检测", style="Secondary.TButton", command=self._refresh_status).pack(side="right")

        log_panel = tk.Frame(body, bg="#101d33", padx=18, pady=15)
        log_panel.pack(fill="both", expand=True, pady=(0, 20))
        log_header = tk.Frame(log_panel, bg="#101d33")
        log_header.pack(fill="x", pady=(0, 10))
        tk.Label(log_header, text="运行日志", bg="#101d33", fg="#e8f0fd", font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        tk.Label(log_header, text="启动器会持续监测服务，本窗口可最小化", bg="#101d33", fg="#647b9e", font=("Microsoft YaHei UI", 8)).pack(side="right")
        self.log_text = tk.Text(
            log_panel,
            bg="#091426",
            fg="#9fb4d2",
            insertbackground="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=13,
            pady=11,
            font=("Consolas", 9),
            wrap="word",
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("time", foreground="#516b91")
        self.log_text.tag_configure("ok", foreground="#5ee2a0")
        self.log_text.tag_configure("error", foreground="#ff8398")
        self.log_text.tag_configure("info", foreground="#9fb4d2")
        self._write_log("服务控制台已启动，正在检查本地环境。")

    def _write_log(self, message: str, level: str = "info") -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] ", "time")
        self.log_text.insert("end", f"{message}\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _emit(self, message: str, level: str = "info") -> None:
        self.events.put((level, message))

    def _drain_events(self) -> None:
        while True:
            try:
                level, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if level == "__status__":
                values, reschedule = payload
                for key, value in values.items():
                    self._set_status(key, value)
                if reschedule and not self.closing:
                    self.root.after(2500, lambda: self._refresh_status(reschedule=True))
            elif level == "__start_done__":
                self.start_button.configure(state="normal", text="启动全部服务")
                self._refresh_status()
            elif level == "__open_web__":
                webbrowser.open(str(payload))
            else:
                self._write_log(str(payload), level)
        if not self.closing:
            self.root.after(120, self._drain_events)

    @staticmethod
    def _http_ok(url: str) -> bool:
        try:
            with urlopen(url, timeout=1.2) as response:
                if not 200 <= response.status < 400:
                    return False
                if url.endswith("/health"):
                    return json.loads(response.read().decode("utf-8")).get("status") == "ok"
                return True
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            return False

    @staticmethod
    def _port_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.8):
                return True
        except OSError:
            return False

    def _set_status(self, key: str, online: bool) -> None:
        self.status_vars[key].set("运行正常" if online else "未运行")
        self.dot_labels[key].configure(fg="#39d98a" if online else "#ff617d")

    def _refresh_status(self, reschedule: bool = False) -> None:
        def check() -> None:
            values = {
                "database": self._port_open(5432),
                "backend": self._http_ok(f"{API_URL}/api/v1/health"),
                "frontend": self._http_ok(WEB_URL),
            }
            self.events.put(("__status__", (values, reschedule)))

        threading.Thread(target=check, daemon=True).start()

    def _check_environment(self) -> list[str]:
        missing: list[str] = []
        if not PYTHON_EXE.exists():
            missing.append("后端虚拟环境不存在：web_center/backend/.venv")
        if not (BACKEND_DIR / ".env").exists():
            missing.append("后端配置不存在：web_center/backend/.env")
        if not (FRONTEND_DIR / "node_modules").exists():
            missing.append("前端依赖不存在：请先在 frontend 目录执行 npm install")
        try:
            subprocess.run([NPM_EXE, "--version"], capture_output=True, check=True, creationflags=CREATE_NO_WINDOW)
        except (OSError, subprocess.CalledProcessError):
            missing.append("未找到 Node.js / npm")
        return missing

    def start_all(self) -> None:
        if self.starting:
            return
        missing = self._check_environment()
        if missing:
            message = "\n".join(missing)
            self._write_log(message, "error")
            messagebox.showerror("无法启动", message)
            return
        self.starting = True
        self.start_button.configure(state="disabled", text="正在启动…")
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self) -> None:
        try:
            if not self._port_open(5432):
                self._emit("PostgreSQL 端口未响应，请先启动数据库服务。", "error")
                return
            if not self._http_ok(f"{API_URL}/api/v1/health"):
                self._emit("正在检查并升级数据库结构…")
                migration = subprocess.run(
                    [str(PYTHON_EXE), "-m", "alembic", "upgrade", "head"],
                    cwd=BACKEND_DIR,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW,
                )
                if migration.returncode != 0:
                    self._emit("数据库迁移失败：" + self._last_output(migration.stdout, migration.stderr), "error")
                    return
                self._emit("数据库结构已就绪。", "ok")
                self._start_process(
                    "backend",
                    [str(PYTHON_EXE), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                    BACKEND_DIR,
                )
            else:
                self._emit("后端服务已在运行，本控制台不会重复启动。", "ok")
            if not self._http_ok(WEB_URL):
                self._start_process("frontend", [NPM_EXE, "run", "dev"], FRONTEND_DIR)
            else:
                self._emit("前端服务已在运行，本控制台不会重复启动。", "ok")

            deadline = time.time() + 30
            while time.time() < deadline:
                if self._http_ok(f"{API_URL}/api/v1/health") and self._http_ok(WEB_URL):
                    self._emit("前后端服务均已就绪，可以打开 Web 页面验收。", "ok")
                    self.events.put(("__open_web__", WEB_URL))
                    return
                time.sleep(0.6)
            self._emit("启动等待超时，请查看下方日志定位问题。", "error")
        except Exception as exc:
            self._emit(f"启动失败：{exc}", "error")
        finally:
            self.starting = False
            self.events.put(("__start_done__", ""))

    @staticmethod
    def _last_output(stdout: str, stderr: str) -> str:
        lines = [line.strip() for line in (stdout + "\n" + stderr).splitlines() if line.strip()]
        return lines[-1] if lines else "无详细信息"

    def _start_process(self, name: str, command: list[str], cwd: Path) -> None:
        env = os.environ.copy()
        env.update({"PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", "NO_COLOR": "1", "FORCE_COLOR": "0"})
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        self.processes[name] = process
        label = "后端" if name == "backend" else "前端"
        self._emit(f"已启动{label}服务（PID {process.pid}）。", "ok")
        threading.Thread(target=self._capture_output, args=(name, process), daemon=True).start()

    def _capture_output(self, name: str, process: subprocess.Popen[str]) -> None:
        log_path = LOG_DIR / f"{name}.log"
        with log_path.open("a", encoding="utf-8") as log_file:
            if process.stdout:
                for raw_line in process.stdout:
                    line = ANSI_ESCAPE.sub("", raw_line.rstrip())
                    if not line:
                        continue
                    log_file.write(line + "\n")
                    log_file.flush()
                    self._emit(f"[{name}] {line}")
        code = process.wait()
        self.processes.pop(name, None)
        if not self.closing:
            self._emit(f"{name} 服务已退出（代码 {code}）。", "error" if code else "info")

    def stop_all(self, silent: bool = False) -> None:
        owned = list(self.processes.items())
        if not owned:
            if not silent:
                self._write_log("当前没有由本控制台启动的服务。")
            return
        for name, process in owned:
            if process.poll() is not None:
                continue
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        creationflags=CREATE_NO_WINDOW,
                    )
                else:
                    process.terminate()
                if not silent:
                    self._write_log(f"已停止 {name} 服务。")
            except OSError as exc:
                if not silent:
                    self._write_log(f"停止 {name} 失败：{exc}", "error")
        self.processes.clear()
        self.root.after(500, self._refresh_status)

    def _on_close(self) -> None:
        if self.processes and not messagebox.askyesno(
            "退出控制台",
            "关闭控制台会同时停止本次启动的前后端服务。确认退出吗？",
        ):
            return
        self.closing = True
        self.stop_all(silent=True)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ServiceLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
