from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QWidget,
)

from database import (
    create_project,
    create_survey_batch,
    get_current_context,
    get_projects,
    get_survey_batches,
    set_active_project,
    set_active_survey_batch,
)


class ProjectBatchPage(QWidget):
    """
    项目与调查批次管理。

    当前版本只提供：
    - 新增项目
    - 设置当前项目
    - 新增调查批次
    - 设置当前调查批次
    - 查看项目和批次状态
    """

    context_changed = Signal()

    def __init__(self):
        super().__init__()

        self.selected_project_id = None

        self.init_ui()
        self.load_projects()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root_layout.setSpacing(18)

        description = QLabel(
            "维护调查项目和调查批次。" "系统当前只允许一个当前项目和一个当前调查批次。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #607080; " "font-size: 14px;")

        root_layout.addWidget(description)

        # =========================
        # 项目
        # =========================

        project_title = QLabel("调查项目")
        project_title.setStyleSheet("font-size: 17px; " "font-weight: bold;")

        root_layout.addWidget(project_title)

        project_button_layout = QHBoxLayout()

        add_project_button = QPushButton("新增项目")
        add_project_button.clicked.connect(self.add_project)

        activate_project_button = QPushButton("设为当前项目")
        activate_project_button.clicked.connect(self.activate_project)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_projects)

        project_button_layout.addWidget(add_project_button)
        project_button_layout.addWidget(activate_project_button)
        project_button_layout.addWidget(refresh_button)
        project_button_layout.addStretch()

        root_layout.addLayout(project_button_layout)

        self.project_table = QTableWidget()
        self.project_table.setColumnCount(4)
        self.project_table.setHorizontalHeaderLabels(
            [
                "项目名称",
                "简称",
                "状态",
                "创建时间",
            ]
        )

        self.project_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.project_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.project_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.project_table.setColumnWidth(
            0,
            280,
        )
        self.project_table.setColumnWidth(
            1,
            160,
        )
        self.project_table.setColumnWidth(
            2,
            100,
        )
        self.project_table.setColumnWidth(
            3,
            170,
        )

        self.project_table.itemSelectionChanged.connect(
            self.on_project_selection_changed
        )

        root_layout.addWidget(
            self.project_table,
            1,
        )

        # =========================
        # 调查批次
        # =========================

        batch_title = QLabel("调查批次")
        batch_title.setStyleSheet("font-size: 17px; " "font-weight: bold;")

        root_layout.addWidget(batch_title)

        batch_button_layout = QHBoxLayout()

        add_batch_button = QPushButton("新增调查批次")
        add_batch_button.clicked.connect(self.add_batch)

        activate_batch_button = QPushButton("设为当前调查批次")
        activate_batch_button.clicked.connect(self.activate_batch)

        batch_button_layout.addWidget(add_batch_button)
        batch_button_layout.addWidget(activate_batch_button)
        batch_button_layout.addStretch()

        root_layout.addLayout(batch_button_layout)

        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(6)
        self.batch_table.setHorizontalHeaderLabels(
            [
                "批次名称",
                "批次代码",
                "开始日期",
                "结束日期",
                "状态",
                "创建时间",
            ]
        )

        self.batch_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.batch_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.batch_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.batch_table.setColumnWidth(
            0,
            240,
        )
        self.batch_table.setColumnWidth(
            1,
            150,
        )
        self.batch_table.setColumnWidth(
            2,
            110,
        )
        self.batch_table.setColumnWidth(
            3,
            110,
        )
        self.batch_table.setColumnWidth(
            4,
            100,
        )
        self.batch_table.setColumnWidth(
            5,
            170,
        )

        root_layout.addWidget(
            self.batch_table,
            1,
        )

    # =========================
    # 项目列表
    # =========================

    def load_projects(self):
        projects = get_projects()

        self.project_table.setRowCount(len(projects))

        current_context = get_current_context()

        current_project_id = current_context["project_id"] if current_context else None

        row_to_select = None

        for row_index, project in enumerate(projects):
            name_item = QTableWidgetItem(project["name"])
            name_item.setData(
                Qt.ItemDataRole.UserRole,
                project["id"],
            )

            short_name_item = QTableWidgetItem(project["short_name"] or "")

            status_text = "当前" if project["status"] == "active" else "非当前"

            status_item = QTableWidgetItem(status_text)

            created_item = QTableWidgetItem(project["created_at"] or "")

            self.project_table.setItem(
                row_index,
                0,
                name_item,
            )
            self.project_table.setItem(
                row_index,
                1,
                short_name_item,
            )
            self.project_table.setItem(
                row_index,
                2,
                status_item,
            )
            self.project_table.setItem(
                row_index,
                3,
                created_item,
            )

            if project["id"] == current_project_id:
                row_to_select = row_index

        if row_to_select is None and projects:
            row_to_select = 0

        if row_to_select is not None:
            self.project_table.selectRow(row_to_select)
        else:
            self.selected_project_id = None
            self.batch_table.setRowCount(0)

    def on_project_selection_changed(
        self,
    ):
        row = self.project_table.currentRow()

        if row < 0:
            self.selected_project_id = None
            self.batch_table.setRowCount(0)
            return

        item = self.project_table.item(
            row,
            0,
        )

        if item is None:
            return

        project_id = item.data(Qt.ItemDataRole.UserRole)

        if project_id is None:
            return

        self.selected_project_id = int(project_id)

        self.load_batches()

    # =========================
    # 批次列表
    # =========================

    def load_batches(self):
        if self.selected_project_id is None:
            self.batch_table.setRowCount(0)
            return

        batches = get_survey_batches(self.selected_project_id)

        self.batch_table.setRowCount(len(batches))

        current_context = get_current_context()

        current_batch_id = current_context["batch_id"] if current_context else None

        row_to_select = None

        status_map = {
            "draft": "草稿",
            "active": "当前",
            "completed": "已完成",
            "archived": "已归档",
        }

        for row_index, batch in enumerate(batches):
            name_item = QTableWidgetItem(batch["batch_name"])
            name_item.setData(
                Qt.ItemDataRole.UserRole,
                batch["id"],
            )

            values = [
                name_item,
                QTableWidgetItem(batch["batch_code"]),
                QTableWidgetItem(batch["start_date"] or ""),
                QTableWidgetItem(batch["end_date"] or ""),
                QTableWidgetItem(
                    status_map.get(
                        batch["status"],
                        batch["status"],
                    )
                    or ""
                ),
                QTableWidgetItem(batch["created_at"] or ""),
            ]

            for column, item in enumerate(values):
                self.batch_table.setItem(
                    row_index,
                    column,
                    item,
                )

            if batch["id"] == current_batch_id:
                row_to_select = row_index

        if row_to_select is not None:
            self.batch_table.selectRow(row_to_select)

    # =========================
    # 新增项目
    # =========================

    def add_project(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("新增调查项目")
        dialog.resize(
            460,
            300,
        )

        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        name_edit = QLineEdit()
        short_name_edit = QLineEdit()

        description_edit = QTextEdit()
        description_edit.setMaximumHeight(90)

        form.addRow(
            "项目名称：",
            name_edit,
        )
        form.addRow(
            "项目简称：",
            short_name_edit,
        )
        form.addRow(
            "项目说明：",
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
            result = create_project(
                name=name_edit.text(),
                short_name=(short_name_edit.text()),
                description=(description_edit.toPlainText()),
            )

            self.load_projects()

            self.context_changed.emit()

            message = "项目已保存。"

            if result["status"] == "active":
                message += "\n\n由于系统此前没有当前项目，" "该项目已自动设为当前项目。"

            QMessageBox.information(
                self,
                "保存成功",
                message,
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )

    # =========================
    # 设置当前项目
    # =========================

    def activate_project(self):
        row = self.project_table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "未选择项目",
                "请先选择一个项目。",
            )
            return

        item = self.project_table.item(
            row,
            0,
        )

        if item is None:
            return

        project_id = item.data(Qt.ItemDataRole.UserRole)

        if project_id is None:
            return

        try:
            set_active_project(int(project_id))

            self.load_projects()
            self.context_changed.emit()

            QMessageBox.information(
                self,
                "切换成功",
                "当前项目已切换。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "切换失败",
                str(error),
            )

    # =========================
    # 新增调查批次
    # =========================

    def add_batch(self):
        if self.selected_project_id is None:
            QMessageBox.warning(
                self,
                "无法新增",
                "请先选择所属项目。",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("新增调查批次")
        dialog.resize(
            480,
            420,
        )

        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        name_edit = QLineEdit()
        code_edit = QLineEdit()

        start_date_edit = QLineEdit()
        start_date_edit.setPlaceholderText("YYYY-MM-DD，可留空")

        end_date_edit = QLineEdit()
        end_date_edit.setPlaceholderText("YYYY-MM-DD，可留空")

        description_edit = QTextEdit()
        description_edit.setMaximumHeight(90)

        form.addRow(
            "批次名称：",
            name_edit,
        )
        form.addRow(
            "批次代码：",
            code_edit,
        )
        form.addRow(
            "开始日期：",
            start_date_edit,
        )
        form.addRow(
            "结束日期：",
            end_date_edit,
        )
        form.addRow(
            "批次说明：",
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
            result = create_survey_batch(
                project_id=(self.selected_project_id),
                batch_name=name_edit.text(),
                batch_code=code_edit.text(),
                start_date=(start_date_edit.text()),
                end_date=(end_date_edit.text()),
                description=(description_edit.toPlainText()),
            )

            self.load_batches()
            self.context_changed.emit()

            message = "调查批次已保存。"

            if result["status"] == "active":
                message += (
                    "\n\n由于当前项目此前没有"
                    "当前调查批次，"
                    "该批次已自动设为当前批次。"
                )

            QMessageBox.information(
                self,
                "保存成功",
                message,
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )

    # =========================
    # 设置当前调查批次
    # =========================

    def activate_batch(self):
        row = self.batch_table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "未选择调查批次",
                "请先选择一个调查批次。",
            )
            return

        item = self.batch_table.item(
            row,
            0,
        )

        if item is None:
            return

        batch_id = item.data(Qt.ItemDataRole.UserRole)

        if batch_id is None:
            return

        try:
            set_active_survey_batch(int(batch_id))

            self.load_projects()
            self.context_changed.emit()

            QMessageBox.information(
                self,
                "切换成功",
                "当前调查批次已切换。",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "切换失败",
                str(error),
            )
