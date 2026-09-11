from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database import (
    get_engineering_asset_detail,
    get_engineering_asset_history,
)

ASSET_TYPE_NAMES = {
    "lined_channel_section": "防渗衬砌渠道",
    "sluice_gate": "水闸",
}


CANAL_LEVEL_NAMES = {
    "01": "干渠",
    "02": "分干渠",
    "03": "支渠",
    "04": "分支渠",
}


class EngineeringAssetDetailDialog(QDialog):
    def __init__(
        self,
        engineering_asset_id,
        parent=None,
    ):
        super().__init__(parent)

        self.engineering_asset_id = engineering_asset_id

        self.setWindowTitle("工程详情")
        self.resize(1000, 650)

        self.init_ui()
        self.load_data()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(16)

        # =========================
        # 工程基本信息
        # =========================
        basic_group = QGroupBox("工程基本信息")

        self.basic_form = QFormLayout(basic_group)

        self.business_code_label = QLabel()
        self.asset_name_label = QLabel()
        self.asset_type_label = QLabel()
        self.department_label = QLabel()
        self.office_label = QLabel()
        self.canal_label = QLabel()
        self.canal_level_label = QLabel()
        self.stake_label = QLabel()
        self.first_batch_label = QLabel()
        self.asset_status_label = QLabel()

        self.basic_form.addRow(
            "业务编号：",
            self.business_code_label,
        )

        self.basic_form.addRow(
            "工程名称：",
            self.asset_name_label,
        )

        self.basic_form.addRow(
            "工程类型：",
            self.asset_type_label,
        )

        self.basic_form.addRow(
            "所属基层处：",
            self.department_label,
        )

        self.basic_form.addRow(
            "所属水管所：",
            self.office_label,
        )

        self.basic_form.addRow(
            "所属渠系：",
            self.canal_label,
        )

        self.basic_form.addRow(
            "渠道层级：",
            self.canal_level_label,
        )

        self.basic_form.addRow(
            "桩号/渠段：",
            self.stake_label,
        )

        self.basic_form.addRow(
            "首次登记批次：",
            self.first_batch_label,
        )

        self.basic_form.addRow(
            "工程状态：",
            self.asset_status_label,
        )

        root_layout.addWidget(basic_group)

        # =========================
        # 历次调查
        # =========================
        history_group = QGroupBox("历次调查")

        history_layout = QVBoxLayout(history_group)

        self.history_count_label = QLabel()

        history_layout.addWidget(self.history_count_label)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)

        self.history_table.setHorizontalHeaderLabels(
            [
                "调查批次",
                "调查表",
                "表单版本",
                "业务编号",
                "调查日期",
                "最终等级",
                "记录状态",
                "修改时间",
            ]
        )

        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.history_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.history_table.setAlternatingRowColors(True)

        self.history_table.setColumnWidth(
            0,
            170,
        )
        self.history_table.setColumnWidth(
            1,
            200,
        )
        self.history_table.setColumnWidth(
            2,
            100,
        )
        self.history_table.setColumnWidth(
            3,
            150,
        )
        self.history_table.setColumnWidth(
            4,
            110,
        )
        self.history_table.setColumnWidth(
            5,
            90,
        )
        self.history_table.setColumnWidth(
            6,
            100,
        )
        self.history_table.setColumnWidth(
            7,
            160,
        )

        history_layout.addWidget(self.history_table)

        root_layout.addWidget(
            history_group,
            1,
        )

        # =========================
        # 底部按钮
        # =========================
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton("关闭")

        close_button.clicked.connect(self.accept)

        button_layout.addWidget(close_button)

        root_layout.addLayout(button_layout)

    def load_data(self):
        asset = get_engineering_asset_detail(self.engineering_asset_id)

        if asset is None:
            self.asset_name_label.setText("未找到工程对象")
            return

        asset_type_text = ASSET_TYPE_NAMES.get(
            asset["asset_type"],
            asset["asset_type"],
        )

        canal_level_text = CANAL_LEVEL_NAMES.get(
            asset["canal_level"],
            asset["canal_level"] or "",
        )

        if asset["single_stake_text"]:
            stake_text = asset["single_stake_text"]

        elif asset["start_stake_text"] or asset["end_stake_text"]:
            stake_text = (
                f"{asset['start_stake_text'] or ''}"
                " ～ "
                f"{asset['end_stake_text'] or ''}"
            )

        else:
            stake_text = ""

        asset_status_text = {
            "active": "在用",
            "inactive": "停用",
            "retired": "已拆除/退出",
        }.get(
            asset["asset_status"],
            asset["asset_status"] or "",
        )

        self.business_code_label.setText(str(asset["business_code"] or ""))

        self.asset_name_label.setText(str(asset["asset_name"] or ""))

        self.asset_type_label.setText(str(asset_type_text or ""))

        self.department_label.setText(str(asset["department_name"] or ""))

        self.office_label.setText(str(asset["office_name"] or ""))

        self.canal_label.setText(str(asset["canal_name"] or ""))

        self.canal_level_label.setText(str(canal_level_text or ""))

        self.stake_label.setText(str(stake_text or ""))

        self.first_batch_label.setText(str(asset["first_batch_name"] or ""))

        self.asset_status_label.setText(str(asset_status_text or ""))

        self.load_history()

    def load_history(self):
        history = get_engineering_asset_history(self.engineering_asset_id)

        self.history_table.setRowCount(len(history))

        for row_index, record in enumerate(history):
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
                "void": "已作废",
            }.get(
                record["record_status"],
                record["record_status"] or "",
            )

            overall_grade = record["overall_grade"] or "未确定"

            form_text = f"{record['form_number']} " f"{record['form_name']}"

            version_text = record["version_name"] or record["version_code"] or ""

            values = [
                record["batch_name"],
                form_text,
                version_text,
                record["business_code"],
                record["survey_date"],
                overall_grade,
                status_text,
                record["updated_at"],
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))

                self.history_table.setItem(
                    row_index,
                    column,
                    item,
                )

        self.history_count_label.setText(f"该工程共有 {len(history)} 条调查记录")
