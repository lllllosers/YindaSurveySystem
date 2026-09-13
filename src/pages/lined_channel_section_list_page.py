from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import (
    get_current_context,
    get_lined_channel_section_records,
)


class LinedChannelSectionListPage(QWidget):
    new_requested = Signal()
    back_requested = Signal()
    edit_requested = Signal(int)

    def __init__(self):
        super().__init__()

        self.current_context = None
        self.records = []

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # =========================
        # 顶部按钮
        # =========================

        button_layout = QHBoxLayout()

        back_button = QPushButton("返回")
        back_button.clicked.connect(self.back_requested.emit)

        new_button = QPushButton("新增渠道渠段调查")
        new_button.clicked.connect(self.new_requested.emit)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        button_layout.addWidget(back_button)
        button_layout.addWidget(new_button)
        button_layout.addWidget(refresh_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # =========================
        # 标题
        # =========================

        title = QLabel("附表2.1 防渗衬砌渠道渠段工程状况调查记录")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        layout.addWidget(title)

        description = QLabel(
            "当前阶段已接入基本信息、"
            "草稿保存和重新打开修改。"
            "分项评价、完成调查和导出将在后续阶段接入。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #607080; font-size: 14px;")

        layout.addWidget(description)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #52606d; font-size: 14px;")

        layout.addWidget(self.count_label)

        # =========================
        # 表格
        # =========================

        self.table = QTableWidget()

        self.table.setColumnCount(11)

        self.table.setHorizontalHeaderLabels(
            [
                "业务编号",
                "渠道名称",
                "基层处",
                "水管所",
                "渠系",
                "起始桩号",
                "终止桩号",
                "渠段长度(m)",
                "工程状况类别",
                "状态",
                "修改时间",
            ]
        )

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setAlternatingRowColors(True)

        self.table.cellDoubleClicked.connect(self.open_record)

        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 160)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 110)
        self.table.setColumnWidth(7, 110)
        self.table.setColumnWidth(8, 90)
        self.table.setColumnWidth(9, 160)
        self.table.setColumnWidth(8, 110)
        self.table.setColumnWidth(9, 90)
        self.table.setColumnWidth(10, 160)

        layout.addWidget(
            self.table,
            1,
        )

    def load_data(self):
        """
        加载当前项目、当前调查批次的
        附表2.1调查记录。
        """

        self.current_context = get_current_context()

        if not self.current_context or self.current_context["batch_id"] is None:
            self.records = []
            self.table.setRowCount(0)
            self.count_label.setText("当前没有可用调查批次。")
            return

        self.records = get_lined_channel_section_records(
            project_id=(self.current_context["project_id"]),
            survey_batch_id=(self.current_context["batch_id"]),
        )

        self.render_records()

    def render_records(self):
        self.table.setRowCount(len(self.records))

        for row_index, record in enumerate(self.records):
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                record["record_status"],
                record["record_status"],
            )

            record_data = record.get("record_data") or {}

            section_length = record_data.get("section_length")

            section_length_text = "" if section_length is None else str(section_length)

            values = [
                record["business_code"],
                record["asset_name"],
                record["department_name"],
                record["office_name"],
                record["canal_name"],
                record["start_stake_text"],
                record["end_stake_text"],
                section_length_text,
                record["overall_grade"] or "",
                status_text,
                record["updated_at"],
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

        self.count_label.setText(f"当前批次共 {len(self.records)} 条渠道渠段调查记录。")

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
