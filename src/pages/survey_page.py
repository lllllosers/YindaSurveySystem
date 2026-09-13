from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pages.lined_channel_section_list_page import (
    LinedChannelSectionListPage,
)
from pages.lined_channel_section_page import (
    LinedChannelSectionPage,
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
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.stack = QStackedWidget()

        # =========================
        # 首页
        # =========================

        self.home_page = self.create_home_page()

        # =========================
        # 附表2.1
        # =========================

        self.lined_channel_list_page = LinedChannelSectionListPage()

        self.lined_channel_edit_page = LinedChannelSectionPage()

        # =========================
        # 附表2.2
        # =========================

        self.sluice_list_page = SluiceGateListPage()

        self.sluice_edit_page = SluiceGatePage()

        # =========================
        # Stack
        # =========================

        self.stack.addWidget(self.home_page)

        self.stack.addWidget(self.lined_channel_list_page)

        self.stack.addWidget(self.lined_channel_edit_page)

        self.stack.addWidget(self.sluice_list_page)

        self.stack.addWidget(self.sluice_edit_page)

        # =========================
        # 附表2.1信号
        # =========================

        self.lined_channel_list_page.new_requested.connect(self.open_new_lined_channel)

        self.lined_channel_list_page.back_requested.connect(self.open_home)

        self.lined_channel_list_page.edit_requested.connect(
            self.open_edit_lined_channel
        )

        self.lined_channel_edit_page.back_requested.connect(
            self.open_lined_channel_list
        )

        self.lined_channel_edit_page.survey_saved.connect(self.lined_channel_saved)

        # =========================
        # 附表2.2信号
        # =========================

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

        title = QLabel("调查录入")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        layout.addWidget(title)

        description = QLabel("工程设施现状调查与评价")

        layout.addWidget(description)

        # =========================
        # 附表2.1
        # =========================

        lined_channel_button = QPushButton("附表2.1 防渗衬砌渠道渠段工程状况调查")

        lined_channel_button.setMinimumHeight(46)

        lined_channel_button.clicked.connect(self.open_lined_channel_list)

        layout.addWidget(lined_channel_button)

        # =========================
        # 附表2.2
        # =========================

        sluice_button = QPushButton("附表2.2 水闸工程状况调查")

        sluice_button.setMinimumHeight(46)

        sluice_button.clicked.connect(self.open_sluice_list)

        layout.addWidget(sluice_button)

        placeholder = QLabel("附表2.3及其他调查表将在后续逐步接入。")

        placeholder.setStyleSheet("color: #7a8793;")

        layout.addWidget(placeholder)

        layout.addStretch()

        return page

    # =========================================================
    # 离开模块检查
    # =========================================================

    def can_leave_page(self):
        if self.stack.currentWidget() is self.lined_channel_edit_page:
            return self.lined_channel_edit_page.confirm_leave_changes()

        if self.stack.currentWidget() is self.sluice_edit_page:
            return self.sluice_edit_page.confirm_leave_changes()

        return True

    def open_home(self):
        self.stack.setCurrentWidget(self.home_page)

    # =========================================================
    # 附表2.1
    # =========================================================

    def open_lined_channel_list(self):
        self.lined_channel_list_page.load_data()

        self.stack.setCurrentWidget(self.lined_channel_list_page)

    def open_new_lined_channel(self):
        self.lined_channel_edit_page.prepare_new()

        self.stack.setCurrentWidget(self.lined_channel_edit_page)

    def open_edit_lined_channel(
        self,
        survey_record_id,
    ):
        try:
            (self.lined_channel_edit_page.load_record(survey_record_id))

            self.stack.setCurrentWidget(self.lined_channel_edit_page)

        except Exception as error:
            QMessageBox.warning(
                self,
                "打开失败",
                str(error),
            )

    def lined_channel_saved(self):
        self.lined_channel_list_page.load_data()

    # =========================================================
    # 附表2.2
    # =========================================================

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
            QMessageBox.warning(
                self,
                "打开失败",
                str(error),
            )

    def sluice_saved(self):
        self.sluice_list_page.load_data()
