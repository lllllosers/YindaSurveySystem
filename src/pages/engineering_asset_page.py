from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
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

from services.engineering_numbering import (
    preview_engineering_business_code_renumber,
    renumber_engineering_business_codes,
)

from services.engineering_numbering_finalization import (
    finalize_engineering_business_codes,
    preview_engineering_numbering_finalization,
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

        self.renumber_button = QPushButton(
            "整理业务编号"
        )
        self.renumber_button.setToolTip(
            "按具体渠系和工程类型分组，"
            "按桩号从上游到下游重新整理三位顺序号。"
        )
        self.renumber_button.clicked.connect(
            self.renumber_business_codes
        )

        self.finalize_number_button = QPushButton(
            "锁定正式编号"
        )
        self.finalize_number_button.setToolTip(
            "重新按桩号核验并排序后，将当前调查批次编号锁定为正式编号。"
        )
        self.finalize_number_button.clicked.connect(
            self.finalize_business_codes
        )

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        top_layout.addWidget(description)
        top_layout.addStretch()
        top_layout.addWidget(self.detail_button)
        top_layout.addWidget(
            self.open_survey_button
        )
        top_layout.addWidget(
            self.renumber_button
        )
        top_layout.addWidget(
            self.finalize_number_button
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

        self.table.setColumnCount(14)

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
                "影像",
                "工程状态",
                "编号状态",
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
        self.table.setColumnWidth(11, 90)
        self.table.setColumnWidth(12, 100)
        self.table.setColumnWidth(13, 100)
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

            media_count = int(
                (
                    asset["media_count"]
                    if "media_count" in asset.keys()
                    else 0
                )
                or 0
            )

            media_text = (
                f"有（{media_count}）"
                if media_count > 0
                else "无"
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
                media_text,
                asset_status_text,
                {
                    "provisional": "暂编",
                    "final": "正式",
                }.get(
                    (
                        asset["code_status"]
                        if "code_status" in asset.keys()
                        else ""
                    ),
                    str(
                        (
                            asset["code_status"]
                            if "code_status" in asset.keys()
                            else ""
                        )
                        or ""
                    ),
                ),
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

        provisional_count = sum(
            1
            for asset in assets
            if (
                asset["code_status"]
                if "code_status" in asset.keys()
                else ""
            )
            != "final"
        )
        final_count = len(assets) - provisional_count

        self.count_label.setText(
            f"当前工程台账共 {len(assets)} 个工程对象；"
            f"暂编 {provisional_count}，正式 {final_count}"
        )
        self.update_action_buttons()

    def renumber_business_codes(self):
        context = self.current_context

        if (
            not context
            or context.get("project_id") is None
            or context.get("batch_id") is None
        ):
            QMessageBox.information(
                self,
                "无法整理业务编号",
                "当前没有可用项目或调查批次。",
            )
            return

        try:
            preview = preview_engineering_business_code_renumber(
                project_id=context["project_id"],
                survey_batch_id=context["batch_id"],
            )
        except Exception as error:
            QMessageBox.warning(self, "编号预检失败", str(error))
            return

        if not preview.can_apply:
            QMessageBox.warning(
                self,
                "暂不能整理业务编号",
                preview.format_text(),
            )
            return

        if preview.total_assets == 0:
            QMessageBox.information(
                self,
                "无需整理",
                "当前调查批次没有可参与业务编号整理的工程记录。",
            )
            return

        reopen_text = ""
        if preview.final_to_provisional_count > 0:
            reopen_text = (
                "\n\n其中有 "
                f"{preview.final_to_provisional_count} 个工程当前标记为正式编号；"
                "本次重新整理会将其重新置为“暂编”。"
            )

        reply = QMessageBox.question(
            self,
            "确认整理业务编号",
            (
                "系统将按具体渠系 + 工程类型分组，"
                "按桩号从上游到下游重新生成三位顺序号。\n\n"
                f"参与工程：{preview.total_assets}\n"
                f"编号分组：{preview.group_count}\n"
                f"预计编号变化：{preview.changed_code_count}"
                f"{reopen_text}\n\n"
                "本操作只整理编号，不增加调查业务 revision；"
                "同一批次 SurveyRecord 编号会同步更新。\n"
                "整理后仍为“暂编”，后续补录工程可以再次执行。"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = renumber_engineering_business_codes(
                project_id=context["project_id"],
                survey_batch_id=context["batch_id"],
            )
        except Exception as error:
            QMessageBox.warning(self, "业务编号整理失败", str(error))
            return

        self.load_data()
        QMessageBox.information(
            self,
            "业务编号整理完成",
            (
                f"参与工程：{result.total_assets}\n"
                f"编号分组：{result.group_count}\n"
                f"实际编号变化：{result.changed_code_count}\n"
                f"同步调查记录：{result.synchronized_record_count}\n\n"
                "当前编号状态为“暂编”，后续新增工程后可以再次整理。"
            ),
        )


    def finalize_business_codes(self):
        context = self.current_context

        if (
            not context
            or context.get("project_id") is None
            or context.get("batch_id") is None
        ):
            QMessageBox.information(
                self,
                "无法锁定正式编号",
                "当前没有可用项目或调查批次。",
            )
            return

        try:
            preview = preview_engineering_numbering_finalization(
                project_id=context["project_id"],
                survey_batch_id=context["batch_id"],
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "正式锁号预检失败",
                str(error),
            )
            return

        if not preview.can_finalize:
            QMessageBox.warning(
                self,
                "暂不能锁定正式编号",
                preview.format_text(),
            )
            return

        if preview.total_assets == 0:
            QMessageBox.information(
                self,
                "无需锁号",
                "当前调查批次没有可参与正式锁号的工程记录。",
            )
            return

        warning_text = ""
        if preview.has_warnings:
            warning_text = (
                "\n\n需要人工核验的提示：\n"
                + "\n".join(
                    f"• {issue.message}"
                    for issue in preview.warnings[:12]
                )
            )
            if len(preview.warnings) > 12:
                warning_text += (
                    "\n• ……其余提示请以预检结果为准。"
                )

        reply = QMessageBox.question(
            self,
            "确认锁定正式编号",
            (
                "系统会在同一事务内再次按桩号从上游到下游排序，"
                "然后将当前调查批次参与工程的编号状态设为“正式”。\n\n"
                f"参与工程：{preview.total_assets}\n"
                f"编号分组：{preview.group_count}\n"
                f"预计编号变化：{preview.changed_code_count}\n"
                f"当前暂编：{preview.provisional_count}\n"
                f"当前正式：{preview.already_final_count}"
                f"{warning_text}\n\n"
                "编号整理和锁号不会增加业务 revision。"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = finalize_engineering_business_codes(
                project_id=context["project_id"],
                survey_batch_id=context["batch_id"],
                accept_warnings=preview.has_warnings,
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "正式锁号失败",
                str(error),
            )
            return

        self.load_data()

        QMessageBox.information(
            self,
            "正式编号已锁定",
            (
                f"正式编号工程：{result.finalized_count}\n"
                f"编号分组：{result.group_count}\n"
                f"实际编号变化：{result.changed_code_count}\n"
                f"同步调查记录：{result.synchronized_record_count}\n"
                f"确认提示：{result.warning_count}"
            ),
        )


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
