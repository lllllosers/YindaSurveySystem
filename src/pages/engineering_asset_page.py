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
    get_engineering_assets,
)


ASSET_TYPE_NAMES = {
    "lined_channel_section": "防渗衬砌渠道",
    "sluice_gate": "水闸",
}


class EngineeringAssetPage(QWidget):
    def __init__(self):
        super().__init__()

        self.current_context = get_current_context()

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        top_layout = QHBoxLayout()

        description = QLabel(
            "工程台账用于管理长期工程对象。"
            "同一工程以后可以关联多个调查批次。"
        )

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(
            self.load_data
        )

        top_layout.addWidget(description)
        top_layout.addStretch()
        top_layout.addWidget(refresh_button)

        layout.addLayout(top_layout)

        self.count_label = QLabel()
        layout.addWidget(self.count_label)

        self.table = QTableWidget()

        self.table.setColumnCount(10)

        self.table.setHorizontalHeaderLabels(
            [
                "业务编号",
                "工程名称",
                "工程类型",
                "基层处",
                "水管所",
                "渠系",
                "桩号/渠段",
                "首次登记批次",
                "本批次调查状态",
                "工程状态",
            ]
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.table.setAlternatingRowColors(True)

        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 140)
        self.table.setColumnWidth(5, 160)
        self.table.setColumnWidth(6, 150)
        self.table.setColumnWidth(7, 160)
        self.table.setColumnWidth(8, 130)
        self.table.setColumnWidth(9, 100)

        layout.addWidget(
            self.table,
            1,
        )

    def load_data(self):
        if not self.current_context:
            self.table.setRowCount(0)
            self.count_label.setText(
                "当前没有可用项目。"
            )
            return

        assets = get_engineering_assets(
            project_id=self.current_context[
                "project_id"
            ],
            survey_batch_id=self.current_context[
                "batch_id"
            ],
        )

        self.table.setRowCount(
            len(assets)
        )

        for row_index, asset in enumerate(assets):
            asset_type_text = ASSET_TYPE_NAMES.get(
                asset["asset_type"],
                asset["asset_type"],
            )

            if asset["single_stake_text"]:
                stake_text = asset[
                    "single_stake_text"
                ]
            elif (
                asset["start_stake_text"]
                or asset["end_stake_text"]
            ):
                stake_text = (
                    f"{asset['start_stake_text'] or ''}"
                    " ～ "
                    f"{asset['end_stake_text'] or ''}"
                )
            else:
                stake_text = ""

            survey_status_text = {
                "draft": "草稿",
                "completed": "录入完成",
                "void": "已作废",
                None: "本批次未调查",
            }.get(
                asset["survey_status"],
                str(asset["survey_status"] or ""),
            )

            asset_status_text = {
                "active": "在用",
                "inactive": "停用",
                "retired": "已拆除/退出",
            }.get(
                asset["asset_status"],
                asset["asset_status"],
            )

            values = [
                asset["business_code"],
                asset["asset_name"],
                asset_type_text,
                asset["department_name"],
                asset["office_name"],
                asset["canal_name"],
                stake_text,
                asset["first_batch_name"],
                survey_status_text,
                asset_status_text,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(
                    str(value or "")
                )

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )

        self.count_label.setText(
            f"当前工程台账共 {len(assets)} 个工程对象"
        )