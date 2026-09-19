from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pages.components.survey_result_receive_panel import (
    SurveyResultReceivePanel,
)


class ResultReceivePage(QWidget):
    result_imported = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(16)

        description = QLabel(
            "接收下级电脑或管理单位提交的调查成果包。"
            "系统会先进行只读预检，确认无阻断性冲突后"
            "再允许正式导入。"
        )
        description.setWordWrap(True)
        description.setObjectName(
            "pageDescription"
        )
        layout.addWidget(description)

        self.result_receive_panel = (
            SurveyResultReceivePanel()
        )
        self.result_receive_panel.result_imported.connect(
            self.result_imported.emit
        )

        layout.addWidget(
            self.result_receive_panel
        )
        layout.addStretch()
