from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import (
    get_canal_lineage,
    get_canal_units_for_organization,
    get_current_context,
    get_departments,
    get_water_offices,
)
from services.master_data_integrity import (
    check_master_data_integrity,
)
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)
from services.survey_task_package_reader import (
    inspect_survey_task_package,
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

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.current_context = None

        self._init_ui()
        self._connect_signals()
        self.reload_context()

    # =========================================================
    # UI
    # =========================================================

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root.setSpacing(16)

        intro = QLabel(
            "调查任务包（.ydtask）用于明确某个管理单位本次需要调查的渠系范围，"
            "并随包携带必要的组织、渠系和附表参考信息。"
            "任务包本身不包含调查结果，不会预生成工程台账或调查记录。"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(
            "color: #607080;"
        )
        root.addWidget(intro)

        context_group = QGroupBox(
            "一、当前项目与调查批次"
        )
        context_layout = QFormLayout(
            context_group
        )

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
            "当前批次：",
            self.batch_label,
        )

        root.addWidget(context_group)

        assignment_group = QGroupBox(
            "二、任务分配"
        )
        assignment_layout = QFormLayout(
            assignment_group
        )

        self.department_combo = (
            QComboBox()
        )
        self.office_combo = QComboBox()
        self.task_name_edit = (
            QLineEdit()
        )
        self.notes_edit = (
            QLineEdit()
        )
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
            "三、调查渠系范围"
        )
        scope_layout = QVBoxLayout(
            scope_group
        )

        scope_hint = QLabel(
            "选择管理单位后，系统自动列出该单位当前明确管理的启用渠系，"
            "并默认全部勾选。导出时，上级渠系会作为参考信息自动随包携带。"
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
                "上级渠道",
                "渠道级别",
                "渠道类型",
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
            "检查已有任务包"
        )
        self.export_button = QPushButton(
            "导出 .ydtask"
        )
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

        self._set_operational_enabled(
            has_context
        )

        if has_context:
            self._load_departments()

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

    # =========================================================
    # 机构级联
    # =========================================================

    def _load_departments(self):
        self.department_combo.blockSignals(
            True
        )
        self.department_combo.clear()

        departments = [
            row
            for row in get_departments()
            if row["status"] == "active"
        ]

        departments.sort(
            key=lambda row: (
                int(
                    row["sort_order"]
                    or 0
                )
                or (
                    1000000
                    + int(row["id"])
                ),
                int(row["id"]),
            )
        )

        for department in departments:
            self.department_combo.addItem(
                department["name"],
                {
                    "id": int(
                        department["id"]
                    ),
                    "name": (
                        department["name"]
                    ),
                },
            )

        self.department_combo.blockSignals(
            False
        )

        self._department_changed()

    def _department_changed(self):
        self.office_combo.blockSignals(
            True
        )
        self.office_combo.clear()

        department = (
            self.department_combo
            .currentData()
        )

        if not department:
            self.office_combo.blockSignals(
                False
            )
            self._clear_scope()
            return

        offices = [
            row
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
                    + int(row["id"])
                ),
                int(row["id"]),
            )
        )

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
                },
            )

        self.office_combo.blockSignals(
            False
        )

        self._office_changed()

    def _office_changed(self):
        office = (
            self.office_combo
            .currentData()
        )

        if not office:
            self.task_name_edit.clear()
            self._clear_scope()
            return

        self.task_name_edit.setText(
            f"{office['name']}调查任务"
        )

        self._load_office_canals(
            office["id"]
        )

    # =========================================================
    # 渠系范围
    # =========================================================

    def _clear_scope(self):
        self.canal_tree.blockSignals(
            True
        )
        self.canal_tree.clear()
        self.canal_tree.blockSignals(
            False
        )
        self._update_scope_count()

    def _load_office_canals(
        self,
        office_id,
    ):
        self.canal_tree.blockSignals(
            True
        )
        self.canal_tree.clear()

        canals = list(
            get_canal_units_for_organization(
                office_id
            )
        )

        canals.sort(
            key=lambda row: (
                int(
                    row["sort_order"]
                    or 0
                )
                or (
                    1000000
                    + int(row["id"])
                ),
                int(row["id"]),
            )
        )

        for canal in canals:
            item = QTreeWidgetItem()

            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                int(canal["id"]),
            )

            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                0,
                Qt.CheckState.Checked,
            )

            canal_level = str(
                canal["canal_level"]
                or ""
            )

            parent_name = ""

            lineage = (
                get_canal_lineage(
                    int(canal["id"])
                )
            )

            if len(lineage) >= 2:
                parent_name = str(
                    lineage[-2]["name"]
                    or ""
                )

            item.setText(
                1,
                str(
                    canal["name"]
                    or ""
                ),
            )
            item.setText(
                2,
                parent_name,
            )
            item.setText(
                3,
                canal_level,
            )
            item.setText(
                4,
                _CANAL_LEVEL_NAMES.get(
                    canal_level,
                    "",
                ),
            )
            item.setText(
                5,
                str(
                    canal["description"]
                    or ""
                ),
            )

            self.canal_tree.addTopLevelItem(
                item
            )

        self.canal_tree.blockSignals(
            False
        )

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

    def selected_canal_ids(self):
        result = []

        for index in range(
            self.canal_tree.topLevelItemCount()
        ):
            item = (
                self.canal_tree
                .topLevelItem(index)
            )

            if (
                item.checkState(0)
                == Qt.CheckState.Checked
            ):
                result.append(
                    int(
                        item.data(
                            0,
                            Qt.ItemDataRole.UserRole,
                        )
                    )
                )

        return tuple(result)

    def _update_scope_count(
        self,
        *args,
    ):
        count = len(
            self.selected_canal_ids()
        )

        total = (
            self.canal_tree
            .topLevelItemCount()
        )

        self.scope_count_label.setText(
            f"已选择 {count} / {total} 条"
        )

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

        project_id = (
            self.current_context.get(
                "project_id"
            )
        )
        batch_id = (
            self.current_context.get(
                "batch_id"
            )
        )

        if (
            project_id is None
            or batch_id is None
        ):
            raise ValueError(
                "当前没有可用项目和调查批次。"
            )

        office = (
            self.office_combo
            .currentData()
        )

        if not office:
            raise ValueError(
                "请选择管理单位。"
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

        canal_ids = (
            self.selected_canal_ids()
        )

        if not canal_ids:
            raise ValueError(
                "至少选择一条调查渠系。"
            )

        return SurveyTaskExportRequest(
            project_id=int(
                project_id
            ),
            survey_batch_id=int(
                batch_id
            ),
            organization_unit_id=int(
                office["id"]
            ),
            canal_ids=canal_ids,
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
                        "正式主数据一致性检查未通过，"
                        "暂不能导出任务包。\n\n"
                        + integrity.format_text()
                    )
                )

            office = (
                self.office_combo
                .currentData()
            )

            if not office:
                raise ValueError(
                    "请选择管理单位。"
                )

            task_name = (
                self.task_name_edit
                .text()
                .strip()
            )

            if not task_name:
                task_name = (
                    f"{office['name']}调查任务"
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
                    "导出调查任务包",
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
                        + inspection.format_text()
                    )
                )

            QMessageBox.information(
                self,
                "导出成功",
                (
                    "调查任务包已生成并通过完整性检查。\n\n"
                    f"管理单位：{result.organization_name}\n"
                    f"选定渠系：{result.selected_canal_count} 条\n"
                    f"参考渠系：{result.reference_canal_count} 条\n"
                    f"附表参考：{result.form_count} 项\n\n"
                    f"文件：{result.output_path}"
                ),
            )

            return result

        except Exception as error:
            QMessageBox.warning(
                self,
                "导出失败",
                str(error),
            )
            return None

    # =========================================================
    # 检查已有包
    # =========================================================

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
                inspection.format_text(),
            )
        else:
            QMessageBox.warning(
                self,
                "任务包检查未通过",
                inspection.format_text(),
            )

        return inspection
