"""Yinda Web production server console. The Web process outlives this GUI."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
import webbrowser

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QPushButton, QSystemTrayIcon,
    QTextEdit, QVBoxLayout, QWidget,
)

from server_console_core import ConsolePaths, LOCAL_URL, ServerManager, tail


class Bridge(QObject):
    status = Signal(dict)
    result = Signal(str)
    error = Signal(str)
    logs = Signal(str)


def icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#295ccc"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setFamily("Microsoft YaHei UI")
    font.setPixelSize(39)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "引")
    painter.end()
    return QIcon(pixmap)


class StatusCard(QFrame):
    def __init__(self, title: str, detail: str):
        super().__init__()
        self.setObjectName("statusCard")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("cardHeading")
        self.value = QLabel("正在检查…")
        self.value.setObjectName("cardValue")
        self.detail = QLabel(detail)
        self.detail.setObjectName("cardDetail")
        self.detail.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def update_state(self, value: str, detail: str | None = None):
        self.value.setText("●  " + value)
        color = "#56d6a1" if value in {"运行正常", "正常", "连接正常"} else "#f1bd66" if value.startswith(("未配置", "已停止")) else "#f17d85"
        self.value.setStyleSheet(f"color: {color};")
        if detail is not None:
            self.detail.setText(detail)


class ServerConsole(QMainWindow):
    def __init__(self, manager: ServerManager | None = None):
        super().__init__()
        self.manager = manager or ServerManager()
        self.paths = self.manager.paths
        self.bridge = Bridge()
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.refreshing = False
        self.busy = False
        self.exiting = False
        self.setWindowTitle("引大调查 Web 中心服务")
        self.setWindowIcon(icon())
        self.resize(1120, 760)
        self.setMinimumSize(960, 670)
        self._build()
        self._tray()
        self.bridge.status.connect(self._show_status)
        self.bridge.result.connect(self._show_result)
        self.bridge.error.connect(self._show_error)
        self.bridge.logs.connect(self.log_view.setPlainText)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(15000)
        self.refresh()

    def _build(self):
        body = QWidget()
        self.setCentralWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(32, 26, 32, 25)
        outer.setSpacing(18)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("引大调查 Web 中心服务")
        title.setObjectName("title")
        subtitle = QLabel("数据中心运行与维护控制台  ·  Production")
        subtitle.setObjectName("muted")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()
        self.overall = QLabel("● 正在检查")
        self.overall.setObjectName("overall")
        header.addWidget(self.overall)
        outer.addLayout(header)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.database_card = StatusCard("PostgreSQL", "本机数据库连接")
        self.web_card = StatusCard("Web 服务", "127.0.0.1:8000 · /api/v1/health")
        self.public_card = StatusCard("公网访问", "PUBLIC_BASE_URL")
        for card in (self.database_card, self.web_card, self.public_card):
            cards.addWidget(card, 1)
        outer.addLayout(cards)

        actions = QHBoxLayout()
        self.buttons = []
        for label, command, kind in (
            ("启动 Web 服务", "start", "primary"),
            ("停止 Web 服务", "stop", "danger"),
            ("重启 Web 服务", "restart", "normal"),
            ("打开管理端", "open", "normal"),
            ("生产环境预检", "preflight", "normal"),
            ("立即备份", "backup", "normal"),
            ("设置开机自启", "autostart", "normal"),
        ):
            button = QPushButton(label)
            button.setObjectName(kind)
            button.clicked.connect(lambda checked=False, name=command: self.action(name))
            actions.addWidget(button)
            self.buttons.append(button)
        outer.addLayout(actions)

        diagnostics = QFrame()
        diagnostics.setObjectName("panel")
        grid = QGridLayout(diagnostics)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(11)
        fields = [
            ("数据库连接", "database"), ("PostgreSQL 服务", "postgres_service"),
            ("数据库结构", "alembic"), ("生产预检", "preflight"),
            ("APP_ENV", "app_env"), ("管理页面", "frontend"),
            ("storage", "storage"), ("backups", "backups"),
            ("剩余磁盘空间", "disk"), ("最近检查", "checked_at"),
        ]
        self.fields = {}
        for index, (label, key) in enumerate(fields):
            row, pair = divmod(index, 2)
            caption = QLabel(label)
            caption.setObjectName("muted")
            value = QLabel("—")
            value.setObjectName("fieldValue")
            grid.addWidget(caption, row, pair * 2)
            grid.addWidget(value, row, pair * 2 + 1)
            self.fields[key] = value
        outer.addWidget(diagnostics)

        log_panel = QFrame()
        log_panel.setObjectName("panel")
        log_layout = QVBoxLayout(log_panel)
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("运行日志"))
        log_header.addStretch()
        self.log_choice = QComboBox()
        for label, name in (("Web 服务", "server"), ("控制台操作", "operations"), ("备份", "backup"), ("生产预检", "preflight")):
            self.log_choice.addItem(label, name)
        self.log_choice.currentIndexChanged.connect(self.refresh_logs)
        log_header.addWidget(self.log_choice)
        log_button = QPushButton("查看运行日志")
        log_button.clicked.connect(self.refresh_logs)
        log_header.addWidget(log_button)
        log_layout.addLayout(log_header)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("仅显示最近 100 行日志。")
        log_layout.addWidget(self.log_view)
        outer.addWidget(log_panel, 1)

        foot = QLabel("关闭控制台仅收起窗口；Web 服务持续运行。请使用“停止 Web 服务”明确停服。")
        foot.setObjectName("muted")
        outer.addWidget(foot)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #101826; color: #e9edf5; font-family: 'Microsoft YaHei UI'; font-size: 13px; }
            QLabel { background: transparent; }
            QLabel#title { font-size: 25px; font-weight: 700; }
            QLabel#muted, QLabel#cardDetail { color: #91a1b8; }
            QLabel#overall { font-size: 17px; font-weight: 700; color: #f1bd66; }
            QFrame#statusCard, QFrame#panel { background: #1b2739; border: 1px solid #304159; border-radius: 12px; }
            QFrame#statusCard { min-height: 110px; }
            QLabel#cardHeading { font-size: 15px; font-weight: 650; }
            QLabel#cardValue { font-size: 20px; font-weight: 700; }
            QLabel#fieldValue { font-weight: 600; }
            QPushButton { background: #293950; color: #e9edf5; border: 1px solid #40536e; border-radius: 8px; padding: 9px 12px; }
            QPushButton:hover { background: #3b4d67; }
            QPushButton#primary { background: #3563c6; border-color: #3563c6; }
            QPushButton#danger { background: #52323a; border-color: #65434d; }
            QPushButton:disabled { color: #7b899b; background: #253246; }
            QTextEdit { background: #121c2a; border: 1px solid #304159; border-radius: 7px; font-family: Consolas; }
            QComboBox { background: #293950; padding: 5px 10px; border: 1px solid #40536e; border-radius: 6px; }
        """)

    def _tray(self):
        self.tray = QSystemTrayIcon(icon(), self)
        self.tray.setToolTip("引大调查 Web 中心服务")
        menu = QMenu()
        for label, command in (
            ("打开控制台", "show"), ("打开管理端", "open"),
            ("启动 Web", "start"), ("重启 Web", "restart"),
            ("停止 Web", "stop"), ("退出控制台", "exit"),
        ):
            item = QAction(label, menu)
            item.triggered.connect(lambda checked=False, name=command: self.action(name))
            menu.addAction(item)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def refresh(self):
        if self.refreshing:
            return
        self.refreshing = True
        def work():
            try:
                self.bridge.status.emit(self.manager.status())
            except Exception:
                self.bridge.error.emit("状态检查失败，请查看运行日志。")
            finally:
                self.refreshing = False
        self.pool.submit(work)
        self.refresh_logs()

    def _show_status(self, status: dict):
        self.database_card.update_state(status["database"], f"localhost:{status['db_port']} · {status['postgres_service']}")
        self.web_card.update_state(status["web"], f"127.0.0.1:8000 · PID {status['pid']}")
        self.public_card.update_state(status["public"], status["public_url"] or "未配置公网访问地址")
        for key, label in self.fields.items():
            label.setText(status.get(key, "—"))
        if status["web"] == "运行正常" and status["postgresql"] == "连接端口正常" and status["database"] == "连接正常" and status["public"] in {"正常", "未配置公网访问地址"}:
            self.overall.setText("● 正常")
            self.overall.setStyleSheet("color: #56d6a1;")
        elif status["web"] == "已停止":
            self.overall.setText("● 已停止")
            self.overall.setStyleSheet("color: #91a1b8;")
        else:
            self.overall.setText("● 部分异常")
            self.overall.setStyleSheet("color: #f1bd66;")

    def refresh_logs(self):
        name = self.log_choice.currentData()
        self.bridge.logs.emit(tail(self.paths.runtime / "logs" / f"{name}.log"))

    def _show_result(self, message: str):
        self.busy = False
        for button in self.buttons:
            button.setEnabled(True)
        self.refresh()
        QMessageBox.information(self, "操作完成", message)

    def _show_error(self, message: str):
        self.busy = False
        for button in self.buttons:
            button.setEnabled(True)
        QMessageBox.warning(self, "操作未完成", message)

    def action(self, command: str):
        if command == "show":
            self.showNormal()
            self.activateWindow()
            return
        if command == "exit":
            self.exiting = True
            self.tray.hide()
            QApplication.instance().quit()
            return
        if command == "open":
            webbrowser.open(LOCAL_URL)
            return
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.setEnabled(False)
        def work():
            try:
                if command == "preflight":
                    ok, detail = self.manager.preflight()
                    if not ok:
                        raise RuntimeError(detail)
                    message = "生产环境预检通过。\n" + detail
                elif command == "autostart":
                    message = self.manager.install_autostart()
                else:
                    message = getattr(self.manager, command)()
                self.bridge.result.emit(message)
            except RuntimeError as exc:
                self.bridge.error.emit(str(exc))
            except Exception:
                self.bridge.error.emit("操作失败，请查看运行日志并检查服务器配置。")
        self.pool.submit(work)

    def closeEvent(self, event):
        if not self.exiting and self.tray.isVisible():
            self.hide()
            self.tray.showMessage("引大调查 Web 中心服务", "控制台已收起，Web 服务继续运行。")
            event.ignore()
            return
        event.accept()


def main():
    app = QApplication([])
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc"
    if font_path.is_file():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    window = ServerConsole()
    window.show()
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(500, app.quit)
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
