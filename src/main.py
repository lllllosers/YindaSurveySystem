import sys
from database import (
    get_current_context,
    get_survey_readiness,
)
from PySide6.QtCore import (
    QLibraryInfo,
    QTranslator,
    Qt,
)
from PySide6.QtGui import QIcon
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
from pages.data_query_page import DataQueryPage
from pages.result_export_page import ResultExportPage
from pages.result_receive_page import ResultReceivePage
from pages.survey_page import SurveyPage
from pages.survey_task_page import SurveyTaskPage
from pages.survey_task_receive_page import SurveyTaskReceivePage
from pages.engineering_asset_page import EngineeringAssetPage
from pages.home_page import HomePage
from pages.project_batch_page import ProjectBatchPage
from services.application_bootstrap import (
    initialize_application_database,
)
from services.database_backup import (
    create_database_backup,
)
from services.runtime_paths import (
    get_resource_path,
)
from styles.app_theme import APP_QSS
from version import (
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

        app_title = QLabel("引大入秦工程")
        app_title.setObjectName("appTitle")
        sidebar_layout.addWidget(app_title)

        subtitle = QLabel("现状调查采集系统")
        subtitle.setObjectName("appSubtitle")
        sidebar_layout.addWidget(subtitle)

        sidebar_layout.addSpacing(20)

        self.nav_group_controls = {}

        def add_nav_button(
            name,
            *,
            parent_layout=sidebar_layout,
            child=False,
        ):
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setProperty(
                "navLevel",
                "child" if child else "top",
            )
            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )
            button.clicked.connect(
                lambda checked=False, page=name:
                self.change_page(page)
            )
            parent_layout.addWidget(button)
            return button

        def add_nav_group(
            title,
            child_pages,
        ):
            group_button = QPushButton(
                f"▸ {title}"
            )
            group_button.setObjectName(
                "navGroupButton"
            )
            group_button.setCheckable(True)
            group_button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )
            sidebar_layout.addWidget(
                group_button
            )

            child_container = QWidget()
            child_container.setObjectName(
                "navChildContainer"
            )
            child_layout = QVBoxLayout(
                child_container
            )
            child_layout.setContentsMargins(
                12,
                0,
                0,
                0,
            )
            child_layout.setSpacing(4)

            for child_page in child_pages:
                add_nav_button(
                    child_page,
                    parent_layout=child_layout,
                    child=True,
                )

            child_container.setVisible(False)
            sidebar_layout.addWidget(
                child_container
            )

            self.nav_group_controls[
                title
            ] = (
                group_button,
                child_container,
            )

            group_button.toggled.connect(
                lambda expanded, group=title:
                self._set_nav_group_expanded(
                    group,
                    expanded,
                )
            )

        add_nav_button("首页")
        add_nav_button("调查录入")
        add_nav_button("工程台账")
        add_nav_button("数据查询")

        add_nav_group(
            "任务管理",
            (
                "任务分发",
                "任务接收",
            ),
        )

        add_nav_group(
            "成果管理",
            (
                "成果提交",
                "成果接收",
            ),
        )

        add_nav_button("基础资料")
        add_nav_button("项目/批次")

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

        self.home_page = HomePage()
        self.home_page.navigate_requested.connect(
            self.change_page
        )

        self.content_layout.addWidget(
            self.home_page
        )

        workspace_layout.addWidget(content, 1)

        root_layout.addWidget(workspace, 1)


    def _set_nav_group_expanded(
        self,
        group_name,
        expanded,
    ):
        """
        左侧二级导航采用手风琴式展开。
        同一时间最多展开一个业务分组。
        """

        current = self.nav_group_controls.get(
            group_name
        )

        if current is None:
            return

        button, container = current

        container.setVisible(
            bool(expanded)
        )
        button.setText(
            (
                "▾ "
                if expanded
                else "▸ "
            )
            + str(group_name)
        )

        if not expanded:
            return

        for (
            other_name,
            (
                other_button,
                other_container,
            ),
        ) in self.nav_group_controls.items():
            if other_name == group_name:
                continue

            other_container.setVisible(
                False
            )

            if other_button.isChecked():
                other_button.blockSignals(True)
                other_button.setChecked(False)
                other_button.blockSignals(False)

            other_button.setText(
                f"▸ {other_name}"
            )

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

        readiness = get_survey_readiness()

        if readiness["ready"]:
            return True

        missing_items = "\n".join(f"• {item}" for item in readiness["missing"])

        QMessageBox.information(
            self,
            "基础资料尚未完善",
            (
                "开始调查前还需要完成"
                "以下基础配置：\n\n"
                f"{missing_items}\n\n"
                "请进入“项目/批次”或"
                "“基础资料”完成配置后，"
                "再进入调查录入。"
            ),
        )

        return False

    def change_page(self, page_name):

        # 页面切换前重新读取数据库中的当前上下文。
        # 任务接收、项目切换等操作可能已经改变 active 状态，
        # MainWindow 不能依赖启动时缓存。
        self.refresh_current_context()

        # 已经在当前模块时不重复销毁和创建页面。
        if page_name == self.current_page_name:
            return

        # =========================
        # 正式运行环境完整性检查
        # =========================

        if page_name in (
            "调查录入",
            "工程台账",
            "任务分发",
            "成果提交",
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

        if page_name == "调查录入":
            if not self.can_start_survey():
                return

        # 如果正在“调查录入”中编辑表单，
        # 离开主模块前先检查未保存修改。
        if self.current_page_name == "调查录入":
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

        if page_name == "首页":
            self.home_page = HomePage()
            self.home_page.navigate_requested.connect(
                self.change_page
            )

            self.content_layout.addWidget(
                self.home_page
            )

        elif page_name == "调查录入":
            self.survey_page = SurveyPage()

            self.content_layout.addWidget(self.survey_page)


        elif page_name == "任务分发":


            self.survey_task_page = SurveyTaskPage()

            self.survey_task_page.context_changed.connect(
                self.refresh_current_context
            )



            self.content_layout.addWidget(


                self.survey_task_page


            )


        elif page_name == "任务接收":
            self.survey_task_receive_page = (
                SurveyTaskReceivePage()
            )

            self.survey_task_receive_page.context_changed.connect(
                self.refresh_current_context
            )

            self.content_layout.addWidget(
                self.survey_task_receive_page
            )

        elif page_name == "工程台账":
            self.engineering_asset_page = EngineeringAssetPage()

            self.engineering_asset_page.open_survey_record_requested.connect(
                self.open_survey_record
            )

            self.content_layout.addWidget(self.engineering_asset_page)

        elif page_name == "数据查询":
            self.data_query_page = DataQueryPage()

            self.data_query_page.open_survey_record_requested.connect(
                self.open_survey_record
            )

            self.content_layout.addWidget(self.data_query_page)

        elif page_name == "成果提交":
            self.result_export_page = ResultExportPage()

            self.content_layout.addWidget(
                self.result_export_page
            )

        elif page_name == "成果接收":
            self.result_receive_page = (
                ResultReceivePage()
            )

            self.content_layout.addWidget(
                self.result_receive_page
            )

        elif page_name == "基础资料":
            self.basic_data_page = BasicDataPage()

            self.content_layout.addWidget(self.basic_data_page)

        elif page_name == "项目/批次":
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

    def open_survey_record(
        self,
        form_code,
        survey_record_id,
    ):
        """
        从工程台账、工程详情或数据查询
        直接打开完整工程调查表。
        """

        return_page_name = (
            self.current_page_name
            if self.current_page_name
            in (
                "工程台账",
                "数据查询",
            )
            else None
        )

        if self.current_page_name == "调查录入":
            survey_page = getattr(
                self,
                "survey_page",
                None,
            )

            if (
                survey_page is not None
                and not survey_page.can_leave_page()
            ):
                return

        self.refresh_current_context()

        self.page_title.setText("调查录入")
        self.clear_content()

        self.survey_page = SurveyPage()
        self.survey_page.return_to_module_requested.connect(
            self.change_page
        )
        self.content_layout.addWidget(
            self.survey_page
        )

        if (
            form_code
            not in self.survey_page.engineering_pages
        ):
            QMessageBox.warning(
                self,
                "无法打开调查表",
                "当前记录对应的调查表尚未接入本版本。",
            )
            self.current_page_name = "调查录入"
            return

        self.survey_page.open_engineering_edit(
            str(form_code),
            int(survey_record_id),
            return_page_name=return_page_name,
        )

        self.current_page_name = "调查录入"

    def closeEvent(self, event):
        # =========================
        # 1. 未保存修改保护
        # =========================

        if self.current_page_name == "调查录入":
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

    bootstrap_result = (
        initialize_application_database()
    )

    master_data_result = (
        bootstrap_result[
            "official_master_data"
        ]
    )

    if master_data_result.get(
        "applied"
    ):
        print(
            "正式基础资料已自动初始化："
            "组织机构 25 个，"
            "渠系节点 68 个。"
        )

    app = QApplication(sys.argv)

    app.setStyleSheet(APP_QSS)

    icon_path = get_resource_path(
        "assets",
        "app_icon.ico",
    )

    if icon_path.exists():
        app.setWindowIcon(
            QIcon(str(icon_path))
        )

    # =========================
    # Qt 标准界面中文化
    # =========================
    #
    # QMessageBox、QDialogButtonBox 等 Qt 标准控件
    # 默认按钮文字可能受操作系统语言影响，
    # 例如 Save / Discard / Cancel / Yes / No。
    #
    # 本系统界面统一使用简体中文，
    # 因此主动加载 Qt 官方简体中文翻译。
    #
    qt_translator = QTranslator(app)

    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)

    if qt_translator.load(
        "qtbase_zh_CN",
        translations_path,
    ):
        app.installTranslator(qt_translator)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
