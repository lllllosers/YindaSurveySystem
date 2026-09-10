from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
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
    get_sluice_gate_records,
)


class SluiceGateListPage(QWidget):
    new_requested = Signal()
    back_requested = Signal()

    def __init__(self):
        super().__init__()

        self.current_context = get_current_context()

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        button_layout = QHBoxLayout()

        back_button = QPushButton("返回")
        back_button.clicked.connect(self.back_requested.emit)

        new_button = QPushButton("新增水闸调查")
        new_button.clicked.connect(self.new_requested.emit)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        button_layout.addWidget(back_button)
        button_layout.addWidget(new_button)
        button_layout.addWidget(refresh_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        title = QLabel("附表2.2 水闸工程状况调查记录")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        layout.addWidget(title)

        self.count_label = QLabel()
        layout.addWidget(self.count_label)

        self.table = QTableWidget()
        self.table.setColumnCount(9)

        self.table.setHorizontalHeaderLabels(
            [
                "业务编号",
                "工程名称",
                "基层处",
                "水管所",
                "渠系",
                "桩号",
                "设计流量",
                "状态",
                "修改时间",
            ]
        )

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.table.setAlternatingRowColors(True)

        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 160)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 90)
        self.table.setColumnWidth(8, 160)

        layout.addWidget(self.table, 1)

    def load_data(self):
        if not self.current_context or self.current_context["batch_id"] is None:
            self.table.setRowCount(0)
            self.count_label.setText("当前没有可用调查批次。")
            return

        records = get_sluice_gate_records(
            project_id=self.current_context["project_id"],
            survey_batch_id=self.current_context["batch_id"],
        )

        self.table.setRowCount(len(records))

        for row_index, record in enumerate(records):
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
                "void": "已作废",
            }.get(
                record["record_status"],
                record["record_status"],
            )

            design_flow = record["design_flow"]

            if design_flow is None:
                design_flow_text = ""
            else:
                design_flow_text = str(design_flow)

            values = [
                record["business_code"],
                record["asset_name"],
                record["department_name"],
                record["office_name"],
                record["canal_name"],
                record["stake"],
                design_flow_text,
                status_text,
                record["updated_at"],
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )

        self.count_label.setText(f"当前共有 {len(records)} 条水闸调查记录")
