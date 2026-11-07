"""Chinese Server Console V1; all database, filesystem and SCM work runs off the UI thread."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
from pathlib import Path
import sys
import webbrowser

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox, QStackedWidget,
    QTextEdit, QVBoxLayout, QWidget, QWizard, QWizardPage, QFileDialog)

WEB = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB / "backend"))

from deployment.config import DeploymentConfig, safe_error
from deployment.service import ServiceManager, health, lan_ipv4, run


STYLE = """
QWidget { background:#101c2c; color:#e7eef8; font-family:'Microsoft YaHei UI'; font-size:15px; }
QMainWindow { background:#101c2c; }
QLabel#title { font-size:28px; font-weight:600; } QLabel#muted { color:#9bacc0; }
QListWidget { background:#16263a; border:0; padding:10px; min-width:165px; }
QListWidget::item { padding:14px 12px; } QListWidget::item:selected { background:#254d72; border-radius:6px; }
QPushButton { background:#25415e; border:1px solid #355572; border-radius:7px; padding:9px 18px; }
QPushButton:hover { background:#305675; } QPushButton:disabled { color:#708198; background:#1b2c40; }
QPushButton#primary { background:#176c91; border-color:#238bb5; }
QLineEdit,QComboBox,QSpinBox,QTextEdit { background:#192b40; border:1px solid #35516f; border-radius:5px; padding:8px; selection-background-color:#287da0; }
QLabel#card { background:#192d43; border:1px solid #304c68; border-radius:10px; padding:22px; font-size:20px; }
QWizard,QWizardPage { background:#101c2c; } QToolTip { background:#253e59; color:white; }
"""


class Bridge(QObject):
    done = Signal(object)
    error = Signal(str)


class SetupWizard(QWizard):
    def __init__(self, home: Path, current: DeploymentConfig | None, addresses: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("引大 Server Console · 首次部署")
        self.resize(760, 660)
        self.setWizardStyle(QWizard.ModernStyle)
        self.setButtonText(QWizard.NextButton, "下一步")
        self.setButtonText(QWizard.BackButton, "上一步")
        self.setButtonText(QWizard.FinishButton, "部署并启动")
        self.setButtonText(QWizard.CancelButton, "取消")
        self.inputs = {}
        def page(title, subtitle):
            p = QWizardPage()
            p.setTitle(title)
            p.setSubTitle(subtitle)
            form = QFormLayout(p)
            form.setVerticalSpacing(15)
            self.addPage(p)
            return form
        def text(form, key, title, default, secret=False, directory=False):
            edit = QLineEdit(str(default))
            if secret:
                edit.setEchoMode(QLineEdit.Password)
            self.inputs[key] = edit
            if directory:
                row = QHBoxLayout()
                row.addWidget(edit)
                button = QPushButton("选择…")
                button.clicked.connect(lambda: self.choose_directory(edit))
                row.addWidget(button)
                form.addRow(title, row)
            else:
                form.addRow(title, edit)
        form = page("1 · 安装与数据目录", "Windows 11 x64 · 使用已安装的 PostgreSQL 17；服务安装需要管理员权限。")
        text(form, "install_root", "程序安装目录", current.install_root if current else home, directory=True)
        text(form, "data_root", "持久化数据目录", current.data_root if current else home / "persistent", directory=True)
        note = QLabel("请将完整交付包解压到固定目录。配置、成果、备份与日志存放在持久化目录。\n本向导不安装 PostgreSQL，不创建数据库；请使用专用、预先创建的空数据库。")
        note.setWordWrap(True)
        form.addRow(note)
        form = page("2 · 数据库连接", "数据库端口无需对局域网开放；推荐 127.0.0.1。")
        for key, label, default in (("db_host", "数据库地址", "127.0.0.1"), ("db_port", "数据库端口", 5432),
                ("db_name", "数据库名称", "yinda_web_center"), ("db_user", "数据库用户", "yinda_app"), ("db_password", "数据库密码", "")):
            text(form, key, label, getattr(current, key) if current else default, key == "db_password")
        button = QPushButton("打开 PostgreSQL 官方下载页")
        button.clicked.connect(lambda: webbrowser.open("https://www.postgresql.org/download/windows/"))
        form.addRow(button)
        form = page("3 · 办公室网络", "选择内网 HTTP 正式运行：传输不加密，仅供受信办公室网络，禁止公网暴露。")
        text(form, "listen_host", "监听 IPv4", current.listen_host if current else "0.0.0.0")
        text(form, "web_port", "Web 端口", current.web_port if current else 8000)
        text(form, "allowed_hosts", "允许的访问主机", current.allowed_hosts if current else ",".join(["127.0.0.1", "localhost", *addresses]))
        note = QLabel("允许的主机使用逗号分隔的实际 IPv4 或主机名。\n监听 0.0.0.0 表示所有本机网卡；本机诊断使用 127.0.0.1。\n其他电脑访问仍须现场验证；本程序不更改路由器或防火墙。")
        note.setWordWrap(True)
        form.addRow(note)
        form = page("4 · 初始化与服务", "新部署仅接受空数据库；接续只接受本控制台已登记的数据目录。失败后保留状态供重试。")
        self.mode = QComboBox()
        self.mode.addItem("初始化专用空数据库", "new")
        self.mode.addItem("安全接续 / 重试本控制台已有部署", "continue")
        if current:
            self.mode.setCurrentIndex(1)
        form.addRow("部署方式", self.mode)
        text(form, "username", "首位管理员账号", "admin")
        text(form, "admin_password", "管理员密码（至少 12 位）", "", True)
        note = QLabel("已有管理员不会重置。点击部署后将检查数据库、执行现有 Alembic 迁移、安装服务并启动。\n旧版 YindaWebCenter 计划任务须先由维护人员停用。\n安装失败可修正配置后使用“安全接续”重试。")
        note.setWordWrap(True)
        form.addRow(note)

    def choose_directory(self, edit):
        selected = QFileDialog.getExistingDirectory(self, "选择目录", edit.text())
        if selected:
            edit.setText(selected)

    def accept(self):
        try:
            values = {k: edit.text().strip() if k not in {"db_password", "admin_password"} else edit.text() for k, edit in self.inputs.items()}
            self.username = values.pop("username")
            self.password = values.pop("admin_password")
            for key in ("install_root", "data_root"):
                values[key] = Path(values[key])
            for key in ("db_port", "web_port"):
                values[key] = int(values[key])
            self.config = DeploymentConfig(**values)
            self.config.validate()
            if not self.username or not 12 <= len(self.password) <= 128:
                raise ValueError("请填写管理员账号和 12 至 128 位密码。")
        except Exception as exc:
            QMessageBox.warning(self, "请修正配置", safe_error(exc))
            return
        super().accept()


class Console(QMainWindow):
    def __init__(self, home: Path):
        super().__init__()
        self.home = home.resolve()
        self.config = None
        self.addresses = []
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.bridge = Bridge()
        self.bridge.done.connect(self.finished)
        self.bridge.error.connect(self.failed)
        self.busy = False
        self.setWindowTitle("引大调查 · Server Console V1")
        self.resize(1190, 780)
        self.setMinimumSize(1020, 700)
        self.buttons = []
        body = QWidget()
        self.setCentralWidget(body)
        outer = QHBoxLayout(body)
        outer.setContentsMargins(0, 0, 24, 20)
        self.nav = QListWidget()
        self.stack = QStackedWidget()
        outer.addWidget(self.nav)
        outer.addWidget(self.stack, 1)
        for title in ("概览", "运行管理", "网络访问", "数据与备份 · 后续", "系统升级 · 后续", "日志与诊断", "设置与关于"):
            self.nav.addItem(title)
        for index in (3, 4):
            self.nav.item(index).setFlags(Qt.NoItemFlags)
        for index in range(7):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(25, 25, 0, 0)
            layout.setSpacing(18)
            title = QLabel(self.nav.item(index).text())
            title.setObjectName("title")
            layout.addWidget(title)
            self.stack.addWidget(widget)
        def layout(index):
            return self.stack.widget(index).layout()
        self.summary = QLabel("正在读取配置…")
        self.summary.setObjectName("card")
        self.summary.setWordWrap(True)
        layout(0).addWidget(self.summary)
        self.details = QLabel()
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details.setWordWrap(True)
        layout(0).addWidget(self.details)
        self.add_button(layout(0), "首次部署 / 修复配置", self.setup, True)
        layout(0).addStretch()
        for title, action in (("安装 Windows 服务", "install"), ("启动服务", "start"), ("停止服务", "stop"), ("重启服务", "restart"), ("刷新状态", "refresh")):
            self.add_button(layout(1), title, lambda checked=False, a=action: self.action(a))
        layout(1).addStretch()
        self.network = QTextEdit()
        self.network.setReadOnly(True)
        layout(2).addWidget(self.network)
        self.add_button(layout(2), "复制局域网候选地址", self.copy_urls)
        self.add_button(layout(2), "打开本机管理页面", self.open_web)
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        layout(5).addWidget(self.logs)
        self.add_button(layout(5), "读取最近服务日志", self.read_logs)
        self.add_button(layout(5), "数据库与部署检查", lambda: self.action("check"))
        self.settings_text = QLabel("Server Console V1 · 第一批\nWinSW / LocalService / PostgreSQL 17\n\n关闭控制台不会停止服务。\n运行配置请通过部署向导修改；修改前须停止服务。\n\n数据备份、版本升级和管理员恢复管理在下一批实现。")
        self.settings_text.setWordWrap(True)
        layout(6).addWidget(self.settings_text)
        self.add_button(layout(6), "运行配置 / 部署向导", self.setup)
        layout(6).addStretch()
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.statusBar().showMessage("正在检查…")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(15000)
        self.refresh()

    def add_button(self, layout, title, handler, primary=False):
        button = QPushButton(title)
        if primary:
            button.setObjectName("primary")
        button.clicked.connect(handler)
        layout.addWidget(button)
        self.buttons.append(button)

    def submit(self, function):
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.setEnabled(False)
        self.statusBar().showMessage("正在处理，请稍候…")
        def worker():
            try:
                self.bridge.done.emit(function())
            except Exception as exc:
                self.bridge.error.emit(safe_error(exc))
        self.pool.submit(worker)

    def refresh(self):
        def inspect():
            addresses = lan_ipv4()
            if not (self.home / "config" / "deployment.json").is_file():
                return {"addresses": addresses, "config": None}
            config = DeploymentConfig.load(self.home)
            status = ServiceManager(config).status()
            owned_running = status["owned"] and status["state"] == "running"
            return {"addresses": addresses, "config": config, "status": status,
                "http": owned_running and health(config.local_url),
                "database": owned_running and health(config.local_url, "/api/v1/health/database")}
        self.submit(inspect)

    def finished(self, result):
        self.busy = False
        for button in self.buttons:
            button.setEnabled(True)
        self.statusBar().showMessage("检查完成 · " + datetime.now().strftime("%H:%M:%S"))
        if isinstance(result, dict):
            self.addresses = result["addresses"]
            self.config = result["config"]
            if not self.config:
                self.summary.setText("尚未部署\n请运行首次部署向导")
                self.details.setText(f"交付程序目录：{self.home}\nPostgreSQL 17 须独立安装。")
                self.network.setPlainText("尚未配置 Web。检测到的内网 IPv4：\n" + "\n".join(self.addresses))
                return
            labels = {"absent": "未安装", "running": "运行中", "stopped": "已停止", "starting": "启动中", "stopping": "停止中", "unknown": "状态未知"}
            self.summary.setText("Windows 服务：" + labels.get(result["status"]["state"], "未知") +
                ("" if result["status"]["owned"] else "（未确认归属）") +
                "\n本机 Web：" + ("验证通过" if result["http"] else "未验证通过") +
                "\n数据库：" + ("连接正常" if result["database"] else "未验证连接"))
            self.details.setText(f"持久化目录：{self.config.data_root}\n配置：{self.config.config_file}\n服务账户：{result['status'].get('account', '—')}\nAPP_ENV=production · 明确内网 HTTP 模式")
            self.network.setPlainText("本机诊断：" + self.config.local_url + "\n\n局域网候选地址（需在其他电脑实测）：\n" +
                "\n".join(self.urls()) + "\n\n本机健康检查不代表其他电脑能够访问。\n无法访问时检查 Windows 防火墙入站规则及办公室网络隔离。\n仅允许所需 Web TCP 端口；不开放 PostgreSQL 端口。\n内网 HTTP 的密码和会话传输不加密，请勿映射到公网。")
        else:
            self.logs.setPlainText(str(result))
            self.statusBar().showMessage(str(result).splitlines()[-1] if result else "操作完成")

    def failed(self, message):
        self.busy = False
        for button in self.buttons:
            button.setEnabled(True)
        self.logs.setPlainText(message)
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "操作未完成", message)

    def urls(self):
        if not self.config or self.config.listen_host == "127.0.0.1":
            return []
        hosts = {h.strip() for h in self.config.allowed_hosts.split(",")}
        return [f"http://{ip}:{self.config.web_port}" for ip in self.addresses
                if ip in hosts and self.config.listen_host in {"0.0.0.0", ip}]

    def copy_urls(self):
        QApplication.clipboard().setText("\n".join(self.urls()))

    def open_web(self):
        if self.config:
            webbrowser.open(self.config.local_url)

    def action(self, action):
        if action == "refresh":
            self.refresh()
            return
        if not self.config:
            QMessageBox.information(self, "尚未部署", "请先完成部署向导。")
            return
        manager = ServiceManager(self.config)
        self.submit(lambda: manager.install() if action == "install" else manager.server_action("--check") if action == "check" else manager.control(action))

    def setup(self):
        wizard = SetupWizard(self.home, self.config, self.addresses, self)
        if wizard.exec() == QWizard.Accepted:
            from deployment.installer import deploy
            source = self.home
            config = wizard.config
            payload = (wizard.mode.currentData(), wizard.username, wizard.password)
            wizard.password = ""
            wizard.inputs["admin_password"].clear()
            def operation():
                message = deploy(source, config, *payload)
                self.home = config.install_root
                return message + "\n请刷新状态并打开管理页面。"
            self.submit(operation)

    def read_logs(self):
        if not self.config:
            return
        root = self.config.data_root / "logs"
        def read():
            chunks = []
            for path in sorted(root.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 32768))
                    chunks.append(path.name + "\n" + stream.read().decode("utf-8", errors="replace"))
            return "\n\n".join(chunks) or "暂无服务日志。"
        self.submit(read)

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, "操作进行中", "请等待当前操作完成后关闭控制台。")
            event.ignore()
            return
        self.timer.stop()
        self.pool.shutdown(wait=False)
        event.accept()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    home = args.home or (Path(sys.executable).resolve().parents[1] if getattr(sys, "frozen", False) else WEB)
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = Console(home)
    window.show()
    if args.smoke_test:
        QTimer.singleShot(1500, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
