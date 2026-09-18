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
from services.canal_management_scope import (
    RANGE_MODE_SEGMENT_KNOWN,
    RANGE_MODE_SEGMENT_UNKNOWN,
    RANGE_MODE_WHOLE,
)
from services.canal_management_scope_admin import (
    get_management_scopes_for_admin,
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

_SCOPE_TYPE_LABEL = "分管段"


def _format_scope_range(scope):
    mode = str(scope.get("range_mode") or "")

    if mode == RANGE_MODE_WHOLE:
        return "全渠"

    if mode == RANGE_MODE_SEGMENT_UNKNOWN:
        return "边界未知"

    start = (
        scope.get("start_stake_text")
        or scope.get("start_stake_value")
        or "?"
    )
    end = (
        scope.get("end_stake_text")
        or scope.get("end_stake_value")
        or "?"
    )
    return f"{start}～{end}"


def _format_scope_management_text(scope):
    office_name = str(
        scope.get("organization_name") or ""
    ).strip()

    detail = _format_scope_range(scope)

    if str(scope.get("status") or "") != "active":
        detail += "，停用"

    if office_name:
        return f"{office_name}（{detail}）"

    return f"未指定管理单位（{detail}）"


def _format_scope_node_name(canal_name, scope):
    mode = str(scope.get("range_mode") or "")
    office_name = str(
        scope.get("organization_name") or ""
    ).strip()

    if mode == RANGE_MODE_SEGMENT_KNOWN:
        return (
            f"{canal_name}"
            f"（{_format_scope_range(scope)}）"
        )

    if mode == RANGE_MODE_WHOLE:
        if office_name:
            return f"{canal_name}（{office_name}全渠）"
        return f"{canal_name}（全渠）"

    if office_name:
        return f"{canal_name}（{office_name}分管段）"

    return f"{canal_name}（分管段）"


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
            "请通过“管理分管段”配置全渠或分段管理关系。"
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

        self.management_scope_button = QPushButton("管理分管段")
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

        self.tree.itemDoubleClicked.connect(self._handle_item_double_clicked)

        self.tree.setHeaderLabels(
            [
                "渠道名称",
                "类型",
                "管理单位（范围）",
                "备注",
                "状态",
            ]
        )

        self.tree.setColumnWidth(0, 360)
        self.tree.setColumnWidth(1, 100)
        self.tree.setColumnWidth(2, 280)
        self.tree.setColumnWidth(3, 240)

        root_layout.addWidget(self.tree, 1)

        self.update_action_buttons()

    def load_data(self):
        """
        从 SQLite 读取渠系并构建树形结构。

        CanalUnit 始终表示唯一物理渠道。
        只有存在多个 scope，或存在 segment_known /
        segment_unknown 时，才在渠道节点下显示“分管段”虚拟节点。
        单一 whole scope 直接紧凑显示在渠道节点上。
        """
        self.tree.clear()

        sort_order_map = get_canal_sort_order_map()
        canals = list(get_canal_units())

        canals.sort(
            key=lambda canal: (
                (
                    sort_order_map.get(
                        int(canal["id"]),
                        0,
                    )
                )
                or (1000000 + int(canal["id"])),
                int(canal["id"]),
            )
        )

        scope_map = {}
        for canal in canals:
            canal_id = int(canal["id"])
            scope_map[canal_id] = list(
                get_management_scopes_for_admin(
                    canal_id
                )
            )

        item_map: dict[int, QTreeWidgetItem] = {}

        # 第一遍：创建真实 CanalUnit 节点。
        for canal in canals:
            canal_id = int(canal["id"])
            canal_name = str(canal["name"] or "")
            canal_level = str(canal["canal_level"] or "")
            canal_status = str(canal["status"] or "")
            description = str(canal["description"] or "")

            scopes = scope_map[canal_id]

            show_scope_children = (
                len(scopes) > 1
                or any(
                    str(scope.get("range_mode") or "")
                    != RANGE_MODE_WHOLE
                    for scope in scopes
                )
            )

            if not scopes:
                management_text = "未配置"
            elif show_scope_children:
                management_text = f"{len(scopes)} 个分管段"
            else:
                management_text = (
                    _format_scope_management_text(
                        scopes[0]
                    )
                )

            item = QTreeWidgetItem()
            item.setText(0, canal_name)
            item.setText(
                1,
                CANAL_LEVEL_NAMES.get(
                    canal_level,
                    canal_level,
                ),
            )
            item.setText(2, management_text)
            item.setText(3, description)
            item.setText(
                4,
                (
                    "启用"
                    if canal_status == "active"
                    else "停用"
                ),
            )
            item.setToolTip(2, management_text)
            item.setToolTip(3, description)

            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "node_type": "canal",
                    "id": canal_id,
                    "canal_id": canal_id,
                    "status": canal_status,
                },
            )

            item_map[canal_id] = item

        # 第二遍：将需要展开显示的 scope 作为虚拟“分管段”节点。
        # 分管段不是新的 CanalUnit。
        for canal in canals:
            canal_id = int(canal["id"])
            canal_name = str(canal["name"] or "")
            parent_item = item_map[canal_id]
            scopes = scope_map[canal_id]

            show_scope_children = (
                len(scopes) > 1
                or any(
                    str(scope.get("range_mode") or "")
                    != RANGE_MODE_WHOLE
                    for scope in scopes
                )
            )

            if not show_scope_children:
                continue

            for scope in scopes:
                child = QTreeWidgetItem()
                node_name = _format_scope_node_name(
                    canal_name,
                    scope,
                )
                management_text = (
                    _format_scope_management_text(
                        scope
                    )
                )
                description = str(
                    scope.get("description") or ""
                )
                scope_status = str(
                    scope.get("status") or ""
                )

                child.setText(0, node_name)
                child.setText(1, _SCOPE_TYPE_LABEL)
                child.setText(2, management_text)
                child.setText(3, description)
                child.setText(
                    4,
                    (
                        "启用"
                        if scope_status == "active"
                        else "停用"
                    ),
                )
                child.setToolTip(2, management_text)
                child.setToolTip(3, description)

                child.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {
                        "node_type": "management_scope",
                        "canal_id": canal_id,
                        "management_scope_uid": (
                            scope.get(
                                "management_scope_uid"
                            )
                        ),
                        "status": scope_status,
                    },
                )

                parent_item.addChild(child)

        # 第三遍：建立真实渠道上下级关系。
        for canal in canals:
            canal_id = int(canal["id"])
            item = item_map[canal_id]

            parent_id = canal["parent_id"]

            if parent_id is not None:
                parent_id = int(parent_id)

            if (
                parent_id is not None
                and parent_id in item_map
            ):
                item_map[parent_id].addChild(item)
            else:
                self.tree.addTopLevelItem(item)

        self.tree.expandAll()
        self.update_action_buttons()

    def _get_selected_node_data(self):
        """
        获取当前树节点的数据。

        node_type:
        - canal：真实 CanalUnit
        - management_scope：分管段虚拟节点
        """
        selected_items = self.tree.selectedItems()

        if not selected_items:
            return None

        data = selected_items[0].data(
            0,
            Qt.ItemDataRole.UserRole,
        )

        if not isinstance(data, dict):
            return None

        return data

    def _get_selected_canal_data(self):
        """
        统一获取当前节点所属 CanalUnit 标识。
        分管段节点解析回其所属物理渠道，不创建假渠道身份。
        """
        data = self._get_selected_node_data()

        if data is None:
            return None

        canal_id = data.get("canal_id")

        if canal_id is None:
            canal_id = data.get("id")

        if canal_id is None:
            return None

        return {
            "id": int(canal_id),
            "status": data.get("status"),
            "node_type": data.get(
                "node_type",
                "canal",
            ),
        }

    def _handle_item_double_clicked(
        self,
        item,
        column,
    ):
        del column

        data = item.data(
            0,
            Qt.ItemDataRole.UserRole,
        )

        if (
            isinstance(data, dict)
            and data.get("node_type")
            == "management_scope"
        ):
            self.manage_selected_scope()
            return

        self.edit_selected()

    def _require_selected_canal(self):
        """
        获取当前节点所属的真实 CanalUnit。

        即使选中“分管段”虚拟节点，也只解析回所属 CanalUnit。
        """
        data = self._get_selected_node_data()

        if data is None:
            QMessageBox.information(
                self,
                "请选择渠系",
                "请先在列表中选择一个渠道或分管段节点。",
            )
            return None

        canal_id = data.get("canal_id")

        if canal_id is None:
            canal_id = data.get("id")

        if canal_id is None:
            QMessageBox.warning(
                self,
                "数据异常",
                "当前节点缺少所属渠道标识，请刷新列表。",
            )
            return None

        canal = get_canal_unit(
            int(canal_id)
        )

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
        根据当前树节点类型更新操作按钮。

        渠道节点允许渠道编辑/启停/删除；
        分管段节点只允许进入分管段维护。
        """
        data = self._get_selected_node_data()

        if data is None:
            self.edit_button.setEnabled(False)
            self.status_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.management_scope_button.setEnabled(False)
            self.status_button.setText("停用选中")
            self.management_scope_button.setText(
                "管理分管段"
            )
            return

        is_scope = (
            data.get("node_type")
            == "management_scope"
        )

        self.management_scope_button.setEnabled(
            True
        )

        if is_scope:
            self.edit_button.setEnabled(False)
            self.status_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.status_button.setText("停用选中")
            self.management_scope_button.setText(
                "编辑分管段"
            )
            return

        self.edit_button.setEnabled(True)
        self.status_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.management_scope_button.setText(
            "管理分管段"
        )

        if data.get("status") == "active":
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
