from PySide6.QtCore import (
    Qt,
    Signal,
)
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

from forms.engineering.registry import (
    get_engineering_asset_type_display_name,
)

from pages.engineering_asset_detail_dialog import (
    EngineeringAssetDetailDialog,
)

class EngineeringAssetPage(QWidget):
    open_survey_record_requested = Signal(
        str,
        int,
    )

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
            "查看当前项目工程台账及当前调查批次状态。"
            "双击已有当前调查批次记录可直接打开完整调查表；"
            "未调查工程双击进入工程详情。"
        )
        description.setWordWrap(True)
        description.setObjectName(
            "pageDescription"
        )

        self.detail_button = QPushButton(
            "查看工程详情"
        )
        self.detail_button.setEnabled(False)
        self.detail_button.clicked.connect(
            self.open_asset_detail
        )

        self.open_survey_button = QPushButton(
            "打开当前调查批次调查表"
        )
        self.open_survey_button.setProperty(
            "role",
            "primary",
        )
        self.open_survey_button.setEnabled(False)
        self.open_survey_button.clicked.connect(
            self.open_current_survey
        )

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        top_layout.addWidget(description)
        top_layout.addStretch()
        top_layout.addWidget(self.detail_button)
        top_layout.addWidget(
            self.open_survey_button
        )
        top_layout.addWidget(refresh_button)

        layout.addLayout(top_layout)

        self.count_label = QLabel()
        self.count_label.setObjectName("summaryLabel")
        self.count_label.setMinimumHeight(42)
        layout.addWidget(self.count_label)

        self.table = QTableWidget()

        self.table.cellDoubleClicked.connect(
            self.handle_row_double_clicked
        )
        self.table.itemSelectionChanged.connect(
            self.update_action_buttons
        )

        self.table.setColumnCount(12)

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
                "当前调查批次状态",
                "工程状况类别",
                "调查时间",
                "工程状态",
            ]
        )

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

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

        self.table.setColumnWidth(9, 110)
        self.table.setColumnWidth(10, 120)
        self.table.setColumnWidth(11, 100)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(
            self.table,
            1,
        )

    def load_data(self):
        if not self.current_context:
            self.table.setRowCount(0)
            self.count_label.setText("当前没有可用项目。")
            return

        assets = get_engineering_assets(
            project_id=self.current_context["project_id"],
            survey_batch_id=self.current_context["batch_id"],
        )

        self.table.setRowCount(len(assets))

        for row_index, asset in enumerate(assets):
            asset_type_text = (
                get_engineering_asset_type_display_name(
                    asset["asset_type"]
                )
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

            survey_status_text = {
                "draft": "草稿",
                "completed": "录入完成",
                "void": "已作废",
                None: "当前调查批次未调查",
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

            overall_grade_value = (
                asset["overall_grade"]
                if "overall_grade" in asset.keys()
                else ""
            )
            survey_date_value = (
                asset["survey_date"]
                if "survey_date" in asset.keys()
                else ""
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
                overall_grade_value,
                survey_date_value,
                asset_status_text,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))

                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        asset["engineering_asset_id"],
                    )
                    item.setData(
                        Qt.ItemDataRole.UserRole + 1,
                        asset["survey_record_id"],
                    )
                    item.setData(
                        Qt.ItemDataRole.UserRole + 2,
                        asset["survey_form_code"],
                    )

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )

        self.count_label.setText(
            f"当前工程台账共 {len(assets)} 个工程对象"
        )
        self.update_action_buttons()

    def _selected_identity(self, row=None):
        if row is None:
            row = self.table.currentRow()

        if row is None or row < 0:
            return None

        item = self.table.item(int(row), 0)

        if item is None:
            return None

        return {
            "engineering_asset_id": item.data(
                Qt.ItemDataRole.UserRole
            ),
            "survey_record_id": item.data(
                Qt.ItemDataRole.UserRole + 1
            ),
            "form_code": item.data(
                Qt.ItemDataRole.UserRole + 2
            ),
        }

    def update_action_buttons(self):
        identity = self._selected_identity()

        has_asset = (
            identity is not None
            and identity["engineering_asset_id"]
            is not None
        )

        has_survey = (
            has_asset
            and identity["survey_record_id"]
            is not None
            and bool(identity["form_code"])
        )

        self.detail_button.setEnabled(has_asset)
        self.open_survey_button.setEnabled(
            has_survey
        )

    def handle_row_double_clicked(
        self,
        row,
        column,
    ):
        identity = self._selected_identity(row)

        if identity is None:
            return

        if (
            identity["survey_record_id"]
            is not None
            and identity["form_code"]
        ):
            self.open_survey_record_requested.emit(
                str(identity["form_code"]),
                int(identity["survey_record_id"]),
            )
            return

        self.open_asset_detail()

    def open_current_survey(self):
        identity = self._selected_identity()

        if identity is None:
            return

        if (
            identity["survey_record_id"]
            is None
            or not identity["form_code"]
        ):
            return

        self.open_survey_record_requested.emit(
            str(identity["form_code"]),
            int(identity["survey_record_id"]),
        )

    def open_asset_detail(self, *args):
        identity = self._selected_identity()

        if identity is None:
            return

        engineering_asset_id = (
            identity["engineering_asset_id"]
        )

        if engineering_asset_id is None:
            return

        dialog = EngineeringAssetDetailDialog(
            engineering_asset_id=int(
                engineering_asset_id
            ),
            parent=self,
        )

        dialog.open_survey_record_requested.connect(
            self.open_survey_record_requested.emit
        )

        dialog.exec()
