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
    get_departments,
    get_water_offices,
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
            "维护基层处和水管所基础资料。" "当前阶段先支持新增和查看。"
        )
        description.setStyleSheet("color: #607080; font-size: 14px;")

        root_layout.addWidget(description)

        # 操作按钮
        button_layout = QHBoxLayout()

        add_department_button = QPushButton("新增基层处")
        add_department_button.clicked.connect(self.add_department)

        add_office_button = QPushButton("新增水管所")
        add_office_button.clicked.connect(self.add_water_office)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        button_layout.addWidget(add_department_button)
        button_layout.addWidget(add_office_button)
        button_layout.addWidget(refresh_button)
        button_layout.addStretch()

        root_layout.addLayout(button_layout)

        # 组织机构树
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)

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

    def load_data(self):
        """
        从 SQLite 重新读取组织机构。
        """
        self.tree.clear()

        departments = get_departments()

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
                1000,
                department["id"],
            )

            self.tree.addTopLevelItem(department_item)

            offices = get_water_offices(department["id"])

            for office in offices:
                office_item = QTreeWidgetItem(
                    [
                        office["name"],
                        "水管所",
                        office["business_code"] or "",
                        ("启用" if office["status"] == "active" else "停用"),
                    ]
                )

                office_item.setData(
                    0,
                    1000,
                    office["id"],
                )

                department_item.addChild(office_item)

        self.tree.expandAll()

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
        departments = get_departments()

        if not departments:
            QMessageBox.warning(
                self,
                "无法新增",
                "请先新增基层处。",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("新增水管所")
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
