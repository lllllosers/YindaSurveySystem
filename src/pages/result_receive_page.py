from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import (
    get_current_context,
)
from pages.components.survey_result_receive_panel import (
    SurveyResultReceivePanel,
)
from services.survey_result_import_history import (
    list_survey_result_import_history,
)


class ResultReceivePage(QWidget):
    result_imported = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._history_items = ()

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        page_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(
            True
        )
        self.scroll_area.setFrameShape(
            QScrollArea.Shape.NoFrame
        )

        self.scroll_content = QWidget()
        self.scroll_area.setWidget(
            self.scroll_content
        )
        page_layout.addWidget(
            self.scroll_area
        )

        layout = QVBoxLayout(
            self.scroll_content
        )
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(16)

        description = QLabel(
            "接收下级调查端或管理单位提交的调查成果包。"
            "系统会先进行只读预检，确认无阻断性冲突后"
            "再允许正式导入；已接收成果按当前项目和调查批次统一汇总。"
        )
        description.setWordWrap(True)
        description.setObjectName(
            "pageDescription"
        )
        layout.addWidget(
            description
        )

        receive_group = QGroupBox(
            "一、接收新成果"
        )
        receive_group.setProperty(
            "workflowCard",
            True,
        )
        receive_layout = QVBoxLayout(
            receive_group
        )

        self.result_receive_panel = (
            SurveyResultReceivePanel()
        )
        self.result_receive_panel.result_imported.connect(
            self._handle_result_imported
        )

        receive_layout.addWidget(
            self.result_receive_panel
        )
        layout.addWidget(
            receive_group
        )

        history_group = QGroupBox(
            "二、已接收成果"
        )
        history_group.setProperty(
            "workflowCard",
            True,
        )
        history_layout = QVBoxLayout(
            history_group
        )
        history_layout.setSpacing(
            10
        )

        history_hint = QLabel(
            "仅显示当前项目和当前调查批次已正式导入的成果包。"
            "可按任务下发时的管理单位分类查看；默认按接收时间从新到旧排列。"
        )
        history_hint.setObjectName(
            "workflowLead"
        )
        history_hint.setWordWrap(
            True
        )
        history_layout.addWidget(
            history_hint
        )

        filter_row = QHBoxLayout()

        filter_label = QLabel(
            "管理单位："
        )
        self.history_office_combo = QComboBox()
        self.history_office_combo.setProperty(
            "uiWidthRole",
            "filter",
        )
        self.history_office_combo.currentIndexChanged.connect(
            self._render_history
        )

        self.history_refresh_button = QPushButton(
            "刷新"
        )
        self.history_refresh_button.setProperty(
            "uiRole",
            "secondary",
        )
        self.history_refresh_button.clicked.connect(
            self.refresh_history
        )

        filter_row.addWidget(
            filter_label
        )
        filter_row.addWidget(
            self.history_office_combo
        )
        filter_row.addStretch()
        filter_row.addWidget(
            self.history_refresh_button
        )

        history_layout.addLayout(
            filter_row
        )

        self.history_summary_label = QLabel(
            "尚未加载接收历史。"
        )
        self.history_summary_label.setObjectName(
            "workflowSummary"
        )
        self.history_summary_label.setWordWrap(
            True
        )
        history_layout.addWidget(
            self.history_summary_label
        )

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(
            8
        )
        self.history_table.setHorizontalHeaderLabels(
            [
                "接收时间",
                "管理单位",
                "成果名称",
                "调查记录",
                "工程对象",
                "分项评价",
                "影像",
                "接收状态",
            ]
        )
        self.history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.history_table.setAlternatingRowColors(
            True
        )
        self.history_table.setMinimumHeight(
            180
        )
        self.history_table.verticalHeader().setVisible(
            False
        )

        header = (
            self.history_table
            .horizontalHeader()
        )
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        header.setStretchLastSection(
            True
        )

        self.history_table.setColumnWidth(
            0,
            155,
        )
        self.history_table.setColumnWidth(
            1,
            180,
        )
        self.history_table.setColumnWidth(
            2,
            240,
        )
        self.history_table.setColumnWidth(
            3,
            90,
        )
        self.history_table.setColumnWidth(
            4,
            90,
        )
        self.history_table.setColumnWidth(
            5,
            90,
        )
        self.history_table.setColumnWidth(
            6,
            80,
        )

        history_layout.addWidget(
            self.history_table
        )

        layout.addWidget(
            history_group,
            1,
        )

        self.refresh_history()

    def _handle_result_imported(
        self,
        result,
    ):
        self.refresh_history()
        self.result_imported.emit(
            result
        )

    def _current_context_ids(self):
        context = (
            get_current_context()
        )

        if not context:
            return (
                None,
                None,
            )

        try:
            project_id = (
                context[
                    "project_id"
                ]
            )
            batch_id = (
                context[
                    "batch_id"
                ]
            )
        except (
            KeyError,
            IndexError,
            TypeError,
        ):
            return (
                None,
                None,
            )

        return (
            project_id,
            batch_id,
        )

    def refresh_history(self):
        project_id, batch_id = (
            self._current_context_ids()
        )

        if (
            project_id is None
            or batch_id is None
        ):
            self._history_items = ()
            self._rebuild_office_filter()
            self.history_table.setRowCount(
                0
            )
            self.history_summary_label.setText(
                "当前未选择项目或调查批次；"
                "仍可接收成果，选择项目/批次后可查看对应接收历史。"
            )
            return ()

        self._history_items = (
            list_survey_result_import_history(
                project_id=project_id,
                survey_batch_id=batch_id,
            )
        )

        self._rebuild_office_filter()
        self._render_history()

        return self._history_items

    def _rebuild_office_filter(self):
        previous = (
            self.history_office_combo
            .currentData()
        )

        options = {}

        for item in self._history_items:
            for (
                organization_uid,
                organization_name,
            ) in zip(
                item.organization_uids,
                item.organization_names,
            ):
                if (
                    organization_uid
                    and organization_name
                ):
                    options[
                        organization_uid
                    ] = (
                        organization_name
                    )

        self.history_office_combo.blockSignals(
            True
        )
        self.history_office_combo.clear()
        self.history_office_combo.addItem(
            "全部管理单位",
            None,
        )

        for (
            organization_uid,
            organization_name,
        ) in sorted(
            options.items(),
            key=lambda item: (
                item[1],
                item[0],
            ),
        ):
            self.history_office_combo.addItem(
                organization_name,
                organization_uid,
            )

        if previous is not None:
            index = (
                self.history_office_combo
                .findData(
                    previous
                )
            )

            if index >= 0:
                self.history_office_combo.setCurrentIndex(
                    index
                )

        self.history_office_combo.blockSignals(
            False
        )

    def _visible_history_items(self):
        organization_uid = (
            self.history_office_combo
            .currentData()
        )

        if organization_uid is None:
            return tuple(
                self._history_items
            )

        return tuple(
            item
            for item in self._history_items
            if organization_uid
            in item.organization_uids
        )

    @staticmethod
    def _organization_text(
        item,
    ):
        if item.organization_names:
            return "、".join(
                item.organization_names
            )

        if item.source_task_uids:
            return "任务来源未匹配"

        return "未关联任务"

    def _render_history(self):
        items = (
            self._visible_history_items()
        )

        self.history_table.setSortingEnabled(
            False
        )
        self.history_table.setRowCount(
            len(items)
        )

        for row_index, item in enumerate(
            items
        ):
            values = (
                item.imported_at,
                self._organization_text(
                    item
                ),
                item.result_name,
                str(
                    item.records_total
                ),
                str(
                    item.assets_total
                ),
                str(
                    item.inspections_total
                ),
                str(
                    item.media_total
                ),
                item.status_text,
            )

            for (
                column_index,
                value,
            ) in enumerate(
                values
            ):
                cell = QTableWidgetItem(
                    str(
                        value or ""
                    )
                )

                if column_index in (
                    3,
                    4,
                    5,
                    6,
                ):
                    cell.setTextAlignment(
                        int(
                            Qt.AlignmentFlag.AlignCenter
                        )
                    )

                self.history_table.setItem(
                    row_index,
                    column_index,
                    cell,
                )

        self.history_table.setSortingEnabled(
            True
        )
        self.history_table.sortItems(
            0,
            Qt.SortOrder.DescendingOrder,
        )

        all_count = len(
            self._history_items
        )
        visible_count = len(
            items
        )

        organization_uids = {
            uid
            for item in self._history_items
            for uid in item.organization_uids
        }

        if (
            self.history_office_combo
            .currentData()
            is None
        ):
            self.history_summary_label.setText(
                (
                    f"当前批次已接收 {all_count} 个成果包，"
                    f"来源管理单位 {len(organization_uids)} 个。"
                )
            )
        else:
            self.history_summary_label.setText(
                (
                    f"当前筛选显示 {visible_count} 个成果包；"
                    f"当前批次共已接收 {all_count} 个。"
                )
            )
