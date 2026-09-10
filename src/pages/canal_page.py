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
    get_canal_units,
    get_departments,
    get_water_offices,
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
        )
        description.setStyleSheet(
            "color: #607080; font-size: 14px;"
        )

        root_layout.addWidget(description)

        button_layout = QHBoxLayout()

        add_button = QPushButton("新增渠道")
        add_button.clicked.connect(self.add_canal)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        button_layout.addWidget(add_button)
        button_layout.addWidget(refresh_button)
        button_layout.addStretch()

        root_layout.addLayout(button_layout)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)

        self.tree.setHeaderLabels(
            [
                "渠道名称",
                "渠道层级",
                "管理单位",
                "状态",
            ]
        )

        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 120)
        self.tree.setColumnWidth(2, 220)

        root_layout.addWidget(self.tree, 1)

    def load_data(self):
        """
        从 SQLite 读取渠系，并按照 parent_id 构建树形结构。
        """
        self.tree.clear()

        canals = get_canal_units()

        item_map: dict[int, QTreeWidgetItem] = {}

        # 第一遍：先创建所有节点
        for canal in canals:
            canal_id = int(canal["id"])
            canal_name = str(canal["name"] or "")
            canal_level = str(canal["canal_level"] or "")
            organization_name = str(
                canal["organization_name"] or ""
            )
            status = str(canal["status"] or "")

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
                organization_name,
            )

            item.setText(
                3,
                "启用" if status == "active" else "停用",
            )

            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                canal_id,
            )

            item_map[canal_id] = item

        # 第二遍：建立父子关系
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
            canal_name = str(canal["name"] or "")
            canal_level = str(canal["canal_level"] or "")

            parent_combo.addItem(
                (
                    f"{canal_name} "
                    f"({CANAL_LEVEL_NAMES.get(canal_level, '')})"
                ),
                canal["id"],
            )

        organization_combo = QComboBox()
        organization_combo.addItem(
            "暂不指定",
            None,
        )

        departments = get_departments()

        for department in departments:
            offices = get_water_offices(
                department["id"]
            )

            for office in offices:
                organization_combo.addItem(
                    (
                        f"{department['name']} / "
                        f"{office['name']}"
                    ),
                    office["id"],
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
            "管理水管所：",
            organization_combo,
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

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        try:
            create_canal_unit(
                name=name_edit.text(),
                canal_level=level_combo.currentData(),
                parent_id=parent_combo.currentData(),
                organization_unit_id=(
                    organization_combo.currentData()
                ),
                description=(
                    description_edit.toPlainText()
                ),
            )

            self.load_data()

            QMessageBox.information(
                self,
                "保存成功",
                "渠道已保存。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )