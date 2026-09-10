from PySide6.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pages.canal_page import CanalPage
from pages.organization_page import OrganizationPage


class BasicDataPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

        self.tabs.addTab(
            OrganizationPage(),
            "组织机构",
        )

        self.tabs.addTab(
            CanalPage(),
            "渠系",
        )

        layout.addWidget(self.tabs)