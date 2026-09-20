from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import (
    get_current_context,
    get_engineering_survey_query_records,
    get_survey_batches,
)

from forms.engineering.formatters import (
    format_record_status,
)
from forms.engineering.registry import (
    get_engineering_form_definition,
    get_engineering_form_definitions,
    get_engineering_grade_options,
)

from services.engineering_summary_export import (
    export_engineering_summary,
)

from services.query_export import (
    export_common_query_summary,
)


class DataQueryPage(QWidget):
    open_survey_record_requested = Signal(
        str,
        int,
    )

    """
    工程调查统一数据查询。

    当前第一版：
    - 当前项目内跨批次查询；
    - 跨已注册附表2系列查询；
    - 公共条件筛选；
    - 轻量统计；
    - 当前查询结果导出。
    """

    def __init__(self):
        super().__init__()

        self.current_context = None

        self.all_records = []
        self.filtered_records = []

        self.init_ui()
        self.load_data()

    # =========================================================
    # UI
    # =========================================================

    def init_ui(self):
        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.setSpacing(16)

        description = QLabel(
            "统一查询当前项目中的工程调查数据。"
            "可跨调查批次、跨调查表筛选，"
            "并导出当前查询结果。"
        )

        description.setWordWrap(True)
        description.setObjectName(
            "pageDescription"
        )

        root_layout.addWidget(description)

        # =====================================================
        # 第一行
        # =====================================================

        filter_card = QFrame()
        filter_card.setObjectName("filterCard")
        filter_panel_layout = QVBoxLayout(filter_card)
        filter_panel_layout.setContentsMargins(16, 14, 16, 14)
        filter_panel_layout.setSpacing(10)

        filter_title = QLabel("筛选条件")
        filter_title.setObjectName("filterTitle")
        filter_panel_layout.addWidget(filter_title)

        filter_row_1 = QHBoxLayout()
        filter_row_1.setSpacing(10)
        filter_row_1_section_label = QLabel("调查范围")
        filter_row_1_section_label.setObjectName("filterRowLabel")
        filter_row_1_section_label.setFixedWidth(72)
        filter_row_1.addWidget(filter_row_1_section_label)

        self.batch_combo = QComboBox()
        self.batch_combo.setProperty("uiWidthRole", "filter")

        self.form_combo = QComboBox()
        self.form_combo.setProperty("uiWidthRole", "filter")

        self.keyword_edit = QLineEdit()
        self.keyword_edit.setProperty("uiWidthRole", "filter")

        self.keyword_edit.setPlaceholderText("业务编号 / 工程名称 / 桩号")

        filter_row_1.addWidget(QLabel("调查批次："))
        filter_row_1.addWidget(self.batch_combo)

        filter_row_1.addWidget(QLabel("调查表："))
        filter_row_1.addWidget(self.form_combo)

        filter_row_1.addWidget(QLabel("关键词："))
        filter_row_1.addWidget(self.keyword_edit)

        filter_row_1.addStretch()
        filter_panel_layout.addLayout(filter_row_1)

        # =====================================================
        # 第二行
        # =====================================================

        filter_row_2 = QHBoxLayout()
        filter_row_2.setSpacing(10)
        filter_row_2_section_label = QLabel("组织范围")
        filter_row_2_section_label.setObjectName("filterRowLabel")
        filter_row_2_section_label.setFixedWidth(72)
        filter_row_2.addWidget(filter_row_2_section_label)

        self.department_combo = QComboBox()
        self.department_combo.setProperty("uiWidthRole", "filter")

        self.office_combo = QComboBox()
        self.office_combo.setProperty("uiWidthRole", "filter")

        self.canal_combo = QComboBox()
        self.canal_combo.setProperty("uiWidthRole", "filter")

        filter_row_2.addWidget(QLabel("基层处："))
        filter_row_2.addWidget(self.department_combo)

        filter_row_2.addWidget(QLabel("水管所："))
        filter_row_2.addWidget(self.office_combo)

        filter_row_2.addWidget(QLabel("渠系："))
        filter_row_2.addWidget(self.canal_combo)

        filter_row_2.addStretch()
        filter_panel_layout.addLayout(filter_row_2)

        # =====================================================
        # 第三行
        # =====================================================

        filter_row_3 = QHBoxLayout()
        filter_row_3.setSpacing(10)
        filter_row_3_section_label = QLabel("记录状态")
        filter_row_3_section_label.setObjectName("filterRowLabel")
        filter_row_3_section_label.setFixedWidth(72)
        filter_row_3.addWidget(filter_row_3_section_label)

        self.status_combo = QComboBox()
        self.status_combo.setProperty("uiWidthRole", "filter")

        self.status_combo.addItem(
            "全部状态",
            None,
        )

        self.status_combo.addItem(
            "草稿",
            "draft",
        )

        self.status_combo.addItem(
            "录入完成",
            "completed",
        )

        self.grade_combo = QComboBox()
        self.grade_combo.setProperty("uiWidthRole", "filter")

        self.media_combo = QComboBox()
        self.media_combo.setProperty("uiWidthRole", "filter")
        self.media_combo.addItem(
            "全部影像",
            None,
        )
        self.media_combo.addItem(
            "有影像",
            "has_media",
        )
        self.media_combo.addItem(
            "无影像",
            "no_media",
        )

        query_button = QPushButton("查询")
        query_button.setProperty("uiRole", "primary")
        query_button.clicked.connect(self.apply_filters)

        reset_button = QPushButton("重置")
        reset_button.setProperty("uiRole", "secondary")
        reset_button.clicked.connect(self.reset_filters)

        refresh_button = QPushButton("刷新数据")
        refresh_button.setProperty("uiRole", "secondary")
        refresh_button.clicked.connect(self.load_data)

        export_button = QPushButton("导出查询结果")
        export_button.setProperty("uiRole", "secondary")
        export_button.clicked.connect(self.export_query_results)

        self.open_record_button = QPushButton(
            "打开完整调查表"
        )
        self.open_record_button.setProperty("uiRole", "secondary")
        self.open_record_button.setProperty(
            "role",
            "primary",
        )
        self.open_record_button.setEnabled(False)
        self.open_record_button.clicked.connect(
            self.open_selected_record
        )

        self.keyword_edit.returnPressed.connect(self.apply_filters)

        self.form_combo.currentIndexChanged.connect(
            self._form_filter_changed
        )

        self._refresh_grade_options()

        filter_row_3.addWidget(QLabel("状态："))

        filter_row_3.addWidget(self.status_combo)

        filter_row_3.addWidget(QLabel("工程状况类别："))

        filter_row_3.addWidget(self.grade_combo)

        filter_row_3.addWidget(
            QLabel("影像：")
        )
        filter_row_3.addWidget(
            self.media_combo
        )

        filter_row_3.addStretch()


        filter_panel_layout.addLayout(filter_row_3)

        filter_action_row = QHBoxLayout()
        filter_action_row.setSpacing(8)
        filter_action_row.addWidget(export_button)
        filter_action_row.addWidget(self.open_record_button)
        filter_action_row.addStretch()
        filter_action_row.addWidget(refresh_button)
        filter_action_row.addWidget(reset_button)
        filter_action_row.addWidget(query_button)
        filter_panel_layout.addLayout(filter_action_row)
        root_layout.addWidget(filter_card)

        # =====================================================
        # 统计
        # =====================================================

        self.statistics_label = QLabel()
        self.statistics_label.setObjectName("summaryLabel")
        self.statistics_label.setMinimumHeight(42)

        self.statistics_label.setStyleSheet("color: #52606d;" "font-size: 14px;")

        root_layout.addWidget(self.statistics_label)

        # =====================================================
        # 表格
        # =====================================================

        self.table = QTableWidget()

        self.table.cellDoubleClicked.connect(
            self.open_selected_record
        )
        self.table.itemSelectionChanged.connect(
            self._update_open_record_button
        )

        self.table.setColumnCount(13)

        self.table.setHorizontalHeaderLabels(
            [
                "调查表",
                "调查批次",
                "业务编号",
                "工程名称",
                "基层处",
                "水管所",
                "渠系",
                "工程位置",
                "工程状况类别",
                "调查时间",
                "状态",
                "影像",
                "修改时间",
            ]
        )

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setAlternatingRowColors(True)

        widths = [
            310,
            200,
            155,
            180,
            125,
            125,
            150,
            180,
            105,
            110,
            90,
            90,
            160,
        ]

        for index, width in enumerate(widths):
            self.table.setColumnWidth(
                index,
                width,
            )

        root_layout.addWidget(
            self.table,
            1,
        )

    # =========================================================
    # 加载
    # =========================================================

    def load_data(self):
        self.current_context = get_current_context()

        if not self.current_context or self.current_context["project_id"] is None:
            self.all_records = []
            self.filtered_records = []

            self.table.setRowCount(0)

            self.statistics_label.setText("当前没有可用调查项目。")

            self.batch_combo.clear()
            self.form_combo.clear()

            self._refresh_value_filters()

            return

        project_id = self.current_context["project_id"]

        self._load_batch_options(project_id)

        self._load_form_options()

        self.all_records = get_engineering_survey_query_records(
            project_id=project_id,
        )

        self._refresh_value_filters()

        self.apply_filters()

    def _load_batch_options(
        self,
        project_id,
    ):
        current_value = self.batch_combo.currentData()

        self.batch_combo.blockSignals(True)

        self.batch_combo.clear()

        self.batch_combo.addItem(
            "全部调查批次",
            None,
        )

        for batch in get_survey_batches(project_id):
            self.batch_combo.addItem(
                batch["batch_name"],
                batch["id"],
            )

        if current_value is not None:
            index = self.batch_combo.findData(current_value)

            if index >= 0:
                self.batch_combo.setCurrentIndex(index)

        self.batch_combo.blockSignals(False)

    def _load_form_options(self):
        current_value = self.form_combo.currentData()

        self.form_combo.blockSignals(True)

        self.form_combo.clear()

        self.form_combo.addItem(
            "全部工程调查表",
            None,
        )

        for definition in (
            get_engineering_form_definitions()
        ):
            self.form_combo.addItem(
                definition.display_name,
                definition.form_code,
            )

        if current_value is not None:
            index = self.form_combo.findData(current_value)

            if index >= 0:
                self.form_combo.setCurrentIndex(index)

        self.form_combo.blockSignals(False)

        self._refresh_grade_options()

    def _form_filter_changed(
        self,
        *args,
    ):
        self._refresh_grade_options()

    def _current_grade_options(
        self,
    ):
        return get_engineering_grade_options(
            self.form_combo.currentData()
        )

    def _refresh_grade_options(
        self,
    ):
        current_value = (
            self.grade_combo.currentData()
        )

        grade_options = (
            self._current_grade_options()
        )

        self.grade_combo.blockSignals(True)

        self.grade_combo.clear()

        self.grade_combo.addItem(
            "全部类别",
            None,
        )

        for grade in grade_options:
            self.grade_combo.addItem(
                grade,
                grade,
            )

        if current_value in grade_options:
            index = (
                self.grade_combo.findData(
                    current_value
                )
            )

            if index >= 0:
                self.grade_combo.setCurrentIndex(
                    index
                )

        self.grade_combo.blockSignals(False)

    # =========================================================
    # 动态筛选值
    # =========================================================

    def _set_value_filter(
        self,
        combo,
        values,
        all_text,
    ):
        current_value = combo.currentData()

        combo.blockSignals(True)

        combo.clear()

        combo.addItem(
            all_text,
            None,
        )

        clean_values = sorted(
            {str(value).strip() for value in values if value and str(value).strip()}
        )

        for value in clean_values:
            combo.addItem(
                value,
                value,
            )

        if current_value is not None:
            index = combo.findData(current_value)

            if index >= 0:
                combo.setCurrentIndex(index)

        combo.blockSignals(False)

    def _refresh_value_filters(self):
        self._set_value_filter(
            self.department_combo,
            [record["department_name"] for record in self.all_records],
            "全部基层处",
        )

        self._set_value_filter(
            self.office_combo,
            [record["office_name"] for record in self.all_records],
            "全部水管所",
        )

        self._set_value_filter(
            self.canal_combo,
            [record["canal_name"] for record in self.all_records],
            "全部渠系",
        )

    # =========================================================
    # 筛选
    # =========================================================

    def apply_filters(self):
        keyword = self.keyword_edit.text().strip().casefold()

        batch_id = self.batch_combo.currentData()

        form_code = self.form_combo.currentData()

        department = self.department_combo.currentData()

        office = self.office_combo.currentData()

        canal = self.canal_combo.currentData()

        status = self.status_combo.currentData()

        grade = self.grade_combo.currentData()

        media_state = (
            self.media_combo.currentData()
        )

        result = []

        for record in self.all_records:
            if batch_id is not None and record["survey_batch_id"] != batch_id:
                continue

            if form_code is not None and record["form_code"] != form_code:
                continue

            if keyword:
                keyword_values = [
                    record["business_code"],
                    record["asset_name"],
                    record["engineering_position"],
                ]

                matched = any(
                    keyword in str(value or "").casefold() for value in keyword_values
                )

                if not matched:
                    continue

            if department is not None and record["department_name"] != department:
                continue

            if office is not None and record["office_name"] != office:
                continue

            if canal is not None and record["canal_name"] != canal:
                continue

            if status is not None and record["record_status"] != status:
                continue

            if grade is not None and record["overall_grade"] != grade:
                continue

            media_count = int(
                record.get(
                    "media_count"
                )
                or 0
            )

            if (
                media_state == "has_media"
                and media_count <= 0
            ):
                continue

            if (
                media_state == "no_media"
                and media_count > 0
            ):
                continue

            result.append(record)

        self.filtered_records = result

        self._render_records(result)

        self._update_statistics(result)

    def reset_filters(self):
        self.keyword_edit.clear()

        for combo in (
            self.batch_combo,
            self.form_combo,
            self.department_combo,
            self.office_combo,
            self.canal_combo,
            self.status_combo,
            self.grade_combo,
            self.media_combo,
        ):
            if combo.count():
                combo.setCurrentIndex(0)

        self.apply_filters()

    # =========================================================
    # 表格
    # =========================================================

    def _render_records(
        self,
        records,
    ):
        self.table.setRowCount(len(records))

        for row_index, record in enumerate(records):
            status_text = format_record_status(
                record["record_status"]
            )

            media_count = int(
                record.get(
                    "media_count"
                )
                or 0
            )

            media_text = (
                f"有（{media_count}）"
                if media_count > 0
                else "无"
            )

            values = [
                record["form_display_name"],
                record["batch_name"],
                record["business_code"],
                record["asset_name"],
                record["department_name"],
                record["office_name"],
                record["canal_name"],
                record["engineering_position"],
                record["overall_grade"] or "",
                record["survey_date"],
                status_text,
                media_text,
                record["updated_at"],
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))

                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        record["survey_record_id"],
                    )
                    item.setData(
                        Qt.ItemDataRole.UserRole + 1,
                        record["form_code"],
                    )

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )

        self._update_open_record_button()

    def _selected_record_identity(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        if item is None:
            return None

        survey_record_id = item.data(
            Qt.ItemDataRole.UserRole
        )
        form_code = item.data(
            Qt.ItemDataRole.UserRole + 1
        )

        if (
            survey_record_id is None
            or not form_code
        ):
            return None

        return (
            str(form_code),
            int(survey_record_id),
        )

    def _update_open_record_button(self):
        self.open_record_button.setEnabled(
            self._selected_record_identity()
            is not None
        )

    def open_selected_record(self, *args):
        identity = (
            self._selected_record_identity()
        )

        if identity is None:
            return

        form_code, survey_record_id = identity

        self.open_survey_record_requested.emit(
            form_code,
            survey_record_id,
        )

    # =========================================================
    # 统计
    # =========================================================

    def _update_statistics(
        self,
        records,
    ):
        draft_count = sum(1 for record in records if record["record_status"] == "draft")

        completed_count = sum(
            1 for record in records if record["record_status"] == "completed"
        )

        media_record_count = sum(
            1
            for record in records
            if int(
                record.get(
                    "media_count"
                )
                or 0
            )
            > 0
        )

        grade_options = (
            self._current_grade_options()
        )

        grade_counts = {
            grade: 0
            for grade in grade_options
        }

        ungraded_count = 0

        for record in records:
            grade = record["overall_grade"]

            if grade in grade_counts:
                grade_counts[grade] += 1
            else:
                ungraded_count += 1

        grade_statistics = "".join(
            f"  |  {grade} {grade_counts[grade]}"
            for grade in grade_options
        )

        self.statistics_label.setText(
            f"查询结果 {len(records)} 条"
            f"  |  草稿 {draft_count}"
            f"  |  已完成 {completed_count}"
            f"{grade_statistics}"
            f"  |  未定 {ungraded_count}"
            f"  |  有影像 {media_record_count}"
        )

    # =========================================================
    # 导出
    # =========================================================

    def export_query_results(self):
        if not self.filtered_records:
            QMessageBox.warning(
                self,
                "没有可导出数据",
                "当前查询结果为空。",
            )
            return

        form_code = self.form_combo.currentData()

        form_definition = (
            get_engineering_form_definition(
                form_code
            )
            if form_code is not None
            else None
        )

        if (
            form_code is not None
            and form_definition is None
        ):
            QMessageBox.warning(
                self,
                "无法导出",
                (
                    "当前调查表尚未接入"
                    "工程调查定义 Registry。"
                ),
            )
            return

        batch_text = (
            self.batch_combo.currentText()
            or "全部批次"
        )

        safe_batch_text = batch_text

        invalid_chars = '\\/:*?"<>|'

        for char in invalid_chars:
            safe_batch_text = (
                safe_batch_text.replace(
                    char,
                    "_",
                )
            )

        # =========================
        # 单一表单
        # =========================

        if form_definition is not None:
            default_name = (
                "数据查询_"
                f"附表{form_definition.form_number}_"
                f"{safe_batch_text}.xlsx"
            )

        else:
            default_name = (
                "数据查询_工程调查汇总_"
                f"{safe_batch_text}.xlsx"
            )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出查询结果",
            default_name,
            "Excel 工作簿 (*.xlsx)",
        )

        if not file_path:
            return

        if not (file_path.lower().endswith(".xlsx")):
            file_path += ".xlsx"

        try:
            if form_definition is not None:
                if (
                    form_definition
                    .summary_export_definition
                    is None
                ):
                    raise ValueError(
                        f"{form_definition.form_code} "
                        "尚未配置详细汇总导出定义。"
                    )

                result = export_engineering_summary(
                    form_definition,
                    records=self.filtered_records,
                    file_path=file_path,
                )

            else:
                result = export_common_query_summary(
                    records=self.filtered_records,
                    file_path=file_path,
                )

            QMessageBox.information(
                self,
                "导出成功",
                (
                    "当前查询结果已导出。"
                    "\n\n"
                    f"导出记录数："
                    f"{result['exported_count']}"
                    "\n"
                    f"保存位置：\n"
                    f"{result['file_path']}"
                ),
            )

        except PermissionError:
            QMessageBox.warning(
                self,
                "导出失败",
                (
                    "无法写入目标 Excel 文件。\n\n"
                    "如果文件正在 Excel 中打开，"
                    "请先关闭文件后重新导出。"
                ),
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "导出失败",
                str(error),
            )
