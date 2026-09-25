from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import (
    Signal,
    Qt,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QLayout,
)

from database import (
    get_canal_lineage,
    get_current_context,
    get_departments,
    get_water_offices,
)
from services.canal_management_scope import (
    get_management_scopes_for_organization,
)
from services.master_data_integrity import (
    check_master_data_integrity,
)
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)
from services.survey_child_task_package import (
    ChildSurveyTaskExportRequest,
    export_child_survey_task_package,
)
from services.survey_task_workspace import (
    get_current_task_workspace,
)
from services.survey_task_package_reader import (
    inspect_survey_task_package,
)
from services.survey_task_tracking import (
    list_survey_task_tracking,
)


_INVALID_FILENAME_CHARS = re.compile(
    r'[<>:"/\\|?*\x00-\x1f]'
)


_CANAL_LEVEL_NAMES = {
    "01": "干渠",
    "02": "分干渠",
    "03": "支渠",
    "04": "分支渠",
}

def _format_scope_range(scope):
    mode = str(scope.get("range_mode") or "")
    if mode == "whole":
        return "全渠"
    if mode == "segment_unknown":
        return "边界未知"
    start = scope.get("start_stake_text") or scope.get("start_stake_value") or "?"
    end = scope.get("end_stake_text") or scope.get("end_stake_value") or "?"
    return f"{start}～{end}"


def _safe_filename(value):
    value = str(
        value or ""
    ).strip()

    value = (
        _INVALID_FILENAME_CHARS
        .sub("_", value)
        .strip(" .")
    )

    return value or "调查任务"


class SurveyTaskPage(QWidget):
    """
    调查任务包页面。

    第一版任务包服务于当前纸质外业工作流：
    - 任务包描述“谁调查哪些渠系”；
    - 携带必要组织、渠系和表单参考信息；
    - 不创建 EngineeringAsset；
    - 不创建 SurveyRecord；
    - 不包含调查结果和影像。
    """

    context_changed = Signal()

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.current_context = None
        self._task_history_items = ()
        self._distribution_mode = "center"
        self._parent_workspace = None

        self._init_ui()
        self._connect_signals()
        self.reload_context()

    # =========================================================
    # UI
    # =========================================================

    def _init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(
            0, 0, 0, 0
        )
        page_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(
            True
        )

        self.scroll_content = QWidget()
        self.scroll_area.setWidget(
            self.scroll_content
        )
        page_layout.addWidget(
            self.scroll_area
        )

        root = QVBoxLayout(
            self.scroll_content
        )

        root.setSizeConstraint(
            QLayout.SizeConstraint.SetMinimumSize
        )
        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root.setSpacing(16)

        intro = QLabel(
            "任务分发用于为指定管理单位生成调查任务包（.ydtask）。"
            "请选择管理单位和本次调查分管范围后生成任务包，"
            "交由执行调查的电脑或管理单位接收。"
        )
        intro.setObjectName("workflowLead")
        intro.setWordWrap(True)
        intro.setStyleSheet(
            "color: #607080;"
        )
        root.addWidget(intro)

        context_group = QGroupBox(
            "一、当前项目与调查批次"
        )
        context_group.setProperty("workflowCard", True)
        context_layout = QFormLayout(
            context_group
        )
        context_layout.setHorizontalSpacing(18)
        context_layout.setVerticalSpacing(10)

        self.project_label = QLabel(
            "未加载"
        )
        self.batch_label = QLabel(
            "未加载"
        )

        context_layout.addRow(
            "当前项目：",
            self.project_label,
        )
        context_layout.addRow(
            "当前调查批次：",
            self.batch_label,
        )

        root.addWidget(context_group)

        assignment_group = QGroupBox(
            "二、任务分配"
        )
        assignment_group.setProperty("workflowCard", True)
        assignment_layout = QFormLayout(
            assignment_group
        )
        assignment_layout.setHorizontalSpacing(18)
        assignment_layout.setVerticalSpacing(10)

        self.department_combo = (
            QComboBox()
        )
        self.department_combo.setProperty("uiWidthRole", "form")
        self.office_combo = QComboBox()
        self.office_combo.setProperty("uiWidthRole", "form")
        self.task_name_edit = (
            QLineEdit()
        )
        self.task_name_edit.setProperty("uiWidthRole", "form")
        self.notes_edit = (
            QLineEdit()
        )
        self.notes_edit.setProperty("uiWidthRole", "form")
        self.notes_edit.setPlaceholderText(
            "可选：简要填写任务说明或交接备注"
        )

        assignment_layout.addRow(
            "所属基层处：",
            self.department_combo,
        )
        assignment_layout.addRow(
            "管理单位：",
            self.office_combo,
        )
        assignment_layout.addRow(
            "任务名称：",
            self.task_name_edit,
        )
        assignment_layout.addRow(
            "任务备注：",
            self.notes_edit,
        )

        root.addWidget(
            assignment_group
        )

        scope_group = QGroupBox(
            "三、调查分管范围"
        )
        scope_group.setProperty("workflowCard", True)
        scope_layout = QVBoxLayout(
            scope_group
        )

        scope_hint = QLabel(
            "选择管理单位后，系统自动列出该单位当前启用的分管范围，"
            "并默认全部勾选。相关渠道信息会一并写入任务包，接收端无需重复配置。"
        )
        scope_hint.setWordWrap(True)
        scope_hint.setStyleSheet(
            "color: #607080;"
        )
        scope_layout.addWidget(
            scope_hint
        )

        scope_button_layout = (
            QHBoxLayout()
        )

        self.select_all_button = (
            QPushButton("全选")
        )
        self.clear_all_button = (
            QPushButton("全部取消")
        )
        self.scope_count_label = QLabel(
            "已选择 0 条"
        )
        self.scope_count_label.setObjectName("workflowSummary")

        scope_button_layout.addWidget(
            self.select_all_button
        )
        scope_button_layout.addWidget(
            self.clear_all_button
        )
        scope_button_layout.addStretch()
        scope_button_layout.addWidget(
            self.scope_count_label
        )

        scope_layout.addLayout(
            scope_button_layout
        )

        self.canal_tree = (
            QTreeWidget()
        )
        self.canal_tree.setColumnCount(
            6
        )
        self.canal_tree.setHeaderLabels(
            [
                "选择",
                "渠道名称",
                "类型",
                "管理范围",
                "上级渠道",
                "备注",
            ]
        )
        self.canal_tree.setMinimumHeight(
            220
        )
        self.canal_tree.setRootIsDecorated(
            False
        )
        self.canal_tree.setAlternatingRowColors(
            True
        )
        self.canal_tree.setColumnWidth(
            0,
            70,
        )
        self.canal_tree.setColumnWidth(
            1,
            220,
        )
        self.canal_tree.setColumnWidth(
            2,
            220,
        )
        self.canal_tree.setColumnWidth(
            3,
            100,
        )
        self.canal_tree.setColumnWidth(
            4,
            110,
        )
        self.canal_tree.setColumnWidth(
            5,
            300,
        )

        scope_layout.addWidget(
            self.canal_tree,
            1,
        )

        root.addWidget(
            scope_group,
            1,
        )

        action_layout = QHBoxLayout()

        self.inspect_button = QPushButton(
            "检查任务包"
        )
        self.inspect_button.setProperty("uiRole", "secondary")
        self.export_button = QPushButton(
            "生成任务包"
        )
        self.export_button.setProperty("uiRole", "primary")
        self.export_button.setMinimumWidth(
            150
        )

        action_layout.addWidget(
            self.inspect_button
        )
        action_layout.addStretch()
        action_layout.addWidget(
            self.export_button
        )

        root.addLayout(action_layout)

        history_group = QGroupBox(
            "四、已分发任务"
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
            "显示当前项目和调查批次已经生成的调查任务。"
            "“已有成果返回”只表示该任务已有调查记录回到总库，"
            "不等同于该任务已经全部完成。"
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

        history_filter_row = QHBoxLayout()

        history_filter_label = QLabel(
            "管理单位："
        )
        self.task_history_office_combo = (
            QComboBox()
        )
        self.task_history_office_combo.setProperty(
            "uiWidthRole",
            "filter",
        )

        self.task_history_refresh_button = (
            QPushButton(
                "刷新"
            )
        )
        self.task_history_refresh_button.setProperty(
            "uiRole",
            "secondary",
        )

        history_filter_row.addWidget(
            history_filter_label
        )
        history_filter_row.addWidget(
            self.task_history_office_combo
        )
        history_filter_row.addStretch()
        history_filter_row.addWidget(
            self.task_history_refresh_button
        )

        history_layout.addLayout(
            history_filter_row
        )

        self.task_history_summary_label = QLabel(
            "尚未加载任务分发历史。"
        )
        self.task_history_summary_label.setObjectName(
            "workflowSummary"
        )
        self.task_history_summary_label.setWordWrap(
            True
        )
        history_layout.addWidget(
            self.task_history_summary_label
        )

        self.task_history_table = QTableWidget()
        self.task_history_table.setColumnCount(
            7
        )
        self.task_history_table.setHorizontalHeaderLabels(
            [
                "分发时间",
                "基层处",
                "管理单位",
                "任务名称",
                "分管范围",
                "已回收记录",
                "回收状态",
            ]
        )
        self.task_history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.task_history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.task_history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.task_history_table.setAlternatingRowColors(
            True
        )
        self.task_history_table.setMinimumHeight(
            180
        )
        self.task_history_table.verticalHeader().setVisible(
            False
        )

        history_header = (
            self.task_history_table
            .horizontalHeader()
        )
        history_header.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        history_header.setStretchLastSection(
            True
        )

        self.task_history_table.setColumnWidth(
            0,
            155,
        )
        self.task_history_table.setColumnWidth(
            1,
            150,
        )
        self.task_history_table.setColumnWidth(
            2,
            180,
        )
        self.task_history_table.setColumnWidth(
            3,
            240,
        )
        self.task_history_table.setColumnWidth(
            4,
            90,
        )
        self.task_history_table.setColumnWidth(
            5,
            100,
        )

        history_layout.addWidget(
            self.task_history_table
        )

        root.addWidget(
            history_group
        )

        self.task_history_office_combo.currentIndexChanged.connect(
            self._render_task_history
        )
        self.task_history_refresh_button.clicked.connect(
            self.refresh_task_history
        )


    def refresh_task_history(
        self,
    ):
        context = (
            self.current_context
        )

        if (
            not context
            or context.get(
                "project_id"
            )
            is None
            or context.get(
                "batch_id"
            )
            is None
        ):
            self._task_history_items = ()
            self._rebuild_task_history_office_filter()
            self.task_history_table.setRowCount(
                0
            )
            self.task_history_summary_label.setText(
                "当前未选择项目或调查批次。"
            )
            return ()

        self._task_history_items = (
            list_survey_task_tracking(
                project_id=int(
                    context[
                        "project_id"
                    ]
                ),
                survey_batch_id=int(
                    context[
                        "batch_id"
                    ]
                ),
            )
        )

        self._rebuild_task_history_office_filter()
        self._render_task_history()

        return self._task_history_items

    def _rebuild_task_history_office_filter(
        self,
    ):
        previous = (
            self.task_history_office_combo
            .currentData()
        )

        options = {
            item.organization_uid:
                item.organization_name
            for item in self._task_history_items
            if (
                item.organization_uid
                and item.organization_name
            )
        }

        self.task_history_office_combo.blockSignals(
            True
        )
        self.task_history_office_combo.clear()
        self.task_history_office_combo.addItem(
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
            self.task_history_office_combo.addItem(
                organization_name,
                organization_uid,
            )

        if previous is not None:
            index = (
                self.task_history_office_combo
                .findData(
                    previous
                )
            )

            if index >= 0:
                self.task_history_office_combo.setCurrentIndex(
                    index
                )

        self.task_history_office_combo.blockSignals(
            False
        )

    def _visible_task_history_items(
        self,
    ):
        organization_uid = (
            self.task_history_office_combo
            .currentData()
        )

        if organization_uid is None:
            return tuple(
                self._task_history_items
            )

        return tuple(
            item
            for item in self._task_history_items
            if (
                item.organization_uid
                == organization_uid
            )
        )

    def _render_task_history(
        self,
    ):
        items = (
            self._visible_task_history_items()
        )

        self.task_history_table.setSortingEnabled(
            False
        )
        self.task_history_table.setRowCount(
            len(items)
        )

        for row_index, item in enumerate(
            items
        ):
            values = (
                item.issued_at,
                item.department_name,
                item.organization_name,
                item.task_name,
                str(
                    item.selected_scope_count
                ),
                str(
                    item.returned_record_count
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
                    4,
                    5,
                    6,
                ):
                    cell.setTextAlignment(
                        int(
                            Qt.AlignmentFlag.AlignCenter
                        )
                    )

                self.task_history_table.setItem(
                    row_index,
                    column_index,
                    cell,
                )

        self.task_history_table.setSortingEnabled(
            True
        )
        self.task_history_table.sortItems(
            0,
            Qt.SortOrder.DescendingOrder,
        )

        all_count = len(
            self._task_history_items
        )
        visible_count = len(
            items
        )
        returned_count = sum(
            1
            for item in self._task_history_items
            if item.returned_record_count > 0
        )

        if (
            self.task_history_office_combo
            .currentData()
            is None
        ):
            if all_count:
                self.task_history_summary_label.setText(
                    (
                        f"当前调查批次已分发 {all_count} 个任务，"
                        f"其中 {returned_count} 个已有成果返回。"
                    )
                )
            else:
                self.task_history_summary_label.setText(
                    "当前调查批次尚未生成调查任务包。"
                )
        else:
            self.task_history_summary_label.setText(
                (
                    f"当前筛选显示 {visible_count} 个任务；"
                    f"当前调查批次共已分发 {all_count} 个。"
                )
            )

    def _connect_signals(self):
        self.department_combo.currentIndexChanged.connect(
            self._department_changed
        )
        self.office_combo.currentIndexChanged.connect(
            self._office_changed
        )
        self.select_all_button.clicked.connect(
            lambda:
            self._set_all_checked(
                True
            )
        )
        self.clear_all_button.clicked.connect(
            lambda:
            self._set_all_checked(
                False
            )
        )
        self.canal_tree.itemChanged.connect(
            self._update_scope_count
        )
        self.export_button.clicked.connect(
            self.export_task_package
        )
        self.inspect_button.clicked.connect(
            self.inspect_existing_package
        )

    # =========================================================
    # 当前上下文
    # =========================================================

    def reload_context(self):
        self.current_context = (
            get_current_context()
        )

        self._parent_workspace = (
            get_current_task_workspace()
        )

        if self._parent_workspace is None:
            self._distribution_mode = "center"
        else:
            target_unit_type = str(
                self._parent_workspace.get(
                    "target_unit_type"
                )
                or "water_office"
            ).strip()

            if (
                target_unit_type
                == "department"
            ):
                self._distribution_mode = (
                    "department"
                )
            else:
                self._distribution_mode = (
                    "office"
                )

        if not self.current_context:
            self.project_label.setText(
                "未选择项目"
            )
            self.batch_label.setText(
                "未选择调查批次"
            )
            self._set_operational_enabled(
                False
            )
            self.refresh_task_history()
            return

        project_name = (
            self.current_context.get(
                "project_name"
            )
            or "未选择项目"
        )
        batch_name = (
            self.current_context.get(
                "batch_name"
            )
            or "未选择调查批次"
        )

        self.project_label.setText(
            project_name
        )
        self.batch_label.setText(
            batch_name
        )

        has_context = (
            self.current_context.get(
                "project_id"
            )
            is not None
            and self.current_context.get(
                "batch_id"
            )
            is not None
        )

        operational = (
            has_context
            and self._distribution_mode
            != "office"
        )

        self._set_operational_enabled(
            operational
        )

        if (
            self._distribution_mode
            == "office"
        ):
            self.task_name_edit.setText(
                "当前为水管所执行任务，不能继续向下分发"
            )
            self._clear_scope()

        elif has_context:
            self._load_departments()

        self.refresh_task_history()

    def _set_operational_enabled(
        self,
        enabled,
    ):
        self.department_combo.setEnabled(
            enabled
        )
        self.office_combo.setEnabled(
            enabled
        )
        self.task_name_edit.setEnabled(
            enabled
        )
        self.notes_edit.setEnabled(
            enabled
        )
        self.canal_tree.setEnabled(
            enabled
        )
        self.select_all_button.setEnabled(
            enabled
        )
        self.clear_all_button.setEnabled(
            enabled
        )
        self.export_button.setEnabled(
            enabled
        )

    def _load_departments(self):
        self.department_combo.blockSignals(True)
        self.department_combo.clear()

        if (
            self._distribution_mode == "department"
            and self._parent_workspace is not None
        ):
            self.department_combo.addItem(
                (
                    self._parent_workspace.get(
                        "organization_name"
                    )
                    or "当前基层处"
                ),
                {
                    "id": int(
                        self._parent_workspace[
                            "organization_unit_id"
                        ]
                    ),
                    "name": (
                        self._parent_workspace.get(
                            "organization_name"
                        )
                        or "当前基层处"
                    ),
                },
            )
            self.department_combo.setEnabled(False)

        elif self._distribution_mode == "center":
            self.department_combo.setEnabled(True)

            departments = [
                row
                for row in get_departments()
                if row["status"] == "active"
            ]

            departments.sort(
                key=lambda row: (
                    int(row["sort_order"] or 0)
                    or (1000000 + int(row["id"])),
                    int(row["id"]),
                )
            )

            for department in departments:
                self.department_combo.addItem(
                    department["name"],
                    {
                        "id": int(department["id"]),
                        "name": department["name"],
                    },
                )

        else:
            self.department_combo.setEnabled(False)

        self.department_combo.blockSignals(False)
        self._department_changed()

    def _department_changed(self):
        self.office_combo.blockSignals(True)
        self.office_combo.clear()

        department = (
            self.department_combo
            .currentData()
        )

        if not department:
            self.office_combo.blockSignals(False)
            self._clear_scope()
            return

        # database.get_water_offices() returns sqlite3.Row.
        # Department mode needs mapping-style .get() below, so normalize
        # rows once before entering UI/authorization logic.
        offices = [
            dict(row)
            for row in get_water_offices(
                department["id"]
            )
            if row["status"] == "active"
        ]

        offices.sort(
            key=lambda row: (
                int(
                    row["sort_order"]
                    or 0
                )
                or (
                    1000000
                    + int(
                        row["id"]
                    )
                ),
                int(
                    row["id"]
                ),
            )
        )

        if (
            self._distribution_mode
            == "center"
        ):
            # 保留既有两级流程的默认行为：
            # 中心端进入页面后，默认仍选中第一个水管所，
            # 这样旧 UI / 旧测试 / 老用户操作习惯都不变。
            #
            # “整个基层处”作为新增三级分发入口放在水管所之后，
            # 不抢占默认选中项。
            for office in offices:
                self.office_combo.addItem(
                    office["name"],
                    {
                        "id": int(
                            office["id"]
                        ),
                        "name": (
                            office["name"]
                        ),
                        "target_unit_type": (
                            "water_office"
                        ),
                    },
                )

            self.office_combo.addItem(
                (
                    f"{department['name']}"
                    "（整个基层处）"
                ),
                {
                    "id": int(
                        department["id"]
                    ),
                    "name": (
                        department["name"]
                    ),
                    "target_unit_type": (
                        "department"
                    ),
                },
            )

        elif (
            self._distribution_mode
            == "department"
        ):
            allowed_owner_uids = {
                str(
                    item.get(
                        "organization_unit_uid"
                    )
                    or ""
                ).strip()
                for item in (
                    self._parent_workspace.get(
                        "management_scopes"
                    )
                    or ()
                )
            }

            for office in offices:
                office_uid = str(
                    office.get(
                        "organization_unit_uid"
                    )
                    or ""
                ).strip()

                if (
                    not office_uid
                    or office_uid
                    not in allowed_owner_uids
                ):
                    continue

                self.office_combo.addItem(
                    office["name"],
                    {
                        "id": int(
                            office["id"]
                        ),
                        "name": (
                            office["name"]
                        ),
                        "target_unit_type": (
                            "water_office"
                        ),
                        "organization_unit_uid": (
                            office_uid
                        ),
                    },
                )

        self.office_combo.blockSignals(False)

        self._office_changed()

    def _office_changed(self):
        target = self.office_combo.currentData()

        if not target:
            self.task_name_edit.clear()
            self._clear_scope()
            return

        if self._distribution_mode == "department":
            self.task_name_edit.setText(
                f"{target['name']}调查任务"
            )
            self._load_parent_workspace_scopes(
                target["organization_unit_uid"]
            )
            return

        if (
            target.get("target_unit_type")
            == "department"
        ):
            self.task_name_edit.setText(
                f"{target['name']}处级调查任务"
            )
            self._load_department_scopes(
                target["id"]
            )
            return

        self.task_name_edit.setText(
            f"{target['name']}调查任务"
        )
        self._load_office_scopes(
            target["id"]
        )

    def _clear_scope(self):
        self.canal_tree.blockSignals(
            True
        )
        self.canal_tree.clear()
        self.canal_tree.blockSignals(
            False
        )
        self._update_scope_count()

    def _load_department_scopes(
        self,
        department_id,
    ):
        self.canal_tree.blockSignals(True)
        self.canal_tree.clear()

        offices = [
            row
            for row in get_water_offices(
                int(department_id)
            )
            if row["status"] == "active"
        ]

        offices.sort(
            key=lambda row: (
                int(row["sort_order"] or 0)
                or (1000000 + int(row["id"])),
                int(row["id"]),
            )
        )

        for office in offices:
            scopes = list(
                get_management_scopes_for_organization(
                    int(office["id"])
                )
            )

            scopes.sort(
                key=lambda row: (
                    int(
                        row.get(
                            "canal_sort_order"
                        )
                        or 0
                    )
                    or (
                        1000000
                        + int(
                            row[
                                "canal_unit_id"
                            ]
                        )
                    ),
                    int(
                        row.get(
                            "sort_order"
                        )
                        or 0
                    ),
                    int(row["id"]),
                )
            )

            for scope in scopes:
                item = QTreeWidgetItem()
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {
                        "management_scope_uid": (
                            scope[
                                "management_scope_uid"
                            ]
                        ),
                        "canal_unit_id": int(
                            scope[
                                "canal_unit_id"
                            ]
                        ),
                    },
                )
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(
                    0,
                    Qt.CheckState.Checked,
                )

                canal_id = int(
                    scope[
                        "canal_unit_id"
                    ]
                )
                parent_name = ""

                lineage = get_canal_lineage(
                    canal_id
                )
                if len(lineage) >= 2:
                    parent_name = str(
                        lineage[-2]["name"]
                        or ""
                    )

                mode = str(
                    scope["range_mode"]
                    or ""
                )

                item.setText(
                    1,
                    str(
                        scope["canal_name"]
                        or ""
                    ),
                )
                item.setText(
                    2,
                    (
                        "全渠"
                        if mode == "whole"
                        else "分管段"
                    ),
                )
                item.setText(
                    3,
                    _format_scope_range(
                        scope
                    ),
                )
                item.setText(
                    4,
                    parent_name,
                )

                description = str(
                    scope["description"]
                    or ""
                ).strip()

                owner_text = str(
                    office["name"]
                    or ""
                )

                if description:
                    owner_text += (
                        " | "
                        + description
                    )

                item.setText(
                    5,
                    owner_text,
                )

                self.canal_tree.addTopLevelItem(
                    item
                )

        self.canal_tree.blockSignals(False)
        self._update_scope_count()

    def _load_parent_workspace_scopes(
        self,
        office_uid,
    ):
        self.canal_tree.blockSignals(True)
        self.canal_tree.clear()

        office_uid = str(
            office_uid or ""
        ).strip()

        scopes = [
            dict(item)
            for item in (
                self._parent_workspace.get(
                    "management_scopes"
                )
                or ()
            )
            if str(
                item.get(
                    "organization_unit_uid"
                )
                or ""
            ).strip()
            == office_uid
        ]

        scopes.sort(
            key=lambda row: (
                int(
                    row.get(
                        "sort_order"
                    )
                    or 0
                ),
                str(
                    row.get(
                        "management_scope_uid"
                    )
                    or ""
                ),
            )
        )

        for scope in scopes:
            item = QTreeWidgetItem()

            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "management_scope_uid": (
                        scope[
                            "management_scope_uid"
                        ]
                    ),
                    "canal_unit_id": int(
                        scope[
                            "canal_unit_id"
                        ]
                    ),
                },
            )

            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                0,
                Qt.CheckState.Checked,
            )

            canal_name = str(
                scope.get(
                    "canal_name"
                )
                or scope.get(
                    "canal_name_snapshot"
                )
                or ""
            )

            mode = str(
                scope.get(
                    "range_mode"
                )
                or ""
            )

            item.setText(
                1,
                canal_name,
            )
            item.setText(
                2,
                (
                    "全渠"
                    if mode == "whole"
                    else "分管段"
                ),
            )
            item.setText(
                3,
                _format_scope_range(
                    scope
                ),
            )

            parent_name = ""

            try:
                lineage = get_canal_lineage(
                    int(
                        scope[
                            "canal_unit_id"
                        ]
                    )
                )
                if len(lineage) >= 2:
                    parent_name = str(
                        lineage[-2]["name"]
                        or ""
                    )
            except Exception:
                parent_name = ""

            item.setText(
                4,
                parent_name,
            )
            item.setText(
                5,
                str(
                    scope.get(
                        "description"
                    )
                    or ""
                ),
            )

            self.canal_tree.addTopLevelItem(
                item
            )

        self.canal_tree.blockSignals(False)
        self._update_scope_count()

    def _load_office_scopes(self, office_id):
        self.canal_tree.blockSignals(True)
        self.canal_tree.clear()

        scopes = list(get_management_scopes_for_organization(office_id))
        scopes.sort(
            key=lambda row: (
                int(row.get("canal_sort_order") or 0)
                or (1000000 + int(row["canal_unit_id"])),
                int(row.get("sort_order") or 0),
                int(row["id"]),
            )
        )

        for scope in scopes:
            item = QTreeWidgetItem()
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "management_scope_uid": scope["management_scope_uid"],
                    "canal_unit_id": int(scope["canal_unit_id"]),
                },
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)

            canal_id = int(scope["canal_unit_id"])
            parent_name = ""
            lineage = get_canal_lineage(canal_id)
            if len(lineage) >= 2:
                parent_name = str(lineage[-2]["name"] or "")

            mode = str(scope["range_mode"] or "")
            item.setText(1, str(scope["canal_name"] or ""))
            item.setText(2, "全渠" if mode == "whole" else "分管段")
            item.setText(3, _format_scope_range(scope))
            item.setText(4, parent_name)
            item.setText(5, str(scope["description"] or ""))
            self.canal_tree.addTopLevelItem(item)

        self.canal_tree.blockSignals(False)
        self._update_scope_count()

    def _set_all_checked(
        self,
        checked,
    ):
        state = (
            Qt.CheckState.Checked
            if checked
            else Qt.CheckState.Unchecked
        )

        self.canal_tree.blockSignals(
            True
        )

        for index in range(
            self.canal_tree.topLevelItemCount()
        ):
            item = (
                self.canal_tree
                .topLevelItem(index)
            )
            item.setCheckState(
                0,
                state,
            )

        self.canal_tree.blockSignals(
            False
        )

        self._update_scope_count()

    def selected_management_scope_uids(self):
        result = []
        for index in range(self.canal_tree.topLevelItemCount()):
            item = self.canal_tree.topLevelItem(index)
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict):
                continue
            uid = str(data.get("management_scope_uid") or "").strip()
            if uid:
                result.append(uid)
        return tuple(result)

    def _update_scope_count(self, *args):
        count = len(self.selected_management_scope_uids())
        total = self.canal_tree.topLevelItemCount()
        self.scope_count_label.setText(f"已选择 {count} / {total} 项")

    # =========================================================
    # 导出
    # =========================================================

    def _build_request(
        self,
        output_path,
    ):
        if not self.current_context:
            raise ValueError(
                "当前没有可用项目和调查批次。"
            )

        project_id = self.current_context.get(
            "project_id"
        )
        batch_id = self.current_context.get(
            "batch_id"
        )

        if (
            project_id is None
            or batch_id is None
        ):
            raise ValueError(
                "当前没有可用项目和调查批次。"
            )

        target = (
            self.office_combo
            .currentData()
        )

        if not target:
            raise ValueError(
                "请选择任务目标单位。"
            )

        task_name = (
            self.task_name_edit
            .text()
            .strip()
        )

        if not task_name:
            raise ValueError(
                "任务名称不能为空。"
            )

        scope_uids = (
            self.selected_management_scope_uids()
        )

        if not scope_uids:
            raise ValueError(
                "至少选择一个调查分管范围。"
            )

        if (
            self._distribution_mode
            == "department"
        ):
            return (
                ChildSurveyTaskExportRequest(
                    organization_unit_id=int(
                        target["id"]
                    ),
                    management_scope_uids=(
                        scope_uids
                    ),
                    task_name=task_name,
                    notes=(
                        self.notes_edit
                        .text()
                        .strip()
                    ),
                    output_path=Path(
                        output_path
                    ),
                )
            )

        return SurveyTaskExportRequest(
            project_id=int(project_id),
            survey_batch_id=int(batch_id),
            organization_unit_id=int(
                target["id"]
            ),
            management_scope_uids=scope_uids,
            task_name=task_name,
            notes=(
                self.notes_edit
                .text()
                .strip()
            ),
            output_path=Path(
                output_path
            ),
        )

    def export_task_package(self):
        try:
            integrity = (
                check_master_data_integrity()
            )

            if not integrity.passed:
                raise ValueError(
                    (
                        "基础资料检查未通过，"
                        "暂不能生成任务包。\n\n"
                        + integrity.format_text()
                    )
                )

            target = (
                self.office_combo
                .currentData()
            )

            if not target:
                raise ValueError(
                    "请选择任务目标单位。"
                )

            task_name = (
                self.task_name_edit
                .text()
                .strip()
            )

            if not task_name:
                task_name = (
                    f"{target['name']}调查任务"
                )

            default_name = (
                _safe_filename(
                    task_name
                )
                + ".ydtask"
            )

            selected_path, _ = (
                QFileDialog.getSaveFileName(
                    self,
                    "保存调查任务包",
                    default_name,
                    (
                        "调查任务包 (*.ydtask);;"
                        "所有文件 (*)"
                    ),
                )
            )

            if not selected_path:
                return None

            request = (
                self._build_request(
                    selected_path
                )
            )

            if (
                self._distribution_mode
                == "department"
            ):
                result = (
                    export_child_survey_task_package(
                        request
                    )
                )
            else:
                result = (
                    export_survey_task_package(
                        request
                    )
                )

            inspection = (
                inspect_survey_task_package(
                    result.output_path
                )
            )

            if not inspection.valid:
                raise ValueError(
                    (
                        "任务包已经生成，"
                        "但导出后完整性检查未通过。\n\n"
                        + inspection.format_user_text()
                    )
                )

            details = [
                "调查任务包已生成并通过完整性检查。",
                "",
                (
                    "管理单位："
                    f"{result.organization_name}"
                ),
                (
                    "选定分管范围："
                    f"{result.selected_management_scope_count} 项"
                ),
            ]

            reference_canal_count = getattr(
                result,
                "reference_canal_count",
                None,
            )
            form_count = getattr(
                result,
                "form_count",
                None,
            )

            if (
                reference_canal_count
                is not None
            ):
                details.append(
                    (
                        "包含渠道："
                        f"{reference_canal_count} 条"
                    )
                )

            if form_count is not None:
                details.append(
                    (
                        "调查表："
                        f"{form_count} 项"
                    )
                )

            if (
                hasattr(
                    result,
                    "parent_task_uid",
                )
                and result.parent_task_uid
            ):
                details.extend(
                    [
                        "",
                        "任务来源：由当前处级任务分发",
                    ]
                )

            details.extend(
                [
                    "",
                    (
                        "文件："
                        f"{result.output_path}"
                    ),
                ]
            )

            QMessageBox.information(
                self,
                "导出成功",
                "\n".join(
                    details
                ),
            )

            self.refresh_task_history()

            return result

        except Exception as error:
            QMessageBox.warning(
                self,
                "导出失败",
                str(error),
            )
            return None

    def inspect_existing_package(self):
        selected_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "检查调查任务包",
                "",
                (
                    "调查任务包 (*.ydtask);;"
                    "所有文件 (*)"
                ),
            )
        )

        if not selected_path:
            return None

        inspection = (
            inspect_survey_task_package(
                selected_path
            )
        )

        if inspection.valid:
            QMessageBox.information(
                self,
                "任务包检查通过",
                inspection.format_user_text(),
            )
        else:
            QMessageBox.warning(
                self,
                "任务包检查未通过",
                inspection.format_user_text(),
            )

        return inspection
