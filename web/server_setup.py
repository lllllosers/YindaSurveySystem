"""The existing product's first-install wizard and visible deployment result view."""
from pathlib import Path
import secrets

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QRadioButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget, QWizard, QWizardPage)

from branding import PRODUCT_NAME, asset
from deployment.config import DeploymentConfig, safe_error, validate_admin
from deployment.installer import STEPS
from deployment.postgres import installation_status
from server_console_core import LEGACY_TASK_NOTICE


def network_values(mode, addresses):
    if mode == "public":
        raise ValueError("公网访问需要先配置 HTTPS 入口，本安装向导不直接开放公网 HTTP。")
    return {"listen_host": "127.0.0.1" if mode == "local" else "0.0.0.0",
            "allowed_hosts": ",".join(dict.fromkeys(["127.0.0.1", "localhost", *(addresses if mode == "lan" else [])]))}


class SetupWizard(QWizard):
    def __init__(self, home, current, addresses, parent=None):
        super().__init__(parent)
        self.current, self.addresses = current, addresses
        self.setWindowTitle(PRODUCT_NAME + " · 安装 Web Center")
        self.setWindowIcon(QIcon(str(asset("YindaWebCenter.ico"))))
        self.setWizardStyle(QWizard.ModernStyle)
        self.resize(840, 710)
        self.setMinimumSize(760, 600)
        self.setPixmap(QWizard.LogoPixmap, QPixmap(str(asset("BrandMark.png"))).scaled(54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        for button, label in ((QWizard.NextButton, "下一步"), (QWizard.BackButton, "上一步"),
                              (QWizard.FinishButton, "完成配置并启动"), (QWizard.CancelButton, "取消")):
            self.setButtonText(button, label)
        self.inputs = {}
        self.advanced_sections = []
        def page(title, subtitle):
            widget = QWizardPage()
            widget.setTitle(title)
            widget.setSubTitle(subtitle)
            outer = QVBoxLayout(widget)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            content = QWidget()
            form = QFormLayout(content)
            form.setVerticalSpacing(15)
            form.setContentsMargins(8, 14, 8, 14)
            scroll.setWidget(content)
            outer.addWidget(scroll)
            self.addPage(widget)
            return form
        def text(form, key, label, default, secret=False, folder=False):
            edit = QLineEdit(str(default))
            edit.setMinimumHeight(31)
            if secret:
                edit.setEchoMode(QLineEdit.Password)
            self.inputs[key] = edit
            if folder:
                row = QHBoxLayout()
                row.addWidget(edit)
                button = QPushButton("选择文件夹")
                def choose():
                    value = QFileDialog.getExistingDirectory(self, label, edit.text())
                    if value:
                        edit.setText(value)
                button.clicked.connect(choose)
                row.addWidget(button)
                form.addRow(label, row)
            else:
                form.addRow(label, edit)
        def note(form, message):
            label = QLabel(message)
            label.setWordWrap(True)
            label.setObjectName("hint")
            form.addRow(label)
        def advanced(form):
            toggle = QCheckBox("高级设置（供维护人员使用）")
            group = QGroupBox()
            inner = QFormLayout(group)
            inner.setVerticalSpacing(12)
            form.addRow(toggle)
            form.addRow(group)
            group.hide()
            toggle.toggled.connect(group.setVisible)
            self.advanced_sections.append((toggle, group))
            return inner
        form = page("1 / 4   选择安装位置", "程序与业务数据分开保存，更新程序时不会覆盖调查成果。")
        text(form, "install_root", "程序安装目录", current.install_root if current else home, folder=True)
        text(form, "data_root", "数据存储目录", current.data_root if current else home / "data", folder=True)
        note(form, "数据存储目录统一保存成果文件、备份、日志及运行配置。建议保留默认位置。\n首次安装后台服务需要 Windows 管理员权限。")
        form = page("2 / 4   准备数据库", "使用 PostgreSQL 17 保存数据。无需手动建库，也无需记住系统生成的运行账号密码。")
        detected = installation_status(current.pg_bin if current else "", current.postgres_service_name if current else "")
        self.postgres_detected = detected
        self.postgres_label = QLabel(detected["detail"])
        self.postgres_label.setWordWrap(True)
        form.addRow(self.postgres_label)
        self.installed = QCheckBox("我已安装 PostgreSQL 17")
        self.installed.setChecked(detected["installed"])
        form.addRow(self.installed)
        self.mode = QComboBox()
        self.mode.addItem("创建本系统专用数据库（推荐）", "create")
        self.mode.addItem("接续本系统已有安装 / 修复配置", "continue")
        self.mode.addItem("使用维护人员准备的空数据库", "new")
        form.addRow("数据准备方式", self.mode)
        self.admin_group = QGroupBox("PostgreSQL 安装时设置的管理密码")
        admin_form = QFormLayout(self.admin_group)
        text(admin_form, "db_admin_password", "管理密码", "", secret=True)
        note(admin_form, "仅用于首次创建专用数据库，不保存到配置、日志或命令行。")
        form.addRow(self.admin_group)
        self.mode.currentIndexChanged.connect(lambda: self.admin_group.setVisible(self.mode.currentData() == "create"))
        if current:
            self.mode.setCurrentIndex(1 if current.state_file.exists() else 2)
        download = QPushButton("安装 PostgreSQL 17：打开官方下载页")
        download.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.postgresql.org/download/windows/")))
        form.addRow(download)
        note(form, "尚未安装时，先运行 PostgreSQL 17 安装程序，记下安装时设置的管理密码，再返回此处。\n发现同名数据库或账号会停止安装，不覆盖或修改原密码。可选择接续，或请维护人员另建部署。")
        inner = advanced(form)
        defaults = {"db_host": "127.0.0.1", "db_port": 5432, "db_name": "yinda_web_center", "db_user": "yinda_web_user",
                    "db_password": secrets.token_urlsafe(32), "pg_bin": detected.get("pg_bin", ""), "postgres_service_name": detected.get("service_name", "")}
        for key, label in (("db_host", "数据库地址"), ("db_port", "数据库端口"), ("db_name", "专用数据库名称"),
                ("db_user", "数据库运行账号"), ("db_password", "数据库运行密码（自动生成）"), ("pg_bin", "PostgreSQL 工具目录"), ("postgres_service_name", "数据库系统服务名")):
            text(inner, key, label, getattr(current, key) if current else defaults[key], secret=key == "db_password", folder=key == "pg_bin")
        text(inner, "db_admin_username", "PostgreSQL 管理账号", "postgres")
        form = page("3 / 4   选择访问方式", "默认供办公室电脑使用，不修改路由器，也不会开放数据库端口。")
        self.network_group = QButtonGroup(self)
        self.network_buttons = {}
        for label, value in (("仅本机访问", "local"), ("局域网访问（推荐）", "lan"), ("公网访问（需配置 HTTPS 后启用）", "public")):
            radio = QRadioButton(label)
            self.network_group.addButton(radio)
            self.network_buttons[value] = radio
            form.addRow(radio)
        self.network_buttons["public"].setEnabled(False)
        self.network_buttons["local" if current and current.listen_host == "127.0.0.1" else "lan"].setChecked(True)
        note(form, "局域网模式会自动使用当前活动网卡地址，网站端口默认为 8000。\n办公室 HTTP 传输不加密，不能直接映射到公网。其他电脑能否访问仍需现场确认。")
        inner = advanced(form)
        text(inner, "web_port", "网站端口", current.web_port if current else 8000)
        self.manual_network = QCheckBox("手动指定网络参数")
        inner.addRow(self.manual_network)
        values = network_values("lan", addresses)
        for key, label in (("listen_host", "监听地址"), ("allowed_hosts", "允许的服务器地址"), ("public_base_url", "已有合法 HTTPS 地址（仅检查）")):
            text(inner, key, label, getattr(current, key) if current else values.get(key, ""))
        form = page("4 / 4   创建系统管理员", "这是登录 Web Center 的账号，与 PostgreSQL 的数据库账号完全不同。")
        text(form, "username", "创建系统管理员账号", "admin")
        text(form, "admin_password", "设置系统管理员密码", "", secret=True)
        text(form, "repeat_password", "确认管理员密码", "", secret=True)
        note(form, "请自行设置至少 8 位的密码，没有固定默认密码。接续已有安装时不会重置原管理员。\n点击下方按钮后会显示每一步进度；失败会说明原因和日志位置。\n" + LEGACY_TASK_NOTICE)

    def accept(self):
        try:
            if not self.installed.isChecked():
                raise ValueError("需要先安装 PostgreSQL 17。请返回数据库步骤，打开官方安装入口。")
            values = {key: edit.text() if "password" in key else edit.text().strip() for key, edit in self.inputs.items()}
            self.password = values.pop("admin_password")
            if values.pop("repeat_password") != self.password:
                raise ValueError("两次系统管理员密码不一致，请重新确认。")
            self.username = validate_admin(values.pop("username"), self.password)
            admin_password = values.pop("db_admin_password")
            admin_user = values.pop("db_admin_username")
            self.database_admin = None
            if self.mode.currentData() == "create":
                if not admin_password:
                    raise ValueError("请填写 PostgreSQL 安装时设置的管理密码。")
                self.database_admin = {"username": admin_user, "password": admin_password, "create_dedicated": True}
            if not self.manual_network.isChecked():
                mode = "local" if self.network_buttons["local"].isChecked() else "lan"
                values.update(network_values(mode, self.addresses))
            for key in ("install_root", "data_root"):
                values[key] = Path(values[key])
            for key in ("db_port", "web_port"):
                values[key] = int(values[key])
            values["data_layout"] = self.current.data_layout if self.current else "flat"
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


class DeploymentProgress(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(PRODUCT_NAME + " · 安装进度")
        self.setWindowIcon(QIcon(str(asset("YindaWebCenter.ico"))))
        self.setWindowModality(Qt.WindowModal)
        self.resize(790, 650)
        self.running = True
        self.started = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        self.heading = QLabel("正在部署 Web Center")
        self.heading.setObjectName("title")
        layout.addWidget(self.heading)
        self.meter = QProgressBar()
        self.meter.setRange(0, 0)
        layout.addWidget(self.meter)
        self.rows = {}
        for key, title in STEPS:
            row = QLabel("○  " + title + "    尚未开始")
            row.setWordWrap(True)
            layout.addWidget(row)
            self.rows[key] = row
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("部署开始后，这里会显示步骤和处理结果。")
        layout.addWidget(self.detail, 1)
        actions = QHBoxLayout()
        self.open_button = QPushButton("打开 Web Center")
        self.open_button.hide()
        self.open_button.clicked.connect(self.open_web)
        actions.addWidget(self.open_button)
        self.return_button = QPushButton("返回控制台")
        self.return_button.setEnabled(False)
        self.return_button.clicked.connect(self.accept)
        actions.addWidget(self.return_button)
        layout.addLayout(actions)
        self.url = ""

    def update_step(self, key, state, detail):
        if key in self.rows:
            self.rows[key].setText({"running": "◌  ", "complete": "✓  ", "failed": "!  "}[state] + dict(STEPS)[key] + "    " + {"running": "正在执行", "complete": "已完成", "failed": "失败"}[state])
        if detail:
            self.detail.append(dict(STEPS).get(key, key) + "：" + detail)

    def finish(self, result=None, error=""):
        self.running = False
        self.meter.setRange(0, 1)
        self.meter.setValue(1 if not error else 0)
        self.return_button.setEnabled(True)
        if error:
            self.heading.setText("安装未完成，请按提示处理")
            self.detail.append(error)
        else:
            self.heading.setText("Web Center 已成功启动")
            self.url = result.get("local_url", "")
            self.detail.append("访问地址：" + self.url + "\n" + result.get("log_path", ""))
            self.open_button.show()

    def open_web(self):
        QDesktopServices.openUrl(QUrl(self.url))

    def reject(self):
        if not self.running:
            super().reject()

    def closeEvent(self, event):
        event.ignore() if self.running else event.accept()
