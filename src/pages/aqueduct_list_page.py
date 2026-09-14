from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from database import (
    delete_engineering_survey_record,
    get_current_context,
    get_engineering_survey_query_records,
)
from services.aqueduct_export import (
    export_aqueduct_original_form,
)


class AqueductListPage(QWidget):
    """
    附表2.3渡槽（座槽）调查记录列表。

    本页负责当前调查批次内：
    - 新增；
    - 编辑；
    - 删除；
    - 快速筛选；
    - 录入进度统计。

    跨批次查询和汇总导出
    由统一“数据查询”模块负责。
    """

    new_requested = Signal()
    back_requested = Signal()
    edit_requested = Signal(int)

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

        export_button = QPushButton("导出结果")

        export_button.clicked.connect(self.export_original_excel)

        delete_button = QPushButton("删除选中记录")

        delete_button.clicked.connect(self.delete_selected_record)

        button_layout.addWidget(back_button)

        button_layout.addWidget(new_button)

        button_layout.addWidget(refresh_button)

        button_layout.addWidget(export_button)

        button_layout.addWidget(delete_button)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        # =====================================================
        # 标题与说明
        # =====================================================

        title = QLabel("附表2.3 渡槽（座槽）工程状况调查记录")

        title.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        layout.addWidget(title)

        description = QLabel(
            "双击记录可打开调查表。"
            "本页用于当前批次录入管理和快速筛选；"
            "跨批次查询、分类统计和汇总导出"
            "请使用“数据查询”模块。"
        )

        description.setWordWrap(True)

        description.setStyleSheet("color: #607080; " "font-size: 14px;")

        layout.addWidget(description)

        # =====================================================
        # 第一行筛选
        # =====================================================

        filter_layout_1 = QHBoxLayout()

        self.keyword_edit = QLineEdit()

        self.keyword_edit.setPlaceholderText("业务编号 / 工程名称 / 桩号")

        self.keyword_edit.setMinimumWidth(220)

        self.department_filter = QComboBox()
        self.department_filter.setMinimumWidth(130)

        self.office_filter = QComboBox()
        self.office_filter.setMinimumWidth(130)

        self.canal_filter = QComboBox()
        self.canal_filter.setMinimumWidth(150)

        filter_layout_1.addWidget(QLabel("关键词："))

        filter_layout_1.addWidget(self.keyword_edit)

        filter_layout_1.addWidget(QLabel("基层处："))

        filter_layout_1.addWidget(self.department_filter)

        filter_layout_1.addWidget(QLabel("水管所："))

        filter_layout_1.addWidget(self.office_filter)

        filter_layout_1.addWidget(QLabel("渠系："))

        filter_layout_1.addWidget(self.canal_filter)

        layout.addLayout(filter_layout_1)

        # =====================================================
        # 第二行筛选
        # =====================================================

        filter_layout_2 = QHBoxLayout()

        self.status_filter = QComboBox()

        self.status_filter.addItem(
            "全部状态",
            None,
        )

        self.status_filter.addItem(
            "草稿",
            "draft",
        )

        self.status_filter.addItem(
            "录入完成",
            "completed",
        )

        self.grade_filter = QComboBox()

        self.grade_filter.addItem(
            "全部类别",
            None,
        )

        for grade in (
            "A",
            "B",
            "C",
            "D",
        ):
            self.grade_filter.addItem(
                grade,
                grade,
            )

        search_button = QPushButton("查询")

        search_button.clicked.connect(self.apply_filters)

        reset_button = QPushButton("重置")

        reset_button.clicked.connect(self.reset_filters)

        self.keyword_edit.returnPressed.connect(self.apply_filters)

        filter_layout_2.addWidget(QLabel("状态："))

        filter_layout_2.addWidget(self.status_filter)

        filter_layout_2.addWidget(QLabel("工程状况类别："))

        filter_layout_2.addWidget(self.grade_filter)

        filter_layout_2.addWidget(search_button)

        filter_layout_2.addWidget(reset_button)

        filter_layout_2.addStretch()

        layout.addLayout(filter_layout_2)

        # =====================================================
        # 轻量统计
        # =====================================================

        self.count_label = QLabel()

        self.count_label.setStyleSheet("font-size: 14px; " "color: #52606d;")

        layout.addWidget(self.count_label)

        # =====================================================
        # 表格
        # =====================================================

        self.table = QTableWidget()

        self.table.setColumnCount(10)

        self.table.setHorizontalHeaderLabels(
            [
                "业务编号",
                "工程名称",
                "基层处",
                "水管所",
                "渠系",
                "桩号",
                "工程状况类别",
                "调查时间",
                "状态",
                "修改时间",
            ]
        )

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setAlternatingRowColors(True)

        self.table.cellDoubleClicked.connect(self.open_record)

        widths = [
            155,
            180,
            130,
            130,
            150,
            120,
            105,
            110,
            90,
            160,
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
    # 数据加载
    # =========================================================

    def load_data(self):
        self.current_context = get_current_context()

        if not self.current_context or self.current_context["batch_id"] is None:
            self.all_records = []
            self.filtered_records = []

            self.table.setRowCount(0)

            self.count_label.setText("当前没有可用调查批次。")

            self._refresh_filter_options()

            return

        self.all_records = get_engineering_survey_query_records(
            project_id=(self.current_context["project_id"]),
            survey_batch_id=(self.current_context["batch_id"]),
            form_code="form_2_3",
        )

        self._refresh_filter_options()

        # 数据刷新后保留当前筛选条件。
        self.apply_filters()

    # =========================================================
    # 筛选选项
    # =========================================================

    def _set_filter_values(
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

    def _refresh_filter_options(self):
        self._set_filter_values(
            self.department_filter,
            [record["department_name"] for record in self.all_records],
            "全部基层处",
        )

        self._set_filter_values(
            self.office_filter,
            [record["office_name"] for record in self.all_records],
            "全部水管所",
        )

        self._set_filter_values(
            self.canal_filter,
            [record["canal_name"] for record in self.all_records],
            "全部渠系",
        )

    # =========================================================
    # 筛选
    # =========================================================

    def apply_filters(self):
        keyword = self.keyword_edit.text().strip().casefold()

        department = self.department_filter.currentData()

        office = self.office_filter.currentData()

        canal = self.canal_filter.currentData()

        status = self.status_filter.currentData()

        grade = self.grade_filter.currentData()

        result = []

        for record in self.all_records:
            # -------------------------
            # 关键词
            # -------------------------

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

            # -------------------------
            # 基层处
            # -------------------------

            if department is not None and record["department_name"] != department:
                continue

            # -------------------------
            # 水管所
            # -------------------------

            if office is not None and record["office_name"] != office:
                continue

            # -------------------------
            # 渠系
            # -------------------------

            if canal is not None and record["canal_name"] != canal:
                continue

            # -------------------------
            # 状态
            # -------------------------

            if status is not None and record["record_status"] != status:
                continue

            # -------------------------
            # A / B / C / D
            # -------------------------

            if grade is not None and record["overall_grade"] != grade:
                continue

            result.append(record)

        self.filtered_records = result

        self._render_records(self.filtered_records)

        self._update_statistics(self.filtered_records)

    def reset_filters(self):
        self.keyword_edit.clear()

        self.department_filter.setCurrentIndex(0)

        self.office_filter.setCurrentIndex(0)

        self.canal_filter.setCurrentIndex(0)

        self.status_filter.setCurrentIndex(0)

        self.grade_filter.setCurrentIndex(0)

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
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                record["record_status"],
                record["record_status"],
            )

            values = [
                record["business_code"],
                record["asset_name"],
                record["department_name"],
                record["office_name"],
                record["canal_name"],
                record["engineering_position"],
                record["overall_grade"] or "",
                record["survey_date"],
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

    # =========================================================
    # 轻量统计
    # =========================================================

    def _update_statistics(
        self,
        records,
    ):
        draft_count = sum(1 for record in records if record["record_status"] == "draft")

        completed_count = sum(
            1 for record in records if record["record_status"] == "completed"
        )

        grade_counts = {
            "A": 0,
            "B": 0,
            "C": 0,
            "D": 0,
        }

        ungraded_count = 0

        for record in records:
            grade = record["overall_grade"]

            if grade in grade_counts:
                grade_counts[grade] += 1
            else:
                ungraded_count += 1

        self.count_label.setText(
            f"当前批次共 "
            f"{len(self.all_records)} 条"
            f"  |  当前筛选 "
            f"{len(records)} 条"
            f"  |  草稿 "
            f"{draft_count}"
            f"  |  已完成 "
            f"{completed_count}"
            f"  |  A "
            f"{grade_counts['A']}"
            f"  |  B "
            f"{grade_counts['B']}"
            f"  |  C "
            f"{grade_counts['C']}"
            f"  |  D "
            f"{grade_counts['D']}"
            f"  |  未定 "
            f"{ungraded_count}"
        )

    # =========================================================
    # 删除
    # =========================================================

    def delete_selected_record(self):
        """
        删除当前选中的附表2.3调查记录。

        草稿和已完成记录均允许删除。
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

        if id_item is None:
            return

        survey_record_id = id_item.data(Qt.ItemDataRole.UserRole)

        if survey_record_id is None:
            return

        business_code = id_item.text().strip()

        asset_name_item = self.table.item(
            row,
            1,
        )

        stake_item = self.table.item(
            row,
            5,
        )

        status_item = self.table.item(
            row,
            8,
        )

        asset_name = (
            asset_name_item.text().strip() if asset_name_item is not None else ""
        )

        stake_text = stake_item.text().strip() if stake_item is not None else ""

        status_text = status_item.text().strip() if status_item is not None else ""

        reply = QMessageBox.question(
            self,
            "确认删除调查记录",
            (
                "确定要永久删除这条"
                "渡槽（座槽）调查记录吗？\n\n"
                f"工程名称：{asset_name}\n"
                f"业务编号：{business_code}\n"
                f"桩号：{stake_text}\n"
                f"当前状态：{status_text}\n\n"
                "删除后，该记录的全部分项评价"
                "也会同时删除。\n"
                "如果该工程已经没有其他调查记录，"
                "工程台账中的工程对象也会一并删除。\n\n"
                "此操作无法从软件中恢复。"
            ),
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = delete_engineering_survey_record(
                survey_record_id=int(survey_record_id),
                form_code="form_2_3",
            )

            if result["asset_deleted"]:
                extra_message = (
                    "\n\n该工程已无其他调查记录，" "对应工程台账对象也已删除。"
                )
            else:
                extra_message = "\n\n该工程仍有其他调查记录，" "工程台账对象已保留。"

            QMessageBox.information(
                self,
                "删除成功",
                ("渡槽（座槽）调查记录" "已删除。" f"{extra_message}"),
            )

            self.load_data()

        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                str(error),
            )

    # =========================================================
    # Excel 正式原表导出
    # =========================================================

    def export_original_excel(
        self,
    ):
        """
        将当前选中的一条附表2.3
        渡槽（座槽）调查记录，
        导出为正式原表格式。
        """

        # =====================================================
        # 1. 当前选中记录
        # =====================================================

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "未选择记录",
                (
                    "请先在列表中选择一条"
                    "渡槽（座槽）调查记录，"
                    "再导出附表2.3正式原表。"
                ),
            )
            return

        # C1已经冻结：
        #
        # 第0列 = 业务编号，
        # 并在 UserRole 中保存 survey_record_id
        #
        # 第1列 = 工程名称

        id_item = self.table.item(
            row,
            0,
        )

        name_item = self.table.item(
            row,
            1,
        )

        if id_item is None:
            return

        survey_record_id = id_item.data(Qt.ItemDataRole.UserRole)

        if survey_record_id is None:
            return

        business_code = id_item.text().strip()

        asset_name = name_item.text().strip() if name_item is not None else "渡槽"

        # =====================================================
        # 2. 默认文件名
        # =====================================================

        safe_asset_name = asset_name or "渡槽"

        safe_business_code = business_code or "未编号"

        invalid_chars = '\\/:*?"<>|'

        for char in invalid_chars:
            safe_asset_name = safe_asset_name.replace(
                char,
                "_",
            )

            safe_business_code = safe_business_code.replace(
                char,
                "_",
            )

        default_name = (
            "附表2.3_"
            "渡槽（座槽）工程状况调查表_"
            f"{safe_business_code}_"
            f"{safe_asset_name}.xlsx"
        )

        # =====================================================
        # 3. 保存位置
        # =====================================================

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出附表2.3正式原表",
            default_name,
            "Excel 工作簿 (*.xlsx)",
        )

        if not file_path:
            return

        # =====================================================
        # 4. 正式导出
        # =====================================================

        try:
            result = export_aqueduct_original_form(
                survey_record_id=int(survey_record_id),
                file_path=file_path,
            )

            QMessageBox.information(
                self,
                "导出成功",
                (
                    "附表2.3正式原表已导出。\n\n"
                    f"工程名称："
                    f"{result['asset_name']}\n"
                    f"业务编号："
                    f"{result['business_code']}\n\n"
                    f"保存位置：\n"
                    f"{file_path}"
                ),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "导出失败",
                ("附表2.3正式原表" "导出失败。\n\n" f"{error}"),
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

        record_id = item.data(Qt.ItemDataRole.UserRole)

        if record_id is None:
            return

        self.edit_requested.emit(int(record_id))
