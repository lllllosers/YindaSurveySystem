"""The only formal Yinda Server Console GUI entry point."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QListWidget, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
    QPushButton, QStackedWidget, QSystemTrayIcon, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from server_console_core import CONSOLE_VERSION, ServerManager, safe_error
from server_setup import SetupWizard, DeploymentProgress
from branding import PRODUCT_NAME, asset

STYLE = """
QWidget { color:#243b59; font-family:'Microsoft YaHei UI'; font-size:14px; }
QMainWindow, QDialog, QWizard, QWizardPage, QWidget#workspace { background:#f1f5fb; }
QFrame#sidebar { background:#12335c; border:0; }
QFrame#sidebar QLabel { color:#e4efff; background:transparent; }
QLabel#brand { font-size:24px; font-weight:700; } QLabel#brandSub { color:#a5c3ed; font-size:14px; }
QListWidget { background:transparent; border:0; outline:0; color:#b5cceb; }
QListWidget::item { padding:15px 18px; margin:3px 0; border-radius:8px; }
QListWidget::item:selected { background:#244f82; color:white; font-weight:600; }
QLabel#title { font-size:26px; font-weight:700; color:#153b6d; }
QLabel#hint { color:#647b98; background:transparent; } QLabel#eyebrow { color:#6683a6; font-size:12px; }
QLabel#version { color:#245a9c; background:#e1ecfc; padding:8px 14px; border-radius:15px; }
QFrame#panel, QFrame#statusCard { background:white; border:1px solid #d8e3f2; border-radius:13px; }
QFrame#statusCard QLabel, QFrame#panel QLabel { background:transparent; }
QLabel#cardTitle { color:#647b98; font-size:13px; } QLabel#cardValue { color:#205a9f; font-size:23px; font-weight:700; }
QLabel#section { font-size:16px; font-weight:600; } QLabel#address { font-size:23px; font-weight:600; color:#205a9f; }
QLabel#banner { color:#315f98; background:#e6eefb; border:1px solid #d2e0f6; border-radius:8px; padding:13px; }
QPushButton { background:white; border:1px solid #cbd9ed; border-radius:7px; padding:10px 16px; color:#244f82; }
QPushButton:hover { background:#e9f0fc; border-color:#81a9e0; } QPushButton:disabled { background:#edf1f8; color:#9baabd; border-color:#e0e7f0; }
QPushButton#primary { background:#2369c5; border-color:#2369c5; color:white; }
QPushButton#primary:hover { background:#1b55a2; } QPushButton#danger { color:#ae594d; }
QPushButton#primary:disabled, QPushButton#danger:disabled { background:#edf1f8; color:#9baabd; border-color:#e0e7f0; }
QPlainTextEdit, QTextEdit, QTreeWidget { background:white; border:1px solid #d5e1f1; border-radius:8px; padding:12px; }
QPlainTextEdit { font-family:'Cascadia Mono','Microsoft YaHei UI'; font-size:13px; }
QHeaderView::section { background:#e9eff9; padding:9px; border:0; }
QLineEdit,QComboBox { background:white; border:1px solid #c8d8ee; border-radius:5px; padding:7px; color:#244f82; }
QGroupBox { border:1px solid #d1ddf0; border-radius:7px; margin-top:13px; padding-top:16px; }
QGroupBox::title { subcontrol-origin:margin; left:10px; } QStatusBar { background:#e4ecf8; color:#647fa2; }
QProgressBar { border:0; background:#dce7f7; border-radius:5px; height:9px; } QProgressBar::chunk { background:#2876d4; border-radius:5px; }
QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; }
"""


def icon():
    return QIcon(str(asset("YindaWebCenter.ico")))


class Bridge(QObject):
    done = Signal(str, object)
    error = Signal(str, str)
    progress = Signal(str, str, str)


class StatusCard(QFrame):
    def __init__(self, title, detail):
        super().__init__()
        self.setObjectName("statusCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        caption = QLabel(title)
        caption.setObjectName("cardTitle")
        self.value = QLabel("正在检查")
        self.value.setObjectName("cardValue")
        self.detail = QLabel(detail)
        self.detail.setWordWrap(True)
        self.detail.setObjectName("hint")
        layout.addWidget(caption)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set_state(self, value, detail, good=False):
        self.value.setText(value)
        self.value.setStyleSheet("color:#256a50;" if good else "color:#a27638;")
        self.detail.setText(detail)


class ServerConsole(QMainWindow):
    def __init__(self, manager=None):
        super().__init__()
        self.manager = manager or ServerManager()
        self.current = None
        self.addresses = []
        self.last_status = {}
        self.busy = False
        self.active_task = None
        self.deploying = False
        self.wizard_open = False
        self.deployment_dialog = None
        self.exiting = False
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.bridge = Bridge()
        self.bridge.done.connect(self.finished)
        self.bridge.error.connect(self.failed)
        self.bridge.progress.connect(self.show_progress)
        self.buttons = []
        self.setWindowTitle(PRODUCT_NAME + " · Web Center")
        self.setWindowIcon(icon())
        self.resize(1280, 850)
        self.setMinimumSize(1060, 680)
        self._build()
        self._tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(15000)
        self.refresh()

    def button(self, text, action, kind=""):
        button = QPushButton(text)
        button.setObjectName(kind)
        button.clicked.connect(action)
        self.buttons.append(button)
        return button

    def _build(self):
        workspace = QWidget()
        workspace.setObjectName("workspace")
        self.setCentralWidget(workspace)
        outer = QHBoxLayout(workspace)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(214)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(20, 30, 20, 24)
        mark = QLabel()
        mark.setPixmap(QPixmap(str(asset("BrandMark.png"))).scaled(76, 76, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        side_layout.addWidget(mark)
        brand = QLabel("引大调查")
        brand.setObjectName("brand")
        side_layout.addWidget(brand)
        sub = QLabel("数据采集系统\nWEB CENTER")
        sub.setObjectName("brandSub")
        side_layout.addWidget(sub)
        side_layout.addSpacing(32)
        self.nav = QListWidget()
        self.nav.addItems(["中心总览", "运行与诊断", "网络访问", "数据与备份", "安装与设置"])
        side_layout.addWidget(self.nav, 1)
        side_layout.addWidget(QLabel("办公室数据中心\nWindows 后台服务"))
        outer.addWidget(side)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.pages = []
        for title, subtitle in (("Web Center 总览", "引大调查数据采集系统 · 运行状态与数据保护"), ("运行与诊断", "检查环境、管理后台服务、查看运行日志"),
                ("网络访问", "区分本机检查和办公室其他电脑的访问"), ("数据与备份", "数据库与成果文件一起保存，完成后记录备份结果"),
                ("安装与设置", "首次安装、运行配置与后台服务设置")):
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(30, 27, 30, 22)
            layout.setSpacing(17)
            header = QHBoxLayout()
            headings = QVBoxLayout()
            caption = QLabel(title)
            caption.setObjectName("title")
            hint = QLabel(subtitle)
            hint.setObjectName("hint")
            headings.addWidget(caption)
            headings.addWidget(hint)
            header.addLayout(headings)
            header.addStretch()
            version = QLabel(CONSOLE_VERSION)
            version.setObjectName("version")
            header.addWidget(version)
            layout.addLayout(header)
            self.stack.addWidget(page)
            self.pages.append(layout)
        overview = self.pages[0]
        self.banner = QLabel("正在检查服务状态…")
        self.banner.setWordWrap(True)
        self.banner.setObjectName("banner")
        overview.addWidget(self.banner)
        self.setup_button = self.button("首次安装 / 运行配置", self.setup, "primary")
        overview.addWidget(self.setup_button)
        cards = QHBoxLayout()
        self.web_card = StatusCard("WEB 后台服务", "无需保持控制台打开")
        self.database_card = StatusCard("POSTGRESQL 17", "独立于 Web 检查数据库连接")
        self.backup_card = StatusCard("最近完整备份", "数据库 + 调查成果文件")
        for card in (self.web_card, self.database_card, self.backup_card):
            cards.addWidget(card, 1)
        overview.addLayout(cards)
        access = QFrame()
        access.setObjectName("panel")
        access_layout = QVBoxLayout(access)
        access_layout.setContentsMargins(20, 16, 20, 16)
        label = QLabel("办公室访问地址")
        label.setObjectName("cardTitle")
        access_layout.addWidget(label)
        self.url_label = QLabel("完成安装后显示访问地址")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.url_label.setObjectName("address")
        access_layout.addWidget(self.url_label)
        self.url_hint = QLabel("局域网地址为候选地址，需由办公室另一台电脑验证。")
        self.url_hint.setObjectName("hint")
        access_layout.addWidget(self.url_hint)
        self.copy_button = self.button("复制访问地址", self.copy_url)
        access_layout.addWidget(self.copy_button)
        overview.addWidget(access)
        actions = QGridLayout()
        self.operation_buttons = {}
        for index, (label, action, kind) in enumerate((("启动服务", "start", "primary"), ("停止服务", "stop", "danger"), ("重启服务", "restart", ""),
                ("打开管理端", "open", ""), ("检查运行环境", "preflight", ""), ("立即备份", "backup", ""))):
            button = self.button(label, lambda checked=False, name=action: self.action(name), kind)
            self.operation_buttons[action] = button
            actions.addWidget(button, index // 3, index % 3)
        overview.addLayout(actions)
        overview.addStretch()
        self.overview_detail = QLabel("安装完成后，可在这里查看数据库版本、磁盘空间和环境检查结果。")
        self.overview_detail.setObjectName("hint")
        self.overview_detail.setWordWrap(True)
        overview.addWidget(self.overview_detail)
        diagnostic_layout = self.pages[1]
        toolbar = QHBoxLayout()
        for label, name in (("检查运行环境", "preflight"), ("安装后台服务", "install"), ("设置开机自启", "autostart")):
            toolbar.addWidget(self.button(label, lambda checked=False, a=name: self.action(a)))
        diagnostic_layout.addLayout(toolbar)
        self.checks = QTreeWidget()
        self.checks.setHeaderLabels(["检查项目", "结果", "说明"])
        self.checks.setColumnWidth(0, 135)
        self.checks.setColumnWidth(1, 70)
        self.checks.setMinimumHeight(150)
        diagnostic_layout.addWidget(self.checks, 1)
        log_toolbar = QHBoxLayout()
        log_label = QLabel("运行日志")
        log_label.setObjectName("section")
        log_toolbar.addWidget(log_label)
        self.log_choice = QComboBox()
        for label, value in (("Web 服务", "server"), ("控制台操作", "operations"), ("环境检查", "preflight"), ("备份", "backup")):
            self.log_choice.addItem(label, value)
        log_toolbar.addWidget(self.log_choice)
        log_toolbar.addWidget(self.button("读取日志", self.read_logs))
        diagnostic_layout.addLayout(log_toolbar)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("每份日志只显示最近 100 行。")
        diagnostic_layout.addWidget(self.log_view, 1)
        self.network = QPlainTextEdit()
        self.network.setReadOnly(True)
        self.pages[2].addWidget(self.network)
        self.pages[2].addWidget(self.button("复制局域网候选地址", self.copy_url))
        self.pages[2].addWidget(self.button("打开本机管理页面", lambda: self.open_web(local=True)))
        self.backup_details = QPlainTextEdit()
        self.backup_details.setReadOnly(True)
        self.pages[3].addWidget(self.backup_details)
        self.pages[3].addWidget(self.button("立即备份数据库与成果文件", lambda: self.action("backup"), "primary"))
        self.pages[3].addWidget(self.button("打开备份文件夹", self.open_backups))
        self.settings = QLabel()
        self.settings.setWordWrap(True)
        self.settings.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.pages[4].addWidget(self.settings)
        self.pages[4].addWidget(self.button("首次安装 / 修改运行配置", self.setup, "primary"))
        self.tray_option = QCheckBox("关闭窗口时收起到托盘，后台服务保持运行")
        self.tray_option.setChecked(True)
        self.pages[4].addWidget(self.tray_option)
        self.pages[4].addWidget(self.button("退出控制台（不停止后台服务）", self.exit_console))
        self.pages[4].addStretch()
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

    def _tray(self):
        self.tray = QSystemTrayIcon(icon(), self)
        self.tray.setToolTip("引大服务器控制台")
        menu = QMenu()
        for label, handler in (("打开控制台", self.show_console), ("打开管理端", self.open_web), ("启动", lambda: self.action("start")),
                ("停止", lambda: self.action("stop")), ("重启", lambda: self.action("restart")), ("立即备份", lambda: self.action("backup")), ("退出控制台", self.exit_console)):
            item = QAction(label, menu)
            item.triggered.connect(handler)
            menu.addAction(item)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_console() if reason == QSystemTrayIcon.DoubleClick else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def show_console(self):
        self.showNormal()
        self.activateWindow()

    def submit(self, name, function):
        if self.busy:
            if name != "deploy" or self.active_task != "status":
                return False
        if name == "deploy":
            self.deploying = True
            self.timer.stop()
        self.active_task = name
        self.busy = True
        for button in self.buttons:
            button.setEnabled(False)
        self.statusBar().showMessage("正在处理，请稍候…")
        def worker():
            try:
                self.bridge.done.emit(name, function())
            except Exception as exc:
                self.bridge.error.emit(name, safe_error(exc))
        self.pool.submit(worker)
        return True

    def refresh(self):
        if self.wizard_open or self.deploying:
            return
        self.submit("status", self.manager.status)

    def finished(self, name, result):
        if name == "status" and self.deploying:
            return
        self.active_task = None
        self.busy = False
        for button in self.buttons:
            button.setEnabled(True)
        if name == "deploy":
            self.deploying = False
            if self.deployment_dialog:
                self.deployment_dialog.finish(result if isinstance(result, dict) else {"message": str(result)})
            self.timer.start(15000)
            QTimer.singleShot(0, self.refresh)
        elif name == "status":
            self.show_status(result)
        elif name == "preflight":
            self.show_checks(result)
            self.nav.setCurrentRow(1)
            self.statusBar().showMessage("环境检查通过。" if result["ok"] else "环境检查发现问题，请查看详细说明。")
        elif name == "logs":
            self.log_view.setPlainText(str(result))
        else:
            self.log_view.setPlainText(str(result))
            self.statusBar().showMessage(str(result).splitlines()[-1])
            QTimer.singleShot(0, self.refresh)

    def show_checks(self, result):
        self.checks.clear()
        for row in result.get("checks", []):
            item = QTreeWidgetItem([row["name"], {"pass": "通过", "error": "需处理", "notice": "提示"}[row["level"]], row["detail"]])
            item.setForeground(1, QColor("#a65247" if row["level"] == "error" else "#256a50"))
            self.checks.addTopLevelItem(item)

    def show_status(self, result):
        self.last_status = result
        self.current = result["config"]
        self.addresses = result["addresses"]
        self.statusBar().showMessage("最近检查 " + result["checked_at"])
        self.copy_button.setEnabled(self.current is not None)
        self.setup_button.setVisible(self.current is None)
        if not self.current:
            self.banner.setText("尚未完成首次安装。请到“安装与设置”开始，控制台会引导创建本系统专用数据库。")
            self.web_card.set_state("尚未安装", "正式 Windows 后台服务")
            self.database_card.set_state("等待配置", "使用本机 PostgreSQL 17")
            self.backup_card.set_state("暂无备份", "完成安装后可立即备份")
            self.network.setPlainText("尚未配置网站。检测到本机内网 IPv4：\n" + "\n".join(self.addresses))
            self.settings.setText(f"版本：{CONSOLE_VERSION}\n程序目录：{self.manager.home}\n\n请使用完整交付包。旧版数据接续需由维护人员先制定离线备份方案，本向导不会自动搬迁真实业务数据。")
            self.backup_details.setPlainText("尚未完成安装。完整备份包含 PostgreSQL 数据库和全部调查成果文件。")
        else:
            config = self.current
            state = result["service"]
            connected = result["database"].get("connected", False)
            self.banner.setText("后台服务和数据库检查通过。局域网可达性仍需其他电脑确认。" if result["web"] and connected else "部分项目尚未验证通过。可先检查运行环境，查看具体原因。")
            names = {"absent": "未安装", "running": "运行中", "stopped": "已停止", "starting": "启动中", "stopping": "停止中"}
            service_label = "服务归属不符" if state["state"] != "absent" and not state["owned"] else names.get(state["state"], "未确认")
            self.web_card.set_state("运行正常" if result["web"] else service_label, "开机自启：" + ("已配置" if state.get("automatic") else "未确认") + " · 本机 HTTP " + ("通过" if result["web"] else "未通过"), result["web"])
            database = result["database"]
            revision = database.get("revision")
            self.database_card.set_state("连接正常" if connected else "未连接", f"{config.db_host}:{config.db_port}\n结构：" + ("当前版本" if revision and revision == database.get("head") else "未确认") , connected)
            backup = result["backup"]
            self.backup_card.set_state("历史备份待核对" if backup.get("legacy") else "已有完整备份" if backup else "暂无完整备份", backup.get("created_at", "建议在使用前创建第一份备份"), bool(backup) and not backup.get("legacy"))
            urls = result["urls"]
            self.url_label.setText(urls[0] if urls else config.local_url)
            self.url_hint.setText("局域网候选地址 · 需其他电脑实测" if urls else "仅本机地址或尚无匹配的局域网地址")
            self.overview_detail.setText(f"版本 {CONSOLE_VERSION}   /   数据盘剩余 {result['disk']}   /   PostgreSQL 服务：{result['postgres_service']}\n环境检查：" + ("通过" if result["preflight"].get("ok") else "尚未执行或需处理"))
            self.network.setPlainText(f"本机诊断\n{config.local_url}\n\n办公室候选地址（未证明其他电脑可达）\n" + ("\n".join(urls) or "暂无") + f"\n\n已有 HTTPS 地址\n{config.public_base_url or '未配置'} · {result['public']}\n\n控制台不改路由器和防火墙，不开放数据库端口。\n访问失败时，请维护人员核对 Web 端口与办公室网络隔离。\n办公室 HTTP 不加密，不得映射到公网。")
            self.backup_details.setPlainText(("最近完整备份\n" + backup["created_at"] + "\n" + backup["path"] if backup else "暂无经完成标识确认的完整备份。") + f"\n\n备份位置\n{config.data_root / 'backups'}\n\n立即备份会短暂停止本系统 Web 写入，完成后恢复原有运行状态。\n数据库备份与全部成果文件一起保存；失败不会显示为完成。\n恢复界面不在本轮范围内。")
            self.settings.setText(f"{CONSOLE_VERSION}\n程序：{config.install_root}\n成果与备份：{config.data_root}\n运行配置：{config.config_file}\n服务账户：{state.get('account', '尚未确认')}\n\n修改配置前请先停止服务。数据库管理密码仅在创建新库时临时使用，不保存。")
            self.show_checks(result["preflight"])
        for button in self.operation_buttons.values():
            button.setEnabled(self.current is not None)

    def failed(self, name, message):
        if name == "status" and self.deploying:
            return
        self.active_task = None
        self.busy = False
        for button in self.buttons:
            button.setEnabled(True)
        self.statusBar().showMessage(message)
        self.log_view.setPlainText(message)
        if name == "deploy":
            self.deploying = False
            if self.deployment_dialog:
                self.deployment_dialog.finish(error=message)
            self.timer.start(15000)
        elif name == "status":
            self.banner.setText("状态检查未完成：" + message)
        else:
            QMessageBox.warning(self, "操作未完成", message)

    def copy_url(self):
        QApplication.clipboard().setText("\n".join(self.last_status.get("urls", [])) or (self.current.local_url if self.current else ""))

    def open_web(self, checked=False, *, local=False):
        if self.current:
            QDesktopServices.openUrl(QUrl(self.current.local_url if local else self.current.public_base_url or self.current.local_url))

    def open_backups(self):
        if self.current:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current.data_root / "backups")))

    def action(self, name):
        if name == "open":
            return self.open_web()
        if not self.current or self.busy:
            return
        if name == "backup" and QMessageBox.question(self, "备份数据库与成果", "备份期间将短暂停止本系统 Web，完成后恢复原有状态。现在开始备份？") != QMessageBox.Yes:
            return
        handler = {"preflight": self.manager.preflight, "backup": self.manager.backup, "autostart": self.manager.install_autostart, "install": self.manager.install}.get(name)
        self.submit(name, handler or getattr(self.manager, name))

    def setup(self):
        if self.busy:
            return
        self.wizard_open = True
        self.timer.stop()
        wizard = SetupWizard(self.manager.home, self.current, self.addresses, self)
        accepted = wizard.exec() == QDialog.DialogCode.Accepted
        self.wizard_open = False
        if accepted:
            args = (wizard.config, wizard.deploy_mode, wizard.username, wizard.password, wizard.database_admin)
            wizard.clear_secrets()
            self.deployment_dialog = DeploymentProgress(self)
            self.deployment_dialog.show()
            submitted = self.submit("deploy", lambda: self.manager.deploy(*args, progress=self.bridge.progress.emit))
            if not submitted:
                self.deployment_dialog.finish(error="当前另一个维护操作正在执行，请等待其完成后重试；安装未被提交。")
        else:
            wizard.clear_secrets()
            self.timer.start(15000)

    def show_progress(self, step, state, detail):
        if self.deployment_dialog:
            self.deployment_dialog.update_step(step, state, detail)

    def read_logs(self):
        if self.current:
            name = self.log_choice.currentData()
            self.submit("logs", lambda: self.manager.logs(name))

    def exit_console(self):
        if self.busy:
            return
        self.exiting = True
        self.close()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        elif not self.exiting and self.tray_option.isChecked() and self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self.timer.stop()
            self.tray.hide()
            self.pool.shutdown(wait=False)
            event.accept()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YindaSurvey.WebCenter")
    app = QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME + " Web Center")
    app.setWindowIcon(icon())
    app.setStyleSheet(STYLE)
    window = ServerConsole(ServerManager(args.home))
    window.show()
    if args.smoke_test:
        timer = QTimer(window)
        timer.timeout.connect(window.exit_console)
        timer.start(1200)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
