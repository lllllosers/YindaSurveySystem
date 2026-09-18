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
    create_canal_unit,
    delete_canal_unit,
    get_canal_unit,
    get_canal_unit_usage,
    get_canal_units,
    set_canal_unit_status,
    update_canal_unit,
)

from services.master_data_admin import (
    get_canal_sort_order_map,
)
from services.canal_management_scope_admin import (
    get_canal_management_summary_map,
)
from pages.components.canal_management_scope_dialog import (
    CanalManagementScopeDialog,
)

CANAL_LEVEL_NAMES = {
    "01": "干渠",
    "02": "分干渠",
    "03": "支渠",
    "04": "分支渠",
}


class CanalPage(QWidget):
    def __init__(self):
        super().__init__()

        self.init_ui()
        self.load_data()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(16)

        description = QLabel(
            "维护干渠、分干渠、支渠和分支渠基础资料。"
            "渠道实体与管理单位分开维护；"
            "请通过“管理范围”配置全渠或分段管理关系。"
            "无法取得正式边界桩号时，可登记为分段管理（边界未知）。"
            "已被工程或调查数据引用的渠系仍可修改名称和备注，"
            "但渠道层级和上级渠道将受到保护。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #607080; font-size: 15px;")

        root_layout.addWidget(description)

        button_layout = QHBoxLayout()

        add_button = QPushButton("新增渠道")
        add_button.clicked.connect(self.add_canal)

        self.edit_button = QPushButton("编辑选中")
        self.edit_button.clicked.connect(self.edit_selected)

        self.status_button = QPushButton("停用选中")
        self.status_button.clicked.connect(self.toggle_selected_status)

        self.delete_button = QPushButton("删除选中")
        self.delete_button.clicked.connect(self.delete_selected)

        self.management_scope_button = QPushButton("管理范围")
        self.management_scope_button.clicked.connect(
            self.manage_selected_scope
        )

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        button_layout.addWidget(add_button)

        button_layout.addSpacing(12)

        button_layout.addWidget(self.edit_button)

        button_layout.addWidget(self.status_button)

        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.management_scope_button)
        button_layout.addWidget(refresh_button)

        button_layout.addStretch()

        root_layout.addLayout(button_layout)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)

        self.tree.itemSelectionChanged.connect(self.update_action_buttons)

        self.tree.itemDoubleClicked.connect(lambda item, column: self.edit_selected())

        self.tree.setHeaderLabels(
            [
                "渠道名称",
                "渠道层级",
                "管理范围",
                "备注",
                "状态",
            ]
        )

        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 100)
        self.tree.setColumnWidth(2, 220)
        self.tree.setColumnWidth(3, 300)

        root_layout.addWidget(self.tree, 1)

        self.update_action_buttons()

    def load_data(self):
        """
        从 SQLite 读取渠系，并按照 parent_id 构建树形结构。
        """
        self.tree.clear()

        sort_order_map = (
            get_canal_sort_order_map()
        )

        management_summary_map = (
            get_canal_management_summary_map()
        )

        canals = list(
            get_canal_units()
        )

        canals.sort(
            key=lambda canal: (
                (
                    sort_order_map.get(
                        int(canal["id"]),
                        0,
                    )
                )
                or (
                    1000000
                    + int(canal["id"])
                ),
                int(canal["id"]),
            )
        )

        item_map: dict[int, QTreeWidgetItem] = {}

        # 第一遍：先创建所有节点
        for canal in canals:
            canal_id = int(canal["id"])
            canal_name = str(canal["name"] or "")
            canal_level = str(canal["canal_level"] or "")
            management_summary = management_summary_map.get(
                canal_id,
                "",
            )
            status = str(canal["status"] or "")

            description = str(
                canal["description"] or ""
            )

            item = QTreeWidgetItem()

            item.setText(
                0,
                canal_name,
            )

            item.setText(
                1,
                CANAL_LEVEL_NAMES.get(
                    canal_level,
                    canal_level,
                ),
            )

            item.setText(
                2,
                management_summary,
            )

            item.setText(
                3,
                description,
            )

            item.setText(
                4,
                "启用" if status == "active" else "停用",
            )

            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "id": canal_id,
                    "status": status,
                },
            )

            item_map[canal_id] = item

        # 第二遍：建立父子关系
        for canal in canals:
            canal_id = int(canal["id"])
            item = item_map[canal_id]

            parent_id = canal["parent_id"]

            if parent_id is not None:
                parent_id = int(parent_id)

            if parent_id is not None and parent_id in item_map:
                item_map[parent_id].addChild(item)
            else:
                self.tree.addTopLevelItem(item)

        self.tree.expandAll()

        self.update_action_buttons()

    def _get_selected_canal_data(self):
        """
        获取当前选中的渠系节点信息。
        """

        selected_items = self.tree.selectedItems()

        if not selected_items:
            return None

        return selected_items[0].data(
            0,
            Qt.ItemDataRole.UserRole,
        )

    def _require_selected_canal(self):
        """
        获取当前选中的渠系记录。
        """

        data = self._get_selected_canal_data()

        if data is None:
            QMessageBox.information(
                self,
                "请选择渠系",
                "请先在列表中选择一个渠系节点。",
            )
            return None

        canal = get_canal_unit(data["id"])

        if canal is None:
            QMessageBox.warning(
                self,
                "数据不存在",
                "选中的渠系已经不存在，请刷新列表。",
            )

            self.load_data()

            return None

        return canal

    def update_action_buttons(self):
        """
        根据当前选中渠系更新操作按钮。
        """

        data = self._get_selected_canal_data()

        has_selection = data is not None

        self.edit_button.setEnabled(has_selection)

        self.status_button.setEnabled(has_selection)

        self.delete_button.setEnabled(has_selection)
        self.management_scope_button.setEnabled(has_selection)

        if not has_selection:
            self.status_button.setText("停用选中")
            return

        if data["status"] == "active":
            self.status_button.setText("停用选中")
        else:
            self.status_button.setText("启用选中")

    def edit_selected(self):
        """
        编辑当前选中的渠系节点。
        """

        canal = self._require_selected_canal()

        if canal is None:
            return

        canal_id = int(canal["id"])

        usage = get_canal_unit_usage(canal_id)

        dialog = QDialog(self)
        dialog.setWindowTitle("编辑渠道")
        dialog.resize(
            480,
            420,
        )

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        # =========================
        # 名称
        # =========================

        name_edit = QLineEdit(canal["name"] or "")

        # =========================
        # 渠道层级
        # =========================

        level_combo = QComboBox()

        for level_code, level_name in (
            ("01", "干渠"),
            ("02", "分干渠"),
            ("03", "支渠"),
            ("04", "分支渠"),
        ):
            level_combo.addItem(
                level_name,
                level_code,
            )

            if level_code == canal["canal_level"]:
                level_combo.setCurrentIndex(level_combo.count() - 1)

        # =========================
        # 上级渠道
        # =========================

        parent_combo = QComboBox()

        parent_combo.addItem(
            "无上级渠道",
            None,
        )

        current_parent_id = canal["parent_id"]

        for other in get_canal_units():
            other_id = int(other["id"])

            # 自己不能作为自己的上级。
            if other_id == canal_id:
                continue

            # 停用渠系原则上不能作为新的上级，
            # 但当前已经使用的上级必须继续显示。
            if other["status"] != "active" and other_id != current_parent_id:
                continue

            other_level = str(other["canal_level"] or "")

            display_name = (
                f"{other['name']} "
                f"({CANAL_LEVEL_NAMES.get(other_level, other_level)})"
            )

            if other["status"] != "active":
                display_name += "（停用）"

            parent_combo.addItem(
                display_name,
                other_id,
            )

            if other_id == current_parent_id:
                parent_combo.setCurrentIndex(parent_combo.count() - 1)

        # =========================
        # 备注
        # =========================

        description_edit = QTextEdit()

        description_edit.setPlainText(canal["description"] or "")

        description_edit.setMaximumHeight(90)

        form.addRow(
            "渠道名称：",
            name_edit,
        )

        form.addRow(
            "渠道层级：",
            level_combo,
        )

        form.addRow(
            "上级渠道：",
            parent_combo,
        )

        form.addRow(
            "备注：",
            description_edit,
        )

        layout.addLayout(form)

        # =========================
        # 已被业务引用时锁定结构字段
        # =========================

        if usage["structure_locked"]:
            level_combo.setEnabled(False)
            parent_combo.setEnabled(False)
            locked_tip = (
                "该渠系已经产生工程或调查数据，"
                "渠道层级和上级渠道不能再修改。"
            )

            level_combo.setToolTip(locked_tip)
            parent_combo.setToolTip(locked_tip)

        info_label = QLabel()

        if usage["structure_locked"]:
            info_label.setText(
                "该渠系已有业务数据引用。"
                "渠道名称和备注仍可修改；"
                "渠道层级和上级渠道已锁定。"
            )
        else:
            info_label.setText("当前渠系尚未产生工程或调查数据，" "结构信息允许修改。")

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
            update_canal_unit(
                canal_unit_id=canal_id,
                name=name_edit.text(),
                canal_level=(level_combo.currentData()),
                parent_id=(parent_combo.currentData()),
                # 旧 organization_unit_id 仅保留兼容值，
                # 渠道管理事实由 CanalManagementScope 维护。
                organization_unit_id=(canal["organization_unit_id"]),
                description=(description_edit.toPlainText()),
            )

            self.load_data()

            QMessageBox.information(
                self,
                "保存成功",
                "渠系资料已更新。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )

    def manage_selected_scope(self):
        """维护当前渠道的管理单位及全渠/分段范围。"""

        canal = self._require_selected_canal()

        if canal is None:
            return

        try:
            dialog = CanalManagementScopeDialog(
                canal["id"],
                self,
            )

            dialog.exec()
            self.load_data()

        except Exception as error:
            QMessageBox.warning(
                self,
                "管理范围打开失败",
                str(error),
            )

    def toggle_selected_status(self):
        """
        启用或停用当前渠系。
        """

        canal = self._require_selected_canal()

        if canal is None:
            return

        if canal["status"] == "active":
            new_status = "inactive"
            action_text = "停用"
        else:
            new_status = "active"
            action_text = "启用"

        if new_status == "inactive":
            message = (
                f"确定停用“{canal['name']}”吗？\n\n"
                "停用后：\n"
                "• 历史工程和调查记录不会删除；\n"
                "• 后续新增调查将不再选择该渠系；\n"
                "• 以后仍可重新启用。"
            )
        else:
            message = f"确定重新启用" f"“{canal['name']}”吗？"

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
            set_canal_unit_status(
                canal["id"],
                new_status,
            )

            self.load_data()

            QMessageBox.information(
                self,
                f"{action_text}成功",
                (f"“{canal['name']}”" f"已{action_text}。"),
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                f"{action_text}失败",
                str(error),
            )

    def delete_selected(self):
        """
        永久删除未被使用的渠系资料。
        """

        canal = self._require_selected_canal()

        if canal is None:
            return

        usage = get_canal_unit_usage(canal["id"])

        if not usage["can_delete"]:
            reasons = []

            if usage["child_count"]:
                reasons.append(f"下级渠道 " f"{usage['child_count']} 个")

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
                    f"“{canal['name']}”"
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
                f"“{canal['name']}”吗？\n\n"
                "该操作会直接从数据库中删除"
                "这条渠系基础资料，无法撤销。\n\n"
                "只有录入错误且从未被使用的资料"
                "才建议执行物理删除。"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_canal_unit(canal["id"])

            self.load_data()

            QMessageBox.information(
                self,
                "删除成功",
                "渠系基础资料已永久删除。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                str(error),
            )

    def add_canal(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("新增渠道")
        dialog.resize(460, 380)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        name_edit = QLineEdit()

        level_combo = QComboBox()
        level_combo.addItem("干渠", "01")
        level_combo.addItem("分干渠", "02")
        level_combo.addItem("支渠", "03")
        level_combo.addItem("分支渠", "04")

        parent_combo = QComboBox()
        parent_combo.addItem(
            "无上级渠道",
            None,
        )

        canals = get_canal_units()

        for canal in canals:
            if canal["status"] != "active":
                continue
            canal_name = str(canal["name"] or "")
            canal_level = str(canal["canal_level"] or "")

            parent_combo.addItem(
                (f"{canal_name} " f"({CANAL_LEVEL_NAMES.get(canal_level, '')})"),
                canal["id"],
            )

        description_edit = QTextEdit()
        description_edit.setMaximumHeight(90)

        form.addRow(
            "渠道名称：",
            name_edit,
        )

        form.addRow(
            "渠道层级：",
            level_combo,
        )

        form.addRow(
            "上级渠道：",
            parent_combo,
        )

        form.addRow(
            "备注：",
            description_edit,
        )

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
            create_canal_unit(
                name=name_edit.text(),
                canal_level=level_combo.currentData(),
                parent_id=parent_combo.currentData(),
                organization_unit_id=None,
                description=(description_edit.toPlainText()),
            )

            self.load_data()

            QMessageBox.information(
                self,
                "保存成功",
                "渠道已保存。请通过“管理范围”配置管理单位及范围。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )
