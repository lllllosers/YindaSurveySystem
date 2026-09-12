import sys
from database import (
    create_initial_forms,
    get_current_context,
    get_survey_readiness,
    init_database,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)
from pages.basic_data_page import BasicDataPage
from pages.survey_page import SurveyPage
from pages.engineering_asset_page import EngineeringAssetPage
from pages.project_batch_page import ProjectBatchPage
from services.database_backup import (
    create_database_backup,
)
from version import (
    APP_AUTHOR,
    APP_NAME,
    APP_STAGE,
    APP_VERSION_LABEL,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_context = get_current_context()
        self.current_page_name = "首页"

        self.setWindowTitle(f"{APP_NAME} - {APP_VERSION_LABEL}")
        self.resize(1200, 760)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # =========================
        # 左侧导航栏
        # =========================
        sidebar = QFrame()
        sidebar.setFixedWidth(210)
        sidebar.setObjectName("sidebar")

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(10)

        app_title = QLabel("引大调查")
        app_title.setObjectName("appTitle")
        sidebar_layout.addWidget(app_title)

        subtitle = QLabel("数据采集系统")
        subtitle.setObjectName("appSubtitle")
        sidebar_layout.addWidget(subtitle)

        sidebar_layout.addSpacing(20)

        nav_items = [
            "首页",
            "本次调查",
            "工程台账",
            "数据查询",
            "成果导出",
            "基础资料",
            "项目与批次",
            "设置",
        ]

        for item in nav_items:
            button = QPushButton(item)
            button.setObjectName("navButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, name=item: self.change_page(name)
            )
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch()

        version_label = QLabel(f"{APP_VERSION_LABEL} {APP_STAGE}")
        version_label.setObjectName("versionLabel")
        sidebar_layout.addWidget(version_label)

        root_layout.addWidget(sidebar)

        # =========================
        # 右侧工作区
        # =========================
        workspace = QWidget()

        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(28, 22, 28, 28)
        workspace_layout.setSpacing(20)

        # 顶部当前项目信息
        top_bar = QFrame()
        top_bar.setObjectName("topBar")

        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(18, 12, 18, 12)

        if self.current_context:
            project_name = self.current_context["project_name"]
            batch_name = self.current_context["batch_name"] or "未选择调查批次"
        else:
            project_name = "未选择项目"
            batch_name = "未选择调查批次"

        self.project_label = QLabel(f"当前项目：{project_name}")

        self.batch_label = QLabel(f"当前调查批次：{batch_name}")

        top_layout.addWidget(self.project_label)
        top_layout.addStretch()
        top_layout.addWidget(self.batch_label)

        workspace_layout.addWidget(top_bar)

        # 页面标题
        self.page_title = QLabel("首页")
        self.page_title.setObjectName("pageTitle")
        workspace_layout.addWidget(self.page_title)

        # 页面主体占位区
        content = QFrame()
        content.setObjectName("contentCard")

        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(30, 30, 30, 30)

        self.content_label = QLabel(
            f"{APP_NAME}\n\n"
            f"{APP_VERSION_LABEL} {APP_STAGE}\n\n"
            "当前已完成附表2.2水闸工程状况调查"
            "完整数据采集闭环。\n\n"
            f"开发者：{APP_AUTHOR}"
        )
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_label.setWordWrap(True)
        self.content_label.setObjectName("contentLabel")

        self.content_layout.addWidget(self.content_label)

        workspace_layout.addWidget(content, 1)

        root_layout.addWidget(workspace, 1)

        # =========================
        # 简单样式
        # =========================
        self.setStyleSheet("""
            QMainWindow {
                background: #f5f6f8;
            }

            #sidebar {
                background: #243447;
            }

            #appTitle {
                color: white;
                font-size: 22px;
                font-weight: bold;
            }

            #appSubtitle {
                color: #c7d0da;
                font-size: 13px;
            }

            #navButton {
                background: transparent;
                color: #e7edf3;
                border: none;
                text-align: left;
                padding: 11px 12px;
                border-radius: 6px;
                font-size: 14px;
            }

            #navButton:hover {
                background: #34495e;
            }

            #versionLabel {
                color: #9caaba;
                font-size: 12px;
            }

            #topBar {
                background: white;
                border: 1px solid #e2e5e9;
                border-radius: 8px;
            }

            #pageTitle {
                font-size: 24px;
                font-weight: bold;
                color: #263238;
            }

            #contentCard {
                background: white;
                border: 1px solid #e2e5e9;
                border-radius: 10px;
            }

            #contentLabel {
                color: #52606d;
                font-size: 16px;
            }
            """)

    def refresh_current_context(self):
        """
        项目或调查批次切换后，
        重新读取当前上下文并刷新顶部显示。
        """

        self.current_context = get_current_context()

        if self.current_context:
            project_name = self.current_context["project_name"] or "未选择项目"

            batch_name = self.current_context["batch_name"] or "未选择调查批次"

        else:
            project_name = "未选择项目"
            batch_name = "未选择调查批次"

        self.project_label.setText(f"当前项目：{project_name}")

        self.batch_label.setText("当前调查批次：" f"{batch_name}")

    def has_active_survey_context(self):
        """
        判断当前是否已经存在可用于调查工作的
        启用项目和启用调查批次。
        """

        if self.current_context is None:
            return False

        return (
            self.current_context.get("project_id") is not None
            and self.current_context.get("batch_id") is not None
        )

    def can_start_survey(self):
        """
        检查当前系统是否已经具备
        开始工程调查的基础条件。
        """

        readiness = (
            get_survey_readiness()
        )

        if readiness["ready"]:
            return True

        missing_items = "\n".join(
            f"• {item}"
            for item in readiness[
                "missing"
            ]
        )

        QMessageBox.information(
            self,
            "基础资料尚未完善",
            (
                "开始调查前还需要完成"
                "以下基础配置：\n\n"
                f"{missing_items}\n\n"
                "请进入“项目与批次”或"
                "“基础资料”完成配置后，"
                "再进入本次调查。"
            ),
        )

        return False

    def change_page(self, page_name):

        # 已经在当前模块时不重复销毁和创建页面。
        if page_name == self.current_page_name:
            return

        # =========================
        # 正式运行环境完整性检查
        # =========================

        if page_name in (
            "本次调查",
            "工程台账",
        ):
            if not self.has_active_survey_context():
                QMessageBox.information(
                    self,
                    "尚未配置调查项目",
                    (
                        "当前没有可用的项目和调查批次。\n\n"
                        "请先完成项目与调查批次配置，"
                        "再进入调查业务模块。"
                    ),
                )
                return

        # =========================
        # 调查基础资料完整性检查
        # =========================

        if page_name == "本次调查":
            if not self.can_start_survey():
                return

        # 如果正在“本次调查”中编辑表单，
        # 离开主模块前先检查未保存修改。
        if self.current_page_name == "本次调查":
            survey_page = getattr(
                self,
                "survey_page",
                None,
            )

            if survey_page is not None:
                if not survey_page.can_leave_page():
                    return

        self.page_title.setText(page_name)

        self.clear_content()

        if page_name == "本次调查":
            self.survey_page = SurveyPage()

            self.content_layout.addWidget(self.survey_page)

        elif page_name == "工程台账":
            self.engineering_asset_page = EngineeringAssetPage()

            self.content_layout.addWidget(self.engineering_asset_page)

        elif page_name == "基础资料":
            self.basic_data_page = BasicDataPage()

            self.content_layout.addWidget(self.basic_data_page)

        elif page_name == "项目与批次":
            self.project_batch_page = ProjectBatchPage()

            self.project_batch_page.context_changed.connect(
                self.refresh_current_context
            )

            self.content_layout.addWidget(self.project_batch_page)

        else:
            self.content_label = QLabel(
                f"{page_name}\n\n" "该模块将在后续开发步骤中逐步实现。"
            )

            self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.content_label.setWordWrap(True)
            self.content_label.setObjectName("contentLabel")

            self.content_layout.addWidget(self.content_label)

        self.current_page_name = page_name

    def closeEvent(self, event):
        # =========================
        # 1. 未保存修改保护
        # =========================

        if self.current_page_name == "本次调查":
            survey_page = getattr(
                self,
                "survey_page",
                None,
            )

            if survey_page is not None:
                if not survey_page.can_leave_page():
                    event.ignore()
                    return

        # =========================
        # 2. 正常退出前自动备份
        # =========================

        try:
            backup_path = create_database_backup(
                reason="exit",
            )

            if backup_path is not None:
                print("数据库退出备份：" f"{backup_path}")

        except Exception as error:
            QMessageBox.warning(
                self,
                "数据库备份失败",
                (
                    "程序退出前未能创建数据库备份。\n\n"
                    f"原因：{error}\n\n"
                    "正式数据库本身不会因此被删除，"
                    "但建议检查磁盘空间或备份目录。"
                ),
            )

        event.accept()

    def clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)

            if item is None:
                continue

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()


def main():
    # =========================
    # 启动前自动备份
    # =========================
    #
    # 如果数据库已经存在，并且自上次备份后
    # 有过修改，则先保存一份启动前快照。
    #
    # 首次运行数据库不存在时会自动跳过。

    try:
        backup_path = create_database_backup(
            reason="startup",
        )

        if backup_path is not None:
            print("数据库自动备份：" f"{backup_path}")

    except Exception as error:
        # 自动备份失败不能导致整个软件无法启动，
        # 但开发阶段必须在终端明确看到。
        print("数据库启动备份失败：" f"{error}")

    # =========================
    # 初始化正式运行所需数据库结构
    # =========================

    init_database()
    create_initial_forms()

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
