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

        self.sluice_list_page.edit_requested.connect(self.open_edit_sluice)

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

    def can_leave_page(self):
        """
        主程序准备离开“本次调查”模块时调用。

        如果当前正在编辑水闸调查，
        则先处理未保存修改。
        """

        if self.stack.currentWidget() is self.sluice_edit_page:
            return self.sluice_edit_page.confirm_leave_changes()

        return True

    def open_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def open_sluice_list(self):
        self.sluice_list_page.load_data()

        self.stack.setCurrentWidget(self.sluice_list_page)

    def open_new_sluice(self):
        self.sluice_edit_page.prepare_new()

        self.stack.setCurrentWidget(self.sluice_edit_page)

    def open_edit_sluice(
        self,
        survey_record_id,
    ):
        try:
            self.sluice_edit_page.load_record(survey_record_id)

            self.stack.setCurrentWidget(self.sluice_edit_page)

        except Exception as error:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "打开失败",
                str(error),
            )

    def sluice_saved(self):
        """
        调查记录保存后刷新列表数据，
        但不主动切换页面。
        """
        self.sluice_list_page.load_data()
