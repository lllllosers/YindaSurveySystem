import sys
from database import (
    create_demo_data,
    create_initial_forms,
    get_current_context,
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
)
from pages.basic_data_page import BasicDataPage
from pages.survey_page import SurveyPage
from pages.engineering_asset_page import EngineeringAssetPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_context = get_current_context()

        self.setWindowTitle("引大灌区调查数据采集系统")
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

        version_label = QLabel("V0.1 Demo")
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

        project_label = QLabel(f"当前项目：{project_name}")
        batch_label = QLabel(f"当前调查批次：{batch_name}")

        top_layout.addWidget(project_label)
        top_layout.addStretch()
        top_layout.addWidget(batch_label)

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
            "引大灌区调查数据采集系统\n\n"
            "V0.1 开发版本\n\n"
            "当前先完成程序框架，后续逐步接入调查批次、基础资料、"
            "工程调查、工程台账、查询和 Excel 导出。"
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

    def change_page(self, page_name):
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

        else:
            self.content_label = QLabel(
                f"{page_name}\n\n" "该模块将在后续开发步骤中逐步实现。"
            )

            self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.content_label.setWordWrap(True)
            self.content_label.setObjectName("contentLabel")

            self.content_layout.addWidget(self.content_label)

    def clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)

            if item is None:
                continue

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()


def main():
    # 确保数据库和开发测试数据存在
    init_database()
    create_demo_data()
    create_initial_forms()

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
