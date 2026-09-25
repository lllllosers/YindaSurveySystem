from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pages.components.survey_task_receive_panel import (
    SurveyTaskReceivePanel,
)


class SurveyTaskReceivePage(QWidget):
    context_changed = Signal()

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
            "接收上级管理端分发的调查任务包。"
            "任务接收成功后，系统会切换到该任务对应的项目、"
            "调查批次和当前任务。"
        )
        description.setWordWrap(True)
        description.setObjectName(
            "pageDescription"
        )
        layout.addWidget(description)

        self.task_receive_panel = (
            SurveyTaskReceivePanel()
        )
        self.task_receive_panel.task_received.connect(
            self.context_changed.emit
        )

        layout.addWidget(
            self.task_receive_panel
        )
        layout.addStretch()
