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
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import (
    create_organization_unit,
    delete_organization_unit,
    get_departments,
    get_organization_unit,
    get_organization_unit_usage,
    get_water_offices,
    set_organization_unit_status,
    update_organization_unit,
)

from services.master_data_admin import (
    get_organization_sort_order_map,
)


class OrganizationPage(QWidget):
    def __init__(self):
        super().__init__()

        self.init_ui()
        self.load_data()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(16)

        # 页面说明
        description = QLabel(
            "维护基层处和末级管理单位基础资料。"
            "正式主数据按甲方确认顺序显示；"
            "水管所、提灌所、水库管理所等统一作为末级管理单位维护。"
            "已被工程或调查数据引用的机构仍可修改名称和备注，"
            "但业务代码等关键归属信息将受到保护。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #607080; font-size: 15px;")

        root_layout.addWidget(description)

        # 操作按钮
        button_layout = QHBoxLayout()

        add_department_button = QPushButton("新增基层处")
        add_department_button.clicked.connect(self.add_department)

        add_office_button = QPushButton("新增管理单位")
        add_office_button.clicked.connect(self.add_water_office)

        self.edit_button = QPushButton("编辑选中")
        self.edit_button.clicked.connect(self.edit_selected)

        self.status_button = QPushButton("停用选中")
        self.status_button.clicked.connect(self.toggle_selected_status)

        self.delete_button = QPushButton("删除选中")
        self.delete_button.clicked.connect(self.delete_selected)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        button_layout.addWidget(add_department_button)

        button_layout.addWidget(add_office_button)

        button_layout.addSpacing(12)

        button_layout.addWidget(self.edit_button)

        button_layout.addWidget(self.status_button)

        button_layout.addWidget(self.delete_button)

        button_layout.addWidget(refresh_button)

        button_layout.addStretch()

        root_layout.addLayout(button_layout)

        # 组织机构树
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)

        self.tree.itemSelectionChanged.connect(self.update_action_buttons)

        self.tree.itemDoubleClicked.connect(lambda item, column: self.edit_selected())

        self.tree.setHeaderLabels(
            [
                "名称",
                "类型",
                "业务代码",
                "状态",
            ]
        )

        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 120)
        self.tree.setColumnWidth(2, 120)

        root_layout.addWidget(self.tree, 1)

        self.update_action_buttons()

    def load_data(self):
        """
        从 SQLite 重新读取组织机构。
        """
        self.tree.clear()

        sort_order_map = (
            get_organization_sort_order_map()
        )

        departments = list(
            get_departments()
        )

        departments.sort(
            key=lambda unit: (
                (
                    sort_order_map.get(
                        int(unit["id"]),
                        0,
                    )
                )
                or (
                    1000000
                    + int(unit["id"])
                ),
                int(unit["id"]),
            )
        )

        for department in departments:
            department_item = QTreeWidgetItem(
                [
                    department["name"],
                    "基层处",
                    department["business_code"] or "",
                    ("启用" if department["status"] == "active" else "停用"),
                ]
            )

            department_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "id": department["id"],
                    "unit_type": "department",
                    "status": department["status"],
                },
            )

            self.tree.addTopLevelItem(department_item)

            offices = list(
                get_water_offices(
                    department["id"]
                )
            )

            offices.sort(
                key=lambda unit: (
                    (
                        sort_order_map.get(
                            int(unit["id"]),
                            0,
                        )
                    )
                    or (
                        1000000
                        + int(unit["id"])
                    ),
                    int(unit["id"]),
                )
            )

            for office in offices:
                office_item = QTreeWidgetItem(
                    [
                        office["name"],
                        "管理单位",
                        office["business_code"] or "",
                        ("启用" if office["status"] == "active" else "停用"),
                    ]
                )

                office_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {
                        "id": office["id"],
                        "unit_type": "water_office",
                        "status": office["status"],
                    },
                )

                department_item.addChild(office_item)

        self.tree.expandAll()

        self.update_action_buttons()

    def _get_selected_unit_data(self):
        """
        获取当前树中选中的组织机构信息。
        """

        selected_items = self.tree.selectedItems()

        if not selected_items:
            return None

        return selected_items[0].data(
            0,
            Qt.ItemDataRole.UserRole,
        )

    def update_action_buttons(self):
        """
        根据当前选中机构更新操作按钮。
        """

        data = self._get_selected_unit_data()

        has_selection = data is not None

        self.edit_button.setEnabled(has_selection)

        self.status_button.setEnabled(has_selection)

        self.delete_button.setEnabled(has_selection)

        if not has_selection:
            self.status_button.setText("停用选中")
            return

        if data["status"] == "active":
            self.status_button.setText("停用选中")
        else:
            self.status_button.setText("启用选中")

    def _require_selected_unit(self):
        """
        返回当前选中的组织机构。

        未选择时给出提示并返回 None。
        """

        data = self._get_selected_unit_data()

        if data is None:
            QMessageBox.information(
                self,
                "请选择机构",
                "请先在列表中选择一个基层处或管理单位。",
            )
            return None

        unit = get_organization_unit(data["id"])

        if unit is None:
            QMessageBox.warning(
                self,
                "数据不存在",
                "选中的组织机构已经不存在，请刷新列表。",
            )
            self.load_data()
            return None

        return unit

    def edit_selected(self):
        """
        编辑当前选中的基层处或水管所。
        """

        unit = self._require_selected_unit()

        if unit is None:
            return

        usage = get_organization_unit_usage(unit["id"])

        unit_type = unit["unit_type"]

        dialog = QDialog(self)

        if unit_type == "department":
            dialog.setWindowTitle("编辑基层处")
        else:
            dialog.setWindowTitle("编辑管理单位")

        dialog.resize(
            460,
            320,
        )

        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        name_edit = QLineEdit(unit["name"] or "")

        code_edit = QLineEdit(unit["business_code"] or "")

        description_edit = QTextEdit()
        description_edit.setPlainText(unit["description"] or "")
        description_edit.setMaximumHeight(90)

        department_combo = None

        if unit_type == "water_office":
            department_combo = QComboBox()

            departments = get_departments()

            current_parent_id = unit["parent_id"]

            current_index = -1

            for department in departments:
                department_id = department["id"]

                # 新的归属只能选择启用基层处。
                # 但当前已经所属的基层处即使停用，
                # 仍必须显示，避免编辑名称时误改归属。
                if (
                    department["status"] != "active"
                    and department_id != current_parent_id
                ):
                    continue

                display_name = department["name"]

                if department["status"] != "active":
                    display_name += "（停用）"

                department_combo.addItem(
                    display_name,
                    department_id,
                )

                if department_id == current_parent_id:
                    current_index = department_combo.count() - 1

                if department["id"] == current_parent_id:
                    current_index = department_combo.count() - 1

            if current_index >= 0:
                department_combo.setCurrentIndex(current_index)

            form.addRow(
                "所属基层处：",
                department_combo,
            )

        form.addRow(
            "名称：",
            name_edit,
        )

        form.addRow(
            "业务代码：",
            code_edit,
        )

        form.addRow(
            "备注：",
            description_edit,
        )

        layout.addLayout(form)

        # =========================
        # 已产生业务数据时锁定关键字段
        # =========================

        if usage["business_code_locked"]:
            code_edit.setEnabled(False)

            code_edit.setToolTip(
                "该机构已经产生工程或调查数据，" "业务代码不能再修改。"
            )

        if (
            unit_type == "water_office"
            and usage["business_reference_count"] > 0
            and department_combo is not None
        ):
            department_combo.setEnabled(False)

            department_combo.setToolTip(
                "该水管所已经产生工程或调查数据，" "所属基层处不能再修改。"
            )

        info_label = QLabel()

        if usage["business_reference_count"] > 0:
            info_label.setText(
                "该机构已有业务数据引用。"
                "名称和备注仍可修改；"
                "关键编号或归属信息已锁定。"
            )
        else:
            info_label.setText("当前机构尚未产生工程或调查数据。")

        info_label.setWordWrap(True)

        info_label.setStyleSheet("color: #607080;")

        layout.addWidget(info_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            if unit_type == "water_office":
                parent_id = (
                    department_combo.currentData()
                    if department_combo is not None
                    else unit["parent_id"]
                )
            else:
                parent_id = None

            update_organization_unit(
                unit_id=unit["id"],
                name=name_edit.text(),
                business_code=(code_edit.text()),
                parent_id=parent_id,
                description=(description_edit.toPlainText()),
            )

            self.load_data()

            QMessageBox.information(
                self,
                "保存成功",
                "组织机构资料已更新。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )

    def toggle_selected_status(self):
        """
        启用或停用选中的组织机构。
        """

        unit = self._require_selected_unit()

        if unit is None:
            return

        current_status = unit["status"]

        if current_status == "active":
            new_status = "inactive"
            action_text = "停用"
        else:
            new_status = "active"
            action_text = "启用"

        if new_status == "inactive":
            message = (
                f"确定停用“{unit['name']}”吗？\n\n"
                "停用后：\n"
                "• 历史工程和调查记录不会删除；\n"
                "• 后续新增调查将不再使用该机构；\n"
                "• 以后仍可重新启用。"
            )
        else:
            message = f"确定重新启用“{unit['name']}”吗？"

        reply = QMessageBox.question(
            self,
            f"确认{action_text}",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            set_organization_unit_status(
                unit["id"],
                new_status,
            )

            self.load_data()

            QMessageBox.information(
                self,
                f"{action_text}成功",
                (f"“{unit['name']}”" f"已{action_text}。"),
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                f"{action_text}失败",
                str(error),
            )

    def delete_selected(self):
        """
        物理删除当前选中的组织机构。

        真正是否允许删除，
        由 database.py 再次做最终校验。
        """

        unit = self._require_selected_unit()

        if unit is None:
            return

        usage = get_organization_unit_usage(unit["id"])

        if not usage["can_delete"]:
            reasons = []

            if usage["child_count"]:
                reasons.append(f"下属机构 " f"{usage['child_count']} 个")

            if usage.get("management_scope_count"):
                reasons.append(
                    f"渠道管理范围 "
                    f"{usage['management_scope_count']} 条"
                )

            if usage["asset_count"]:
                reasons.append(f"工程对象 " f"{usage['asset_count']} 个")

            if usage["survey_count"]:
                reasons.append(f"调查记录 " f"{usage['survey_count']} 条")

            QMessageBox.information(
                self,
                "不能删除",
                (
                    f"“{unit['name']}”"
                    "当前不能物理删除。\n\n"
                    "存在：" + "、".join(reasons) + "。\n\n"
                    "如不再使用，请选择“停用”。"
                ),
            )

            return

        reply = QMessageBox.warning(
            self,
            "确认永久删除",
            (
                f"确定永久删除"
                f"“{unit['name']}”吗？\n\n"
                "该操作会直接从数据库中删除"
                "这条基础资料，无法撤销。\n\n"
                "只有录入错误且从未被使用的资料"
                "才建议执行物理删除。"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_organization_unit(unit["id"])

            self.load_data()

            QMessageBox.information(
                self,
                "删除成功",
                "组织机构已永久删除。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                str(error),
            )

    def add_department(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("新增基层处")
        dialog.resize(420, 260)

        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        name_edit = QLineEdit()
        code_edit = QLineEdit()
        description_edit = QTextEdit()

        description_edit.setMaximumHeight(80)

        form.addRow("名称：", name_edit)
        form.addRow("业务代码：", code_edit)
        form.addRow("备注：", description_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            create_organization_unit(
                name=name_edit.text(),
                unit_type="department",
                business_code=code_edit.text(),
                description=description_edit.toPlainText(),
            )

            self.load_data()

            QMessageBox.information(
                self,
                "保存成功",
                "基层处已保存。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )

    def add_water_office(self):
        departments = [
            department
            for department in get_departments()
            if department["status"] == "active"
        ]

        if not departments:
            QMessageBox.warning(
                self,
                "无法新增",
                "当前没有可用的启用基层处，请先新增或启用基层处。",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("新增管理单位")
        dialog.resize(420, 300)

        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        department_combo = QComboBox()

        for department in departments:
            department_combo.addItem(
                department["name"],
                department["id"],
            )

        name_edit = QLineEdit()
        code_edit = QLineEdit()
        description_edit = QTextEdit()

        description_edit.setMaximumHeight(80)

        form.addRow(
            "所属基层处：",
            department_combo,
        )
        form.addRow("水管所名称：", name_edit)
        form.addRow("业务代码：", code_edit)
        form.addRow("备注：", description_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            create_organization_unit(
                name=name_edit.text(),
                unit_type="water_office",
                business_code=code_edit.text(),
                parent_id=department_combo.currentData(),
                description=description_edit.toPlainText(),
            )

            self.load_data()

            QMessageBox.information(
                self,
                "保存成功",
                "水管所已保存。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )
