"""First-install UI only. All deployment work is dispatched through ServerManager."""
from pathlib import Path
import secrets
from uuid import uuid4

from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QWizard, QWizardPage)

from deployment.config import DeploymentConfig, safe_error
from deployment.postgres import installed_bin
from server_console_core import LEGACY_TASK_NOTICE


class SetupWizard(QWizard):
    def __init__(self, home, current, addresses, parent=None):
        super().__init__(parent)
        self.setWindowTitle("引大 · 安装与运行配置")
        self.setWizardStyle(QWizard.ModernStyle)
        self.resize(860, 780)
        for button, text in ((QWizard.NextButton, "继续"), (QWizard.BackButton, "上一步"),
                             (QWizard.FinishButton, "完成配置并启动"), (QWizard.CancelButton, "取消")):
            self.setButtonText(button, text)
        self.inputs = {}
        def page(title, subtitle):
            widget = QWizardPage()
            widget.setTitle(title)
            widget.setSubTitle(subtitle)
            form = QFormLayout(widget)
            form.setVerticalSpacing(12)
            self.addPage(widget)
            return form
        def text(form, key, label, default, *, secret=False, folder=False):
            edit = QLineEdit(str(default))
            edit.setMinimumHeight(30)
            if secret:
                edit.setEchoMode(QLineEdit.Password)
            self.inputs[key] = edit
            if folder:
                row = QHBoxLayout()
                row.addWidget(edit)
                button = QPushButton("选择文件夹")
                def choose():
                    selected = QFileDialog.getExistingDirectory(self, label, edit.text())
                    if selected:
                        edit.setText(selected)
                button.clicked.connect(choose)
                row.addWidget(button)
                form.addRow(label, row)
            else:
                form.addRow(label, edit)
        def note(form, content):
            label = QLabel(content)
            label.setWordWrap(True)
            label.setObjectName("hint")
            form.addRow(label)
        form = page("1 / 4   安装位置", "选择固定文件夹。更新程序时，调查成果和备份会继续保留。")
        text(form, "install_root", "程序放在哪里", current.install_root if current else home, folder=True)
        text(form, "data_root", "成果、备份与日志", current.data_root if current else home / "persistent", folder=True)
        note(form, "建议使用默认位置。数据库由本机已安装的 PostgreSQL 17 独立保存。\n安装后台服务需要以 Windows 管理员身份打开控制台。")
        form = page("2 / 4   数据保存", "推荐由向导创建本系统专用数据库和普通账号，不需要手动使用数据库管理工具。")
        self.mode = QComboBox()
        self.mode.addItem("为新安装自动创建专用数据库（推荐）", "create")
        self.mode.addItem("使用维护人员已准备好的空数据库", "new")
        self.mode.addItem("接续本控制台已有部署 / 修复配置", "continue")
        form.addRow("这次要做什么", self.mode)
        suffix = uuid4().hex[:6]
        for key, label, default in (("db_host", "数据库所在电脑", "127.0.0.1"), ("db_port", "数据库端口", "5432"),
                ("db_name", "本系统数据库名称", f"yinda_web_{suffix}"), ("db_user", "本系统运行账号", f"yinda_web_{suffix}_app"),
                ("db_password", "运行账号密码", secrets.token_urlsafe(24)), ("pg_bin", "PostgreSQL 工具文件夹", installed_bin())):
            text(form, key, label, getattr(current, key) if current else default, secret=key == "db_password", folder=key == "pg_bin")
        self.admin_group = QGroupBox("仅创建新数据库时使用：PostgreSQL 安装时的管理账号")
        admin_form = QFormLayout(self.admin_group)
        text(admin_form, "db_admin_username", "管理账号", "postgres")
        text(admin_form, "db_admin_password", "管理密码（不保存）", "", secret=True)
        form.addRow(self.admin_group)
        self.mode.currentIndexChanged.connect(lambda: self.admin_group.setVisible(self.mode.currentData() == "create"))
        if current:
            self.mode.setCurrentIndex(2 if current.state_file.exists() else 1)
        note(form, "自动创建只连接本机 PostgreSQL：发现同名数据库或账号就停止，不覆盖或接管已有数据。\n尚未安装 PostgreSQL 17 时，请先完成安装；工具文件夹通常为其 bin 文件夹。")
        download = QPushButton("打开 PostgreSQL 官方安装下载页")
        download.clicked.connect(self.download_postgres)
        form.addRow(download)
        form = page("3 / 4   办公室访问", "让办公室电脑通过浏览器访问。无需修改路由器，不开放数据库端口。")
        for key, label, default in (("web_port", "网站端口", 8000), ("listen_host", "监听地址（默认所有本机网卡）", "0.0.0.0"),
                ("allowed_hosts", "允许访问的服务器地址", ",".join(["127.0.0.1", "localhost", *addresses])),
                ("postgres_service_name", "PostgreSQL 服务名（可留空）", ""), ("public_base_url", "已有 HTTPS 访问地址（可留空）", "")):
            text(form, key, label, getattr(current, key) if current else default)
        note(form, "本机检查与其他电脑访问分开显示。允许地址填写本机 IP 或主机名，多个地址用逗号分隔。\n本批使用办公室 HTTP：传输不加密，不得向公网映射。已有 HTTPS 地址仅用于打开与健康检查，不配置证书或代理。")
        form = page("4 / 4   管理员与后台服务", "完成后可打开管理页面。退出控制台或注销 Windows 不会主动停止后台服务。")
        text(form, "username", "网页登录账号", "admin")
        text(form, "admin_password", "网页登录密码（至少 12 位）", "", secret=True)
        text(form, "repeat_password", "再输入一次", "", secret=True)
        note(form, "这些是网站的管理员账号，与上一步数据库管理账号不同。已有管理员不会重置。\n" + LEGACY_TASK_NOTICE + "\n失败后保留进度供核对，不会自动删除数据库、账号或成果文件。")

    def download_postgres(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://www.postgresql.org/download/windows/"))

    def accept(self):
        try:
            values = {key: edit.text() if "password" in key else edit.text().strip() for key, edit in self.inputs.items()}
            self.username = values.pop("username")
            self.password = values.pop("admin_password")
            if values.pop("repeat_password") != self.password or not 12 <= len(self.password) <= 128:
                raise ValueError("请填写两次相同的网页登录密码，长度 12 至 128 位。")
            admin_user = values.pop("db_admin_username")
            admin_password = values.pop("db_admin_password")
            self.database_admin = None
            if self.mode.currentData() == "create":
                if not admin_user or not admin_password:
                    raise ValueError("创建专用数据库需要 PostgreSQL 安装时的管理账号和密码。")
                self.database_admin = {"username": admin_user, "password": admin_password, "create_dedicated": True}
            for key in ("install_root", "data_root"):
                values[key] = Path(values[key])
            for key in ("db_port", "web_port"):
                values[key] = int(values[key])
            self.config = DeploymentConfig(**values)
            self.config.validate()
            self.deploy_mode = "new" if self.mode.currentData() == "create" else self.mode.currentData()
        except Exception as exc:
            QMessageBox.warning(self, "请检查填写内容", safe_error(exc))
            return
        super().accept()

    def clear_secrets(self):
        for key, edit in self.inputs.items():
            if "password" in key:
                edit.clear()
        self.password = ""
        self.database_admin = None
