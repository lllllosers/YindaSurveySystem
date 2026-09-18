from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from database import (
    get_canal_unit,
    get_departments,
    get_water_offices,
)

from services.canal_management_scope import (
    RANGE_MODE_SEGMENT_KNOWN,
    RANGE_MODE_SEGMENT_UNKNOWN,
    RANGE_MODE_WHOLE,
)
from services.canal_management_scope_admin import (
    create_management_scope,
    delete_management_scope,
    get_management_scopes_for_admin,
    set_management_scope_status,
    update_management_scope,
)
from services.stake import (
    parse_stake,
)


_RANGE_MODE_LABELS = {
    RANGE_MODE_WHOLE: "全渠管理",
    RANGE_MODE_SEGMENT_UNKNOWN: "分段管理（边界未知）",
    RANGE_MODE_SEGMENT_KNOWN: "分段管理（边界已知）",
}


class _ScopeEditDialog(QDialog):
    def __init__(
        self,
        *,
        canal,
        scope=None,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.canal = canal
        self.scope = scope

        self.setWindowTitle(
            "新增管理范围"
            if scope is None
            else "编辑管理范围"
        )

        self.resize(
            520,
            390,
        )

        layout = QVBoxLayout(
            self
        )

        form = QFormLayout()

        canal_label = QLabel(
            str(
                canal[
                    "name"
                ]
                or ""
            )
        )

        self.organization_combo = (
            QComboBox()
        )

        current_organization_id = (
            int(
                scope[
                    "organization_unit_id"
                ]
            )
            if scope is not None
            else None
        )

        for department in get_departments():
            for office in get_water_offices(
                department[
                    "id"
                ]
            ):
                if (
                    office[
                        "status"
                    ]
                    != "active"
                    and int(
                        office[
                            "id"
                        ]
                    )
                    != current_organization_id
                ):
                    continue

                display = (
                    f"{department['name']} / "
                    f"{office['name']}"
                )

                if (
                    office[
                        "status"
                    ]
                    != "active"
                ):
                    display += "（停用）"

                self.organization_combo.addItem(
                    display,
                    int(
                        office[
                            "id"
                        ]
                    ),
                )

                if (
                    current_organization_id
                    is not None
                    and int(
                        office[
                            "id"
                        ]
                    )
                    == current_organization_id
                ):
                    self.organization_combo.setCurrentIndex(
                        self.organization_combo.count()
                        - 1
                    )

        self.range_mode_combo = (
            QComboBox()
        )

        for mode in (
            RANGE_MODE_WHOLE,
            RANGE_MODE_SEGMENT_UNKNOWN,
            RANGE_MODE_SEGMENT_KNOWN,
        ):
            self.range_mode_combo.addItem(
                _RANGE_MODE_LABELS[
                    mode
                ],
                mode,
            )

        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText(
            "例如：K12+000"
        )

        self.end_edit = QLineEdit()
        self.end_edit.setPlaceholderText(
            "例如：K15+500"
        )

        self.description_edit = (
            QTextEdit()
        )
        self.description_edit.setMaximumHeight(
            90
        )

        form.addRow(
            "渠道：",
            canal_label,
        )
        form.addRow(
            "管理单位：",
            self.organization_combo,
        )
        form.addRow(
            "范围类型：",
            self.range_mode_combo,
        )
        form.addRow(
            "起始桩号：",
            self.start_edit,
        )
        form.addRow(
            "终止桩号：",
            self.end_edit,
        )
        form.addRow(
            "备注：",
            self.description_edit,
        )

        layout.addLayout(
            form
        )

        tip = QLabel(
            "边界无法取得正式桩号时，"
            "请选择“分段管理（边界未知）”，"
            "不要估算或编造管理边界。"
        )
        tip.setWordWrap(
            True
        )
        tip.setStyleSheet(
            "color: #607080;"
        )
        layout.addWidget(
            tip
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(
            self._accept_with_validation
        )
        buttons.rejected.connect(
            self.reject
        )

        layout.addWidget(
            buttons
        )

        self.range_mode_combo.currentIndexChanged.connect(
            self._update_stake_enabled
        )

        if scope is not None:
            index = self.range_mode_combo.findData(
                scope[
                    "range_mode"
                ]
            )

            if index >= 0:
                self.range_mode_combo.setCurrentIndex(
                    index
                )

            self.start_edit.setText(
                scope[
                    "start_stake_text"
                ]
                or ""
            )

            self.end_edit.setText(
                scope[
                    "end_stake_text"
                ]
                or ""
            )

            self.description_edit.setPlainText(
                scope[
                    "description"
                ]
                or ""
            )

            # 正式 scope 的稳定 master_key 已绑定管理单位，
            # 不允许直接改成另一个所。
            if (
                scope[
                    "master_key"
                ]
                is not None
                and str(
                    scope[
                        "master_key"
                    ]
                ).strip()
            ):
                self.organization_combo.setEnabled(
                    False
                )
                self.organization_combo.setToolTip(
                    "正式主数据范围如需变更管理单位，"
                    "请停用原范围后新增新范围。"
                )

        self._update_stake_enabled()

    def _update_stake_enabled(
        self,
    ):
        known = (
            self.range_mode_combo.currentData()
            == RANGE_MODE_SEGMENT_KNOWN
        )

        self.start_edit.setEnabled(
            known
        )
        self.end_edit.setEnabled(
            known
        )

        if not known:
            self.start_edit.clear()
            self.end_edit.clear()

    def _collect_payload(
        self,
    ):
        organization_id = (
            self.organization_combo.currentData()
        )

        if organization_id is None:
            raise ValueError(
                "请选择管理单位。"
            )

        mode = (
            self.range_mode_combo.currentData()
        )

        start_text = None
        start_value = None
        end_text = None
        end_value = None

        if mode == RANGE_MODE_SEGMENT_KNOWN:
            start_text, start_value = parse_stake(
                self.start_edit.text()
            )

            end_text, end_value = parse_stake(
                self.end_edit.text()
            )

            if (
                start_value is None
                or end_value is None
            ):
                raise ValueError(
                    "边界已知分段必须填写"
                    "完整起止桩号。"
                )

        return {
            "organization_unit_id": (
                int(
                    organization_id
                )
            ),
            "range_mode": mode,
            "start_stake_text": start_text,
            "start_stake_value": start_value,
            "end_stake_text": end_text,
            "end_stake_value": end_value,
            "description": (
                self.description_edit
                .toPlainText()
                .strip()
                or None
            ),
        }

    def _accept_with_validation(
        self,
    ):
        try:
            payload = (
                self._collect_payload()
            )

            if self.scope is None:
                create_management_scope(
                    canal_unit_id=(
                        self.canal[
                            "id"
                        ]
                    ),
                    **payload,
                )
            else:
                update_management_scope(
                    self.scope[
                        "management_scope_uid"
                    ],
                    **payload,
                )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(
                    error
                ),
            )
            return

        self.accept()


class CanalManagementScopeDialog(QDialog):
    def __init__(
        self,
        canal_unit_id,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.canal_unit_id = int(
            canal_unit_id
        )

        self.canal = get_canal_unit(
            self.canal_unit_id
        )

        if self.canal is None:
            raise ValueError(
                "没有找到指定渠道。"
            )

        self.setWindowTitle(
            "渠道管理范围"
        )

        self.resize(
            980,
            520,
        )

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            f"渠道：{self.canal['name']}"
        )
        title.setStyleSheet(
            "font-size: 18px; "
            "font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        description = QLabel(
            "渠道实体与管理单位分开维护。"
            "同一条干渠可由多个管理单位分段负责；"
            "无法取得正式边界桩号时使用"
            "“分段管理（边界未知）”。"
        )
        description.setWordWrap(
            True
        )
        description.setStyleSheet(
            "color: #607080;"
        )

        layout.addWidget(
            description
        )

        button_layout = QHBoxLayout()

        add_button = QPushButton(
            "新增范围"
        )
        add_button.clicked.connect(
            self.add_scope
        )

        self.edit_button = QPushButton(
            "编辑选中"
        )
        self.edit_button.clicked.connect(
            self.edit_selected
        )

        self.status_button = QPushButton(
            "停用选中"
        )
        self.status_button.clicked.connect(
            self.toggle_selected_status
        )

        self.delete_button = QPushButton(
            "删除选中"
        )
        self.delete_button.clicked.connect(
            self.delete_selected
        )

        refresh_button = QPushButton(
            "刷新"
        )
        refresh_button.clicked.connect(
            self.load_data
        )

        button_layout.addWidget(
            add_button
        )
        button_layout.addSpacing(
            12
        )
        button_layout.addWidget(
            self.edit_button
        )
        button_layout.addWidget(
            self.status_button
        )
        button_layout.addWidget(
            self.delete_button
        )
        button_layout.addWidget(
            refresh_button
        )
        button_layout.addStretch()

        layout.addLayout(
            button_layout
        )

        self.table = QTableWidget()
        self.table.setColumnCount(
            6
        )
        self.table.setHorizontalHeaderLabels(
            [
                "管理单位",
                "范围类型",
                "起始桩号",
                "终止桩号",
                "备注",
                "状态",
            ]
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.itemSelectionChanged.connect(
            self._update_buttons
        )

        self.table.setColumnWidth(
            0,
            230,
        )
        self.table.setColumnWidth(
            1,
            180,
        )
        self.table.setColumnWidth(
            2,
            120,
        )
        self.table.setColumnWidth(
            3,
            120,
        )
        self.table.setColumnWidth(
            4,
            220,
        )

        layout.addWidget(
            self.table,
            1,
        )

        close_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        close_buttons.rejected.connect(
            self.reject
        )

        layout.addWidget(
            close_buttons
        )

        self.load_data()

    def load_data(
        self,
    ):
        scopes = (
            get_management_scopes_for_admin(
                self.canal_unit_id
            )
        )

        self.table.setRowCount(
            len(
                scopes
            )
        )

        for row_index, scope in enumerate(
            scopes
        ):
            values = [
                scope[
                    "organization_name"
                ],
                _RANGE_MODE_LABELS.get(
                    scope[
                        "range_mode"
                    ],
                    scope[
                        "range_mode"
                    ],
                ),
                scope[
                    "start_stake_text"
                ]
                or "",
                scope[
                    "end_stake_text"
                ]
                or "",
                scope[
                    "description"
                ]
                or "",
                (
                    "启用"
                    if scope[
                        "status"
                    ]
                    == "active"
                    else "停用"
                ),
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    str(
                        value
                        or ""
                    )
                )

                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        dict(
                            scope
                        ),
                    )

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )

        self._update_buttons()

    def _selected_scope(
        self,
    ):
        rows = (
            self.table.selectionModel()
            .selectedRows()
        )

        if not rows:
            return None

        item = self.table.item(
            rows[0].row(),
            0,
        )

        if item is None:
            return None

        return item.data(
            Qt.ItemDataRole.UserRole
        )

    def _update_buttons(
        self,
    ):
        scope = (
            self._selected_scope()
        )

        enabled = (
            scope is not None
        )

        self.edit_button.setEnabled(
            enabled
        )
        self.status_button.setEnabled(
            enabled
        )
        self.delete_button.setEnabled(
            enabled
        )

        if scope is None:
            self.status_button.setText(
                "停用选中"
            )
            return

        self.status_button.setText(
            "停用选中"
            if scope[
                "status"
            ]
            == "active"
            else "启用选中"
        )

        is_official = bool(
            str(
                scope[
                    "master_key"
                ]
                or ""
            ).strip()
        )

        self.delete_button.setEnabled(
            not is_official
        )

        if is_official:
            self.delete_button.setToolTip(
                "正式主数据管理范围不能物理删除，"
                "如不再适用请停用。"
            )
        else:
            self.delete_button.setToolTip(
                ""
            )

    def add_scope(
        self,
    ):
        dialog = _ScopeEditDialog(
            canal=self.canal,
            parent=self,
        )

        if (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            self.load_data()

    def edit_selected(
        self,
    ):
        scope = (
            self._selected_scope()
        )

        if scope is None:
            return

        dialog = _ScopeEditDialog(
            canal=self.canal,
            scope=scope,
            parent=self,
        )

        if (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            self.load_data()

    def toggle_selected_status(
        self,
    ):
        scope = (
            self._selected_scope()
        )

        if scope is None:
            return

        new_status = (
            "inactive"
            if scope[
                "status"
            ]
            == "active"
            else "active"
        )

        action = (
            "停用"
            if new_status
            == "inactive"
            else "启用"
        )

        reply = QMessageBox.question(
            self,
            f"确认{action}",
            (
                f"确定{action}该渠道管理范围吗？"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            reply
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            set_management_scope_status(
                scope[
                    "management_scope_uid"
                ],
                new_status,
            )

            self.load_data()

        except Exception as error:
            QMessageBox.warning(
                self,
                f"{action}失败",
                str(
                    error
                ),
            )

    def delete_selected(
        self,
    ):
        scope = (
            self._selected_scope()
        )

        if scope is None:
            return

        reply = QMessageBox.warning(
            self,
            "确认永久删除",
            (
                "确定永久删除这条人工管理范围吗？\n\n"
                "正式主数据范围不能执行此操作。"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            reply
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            delete_management_scope(
                scope[
                    "management_scope_uid"
                ]
            )

            self.load_data()

        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                str(
                    error
                ),
            )
