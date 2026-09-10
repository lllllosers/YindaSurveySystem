from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pages.sluice_gate_list_page import (
    SluiceGateListPage,
)

from pages.sluice_gate_page import (
    SluiceGatePage,
)


class SurveyPage(QWidget):
    def __init__(self):
        super().__init__()

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()

        # 本次调查首页
        self.home_page = self.create_home_page()

        # 水闸调查列表
        self.sluice_list_page = SluiceGateListPage()

        # 水闸录入页面
        self.sluice_edit_page = SluiceGatePage()

        self.stack.addWidget(self.home_page)

        self.stack.addWidget(self.sluice_list_page)

        self.stack.addWidget(self.sluice_edit_page)

        # 信号连接
        self.sluice_list_page.new_requested.connect(self.open_new_sluice)

        self.sluice_list_page.back_requested.connect(self.open_home)

        self.sluice_edit_page.back_requested.connect(self.open_sluice_list)

        self.sluice_edit_page.survey_saved.connect(self.sluice_saved)

        layout.addWidget(self.stack)

    def create_home_page(self):
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        title = QLabel("本次调查")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        layout.addWidget(title)

        description = QLabel("V0.1 当前优先实现附表2工程调查。")

        layout.addWidget(description)

        sluice_button = QPushButton("附表2.2 水闸工程状况调查")
        sluice_button.setMinimumHeight(46)

        sluice_button.clicked.connect(self.open_sluice_list)

        layout.addWidget(sluice_button)

        placeholder = QLabel("附表2.1及其他调查表将在后续逐步接入。")
        placeholder.setStyleSheet("color: #7a8793;")

        layout.addWidget(placeholder)

        layout.addStretch()

        return page

    def open_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def open_sluice_list(self):
        self.sluice_list_page.load_data()

        self.stack.setCurrentWidget(self.sluice_list_page)

    def open_new_sluice(self):
        self.sluice_edit_page.update_business_code()

        self.stack.setCurrentWidget(self.sluice_edit_page)

    def sluice_saved(self):
        self.sluice_list_page.load_data()

        self.stack.setCurrentWidget(self.sluice_list_page)
