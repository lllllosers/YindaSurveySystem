from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from database import (
    delete_engineering_survey_record,
    get_current_context,
    get_engineering_survey_query_records,
)


class AqueductListPage(QWidget):
    """
    附表2.3渡槽（座槽）调查记录列表。

    B1阶段只承担：
    - 当前调查批次记录展示；
    - 新增入口；
    - 打开已有草稿；
    - 返回调查首页。

    筛选、删除、成果导出等功能
    在后续阶段继续补充。
    """

    new_requested = Signal()
    back_requested = Signal()
    edit_requested = Signal(int)

    def __init__(self):
        super().__init__()

        self.current_context = None
        self.records = []

        self.init_ui()
        self.load_data()

    # =========================================================
    # UI
    # =========================================================

    def init_ui(self):
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(16)

        # =====================================================
        # 顶部操作
        # =====================================================

        button_layout = QHBoxLayout()

        back_button = QPushButton("返回")

        back_button.clicked.connect(self.back_requested.emit)

        new_button = QPushButton("新增渡槽（座槽）调查")

        new_button.clicked.connect(self.new_requested.emit)

        refresh_button = QPushButton("刷新")

        refresh_button.clicked.connect(self.load_data)

        delete_button = QPushButton("删除选中记录")

        delete_button.clicked.connect(self.delete_selected_record)

        button_layout.addWidget(back_button)

        button_layout.addWidget(new_button)

        button_layout.addWidget(refresh_button)

        button_layout.addWidget(delete_button)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        # =====================================================
        # 标题
        # =====================================================

        title = QLabel("附表2.3 渡槽（座槽）工程状况调查记录")

        title.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        layout.addWidget(title)

        description = QLabel(
            "双击调查记录可打开编辑。"
            "草稿和已完成记录均可删除；"
            "删除某工程最后一条调查记录时，"
            "对应的孤立工程台账对象也会同步清理。"
            "筛选和导出功能将在后续阶段接入。"
        )

        description.setWordWrap(True)

        description.setStyleSheet("color: #607080; " "font-size: 14px;")

        layout.addWidget(description)

        self.count_label = QLabel()

        self.count_label.setStyleSheet("color: #52606d; " "font-size: 14px;")

        layout.addWidget(self.count_label)

        # =====================================================
        # 表格
        # =====================================================

        self.table = QTableWidget()

        self.table.setColumnCount(4)

        self.table.setHorizontalHeaderLabels(
            [
                "工程名称",
                "桩号",
                "状态",
                "调查记录ID",
            ]
        )

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setAlternatingRowColors(True)

        self.table.cellDoubleClicked.connect(self.open_record)

        widths = [
            260,
            160,
            110,
            120,
        ]

        for column, width in enumerate(widths):
            self.table.setColumnWidth(
                column,
                width,
            )

        layout.addWidget(
            self.table,
            1,
        )

    # =========================================================
    # 数据
    # =========================================================

    def load_data(self):
        self.current_context = get_current_context()

        if not self.current_context or self.current_context["batch_id"] is None:
            self.records = []

            self.table.setRowCount(0)

            self.count_label.setText("当前没有可用调查批次。")

            return

        self.records = get_engineering_survey_query_records(
            project_id=(self.current_context["project_id"]),
            survey_batch_id=(self.current_context["batch_id"]),
            form_code="form_2_3",
        )

        self._render_records()

        self.count_label.setText(f"当前批次共 " f"{len(self.records)} 条渡槽调查记录。")

    # =========================================================
    # 表格
    # =========================================================

    def _render_records(self):
        self.table.setRowCount(len(self.records))

        for row_index, record in enumerate(self.records):
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                record["record_status"],
                record["record_status"],
            )

            values = [
                record["asset_name"],
                record["engineering_position"],
                status_text,
                record["survey_record_id"],
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))

                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        record["survey_record_id"],
                    )

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )

    # =========================================================
    # 删除
    # =========================================================

    def delete_selected_record(self):
        """
        删除当前选中的附表2.3调查记录。

        草稿和已完成记录都允许删除。

        如果删除后对应 EngineeringAsset
        已没有其他调查记录，
        通用删除逻辑会同时清理该孤立工程对象。
        """

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "未选择记录",
                "请先在列表中选择一条调查记录。",
            )
            return

        id_item = self.table.item(
            row,
            0,
        )

        stake_item = self.table.item(
            row,
            1,
        )

        status_item = self.table.item(
            row,
            2,
        )

        record_id_item = self.table.item(
            row,
            3,
        )

        if id_item is None:
            return

        survey_record_id = id_item.data(
            Qt.ItemDataRole.UserRole
        )

        if survey_record_id is None:
            return

        asset_name = id_item.text().strip()

        stake_text = (
            stake_item.text().strip()
            if stake_item is not None
            else ""
        )

        status_text = (
            status_item.text().strip()
            if status_item is not None
            else ""
        )

        record_id_text = (
            record_id_item.text().strip()
            if record_id_item is not None
            else str(survey_record_id)
        )

        reply = QMessageBox.question(
            self,
            "确认删除调查记录",
            (
                "确定要永久删除这条"
                "渡槽（座槽）调查记录吗？\n\n"
                f"工程名称：{asset_name}\n"
                f"桩号：{stake_text}\n"
                f"当前状态：{status_text}\n"
                f"调查记录ID：{record_id_text}\n\n"
                "删除后，该记录的全部分项评价"
                "也会同时删除。\n"
                "如果该工程已经没有其他调查记录，"
                "工程台账中的工程对象也会一并删除。\n\n"
                "此操作无法从软件中恢复。"
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
            result = (
                delete_engineering_survey_record(
                    survey_record_id=int(
                        survey_record_id
                    ),
                    form_code="form_2_3",
                )
            )

            if result["asset_deleted"]:
                extra_message = (
                    "\n\n该工程已无其他调查记录，"
                    "对应工程台账对象也已删除。"
                )

            else:
                extra_message = (
                    "\n\n该工程仍有其他调查记录，"
                    "工程台账对象已保留。"
                )

            QMessageBox.information(
                self,
                "删除成功",
                (
                    "渡槽（座槽）调查记录"
                    "已删除。"
                    f"{extra_message}"
                ),
            )

            self.load_data()

        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                str(error),
            )

    # =========================================================
    # 打开记录
    # =========================================================

    def open_record(
        self,
        row,
        column,
    ):
        item = self.table.item(
            row,
            0,
        )

        if item is None:
            return

        survey_record_id = item.data(Qt.ItemDataRole.UserRole)

        if survey_record_id is None:
            return

        self.edit_requested.emit(int(survey_record_id))
