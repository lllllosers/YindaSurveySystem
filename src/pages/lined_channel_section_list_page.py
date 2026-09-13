from PySide6.QtCore import Qt, Signal
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
    delete_lined_channel_section_record,
    get_current_context,
    get_lined_channel_section_records,
)
from services.lined_channel_export import (
    export_lined_channel_original_form,
)


class LinedChannelSectionListPage(QWidget):
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

        new_button = QPushButton("新增渠道渠段调查")
        new_button.clicked.connect(self.new_requested.emit)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.load_data)

        delete_button = QPushButton("删除选中记录")
        delete_button.clicked.connect(self.delete_selected_record)

        export_button = QPushButton("导出结果")

        export_button.clicked.connect(self.export_original_excel)

        button_layout.addWidget(back_button)
        button_layout.addWidget(new_button)
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(export_button)
        button_layout.addWidget(delete_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # =====================================================
        # 标题
        # =====================================================

        title = QLabel("附表2.1 防渗衬砌渠道渠段工程状况调查记录")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        layout.addWidget(title)

        description = QLabel(
            "双击记录可打开调查表。"
            "本页用于当前批次录入管理和快速筛选；"
            "跨批次查询、分类统计和汇总导出"
            "请使用“数据查询”模块。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #607080;" "font-size: 14px;")

        layout.addWidget(description)

        # =====================================================
        # 第一行筛选
        # =====================================================

        filter_layout_1 = QHBoxLayout()

        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("业务编号 / 渠道名称 / 起止桩号")
        self.keyword_edit.setMinimumWidth(230)

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
        # 统计
        # =====================================================

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #52606d;" "font-size: 14px;")

        layout.addWidget(self.count_label)

        # =====================================================
        # 表格
        # =====================================================

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

        widths = [
            150,
            180,
            130,
            130,
            160,
            110,
            110,
            110,
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
    # 数据
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

        self.all_records = get_lined_channel_section_records(
            project_id=(self.current_context["project_id"]),
            survey_batch_id=(self.current_context["batch_id"]),
        )

        self._refresh_filter_options()

        self.apply_filters()

    # =========================================================
    # 筛选
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

    def apply_filters(self):
        keyword = self.keyword_edit.text().strip().casefold()

        department = self.department_filter.currentData()

        office = self.office_filter.currentData()

        canal = self.canal_filter.currentData()

        status = self.status_filter.currentData()

        grade = self.grade_filter.currentData()

        result = []

        for record in self.all_records:
            if keyword:
                keyword_values = [
                    record["business_code"],
                    record["asset_name"],
                    record["start_stake_text"],
                    record["end_stake_text"],
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

    # =========================================================
    # 统计
    # =========================================================

    def _update_statistics(
        self,
        records,
    ):
        """
        当前调查列表只显示录入进度。

        A/B/C/D等成果统计统一由
        “数据查询”模块负责。
        """

        draft_count = sum(1 for record in records if record["record_status"] == "draft")

        completed_count = sum(
            1 for record in records if record["record_status"] == "completed"
        )

        self.count_label.setText(
            f"当前批次共 "
            f"{len(self.all_records)} 条"
            f"  |  当前筛选 "
            f"{len(records)} 条"
            f"  |  草稿 "
            f"{draft_count}"
            f"  |  已完成 "
            f"{completed_count}"
        )

    # =========================================================
    # 当前选中记录
    # =========================================================

    def _get_selected_record_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(
            row,
            0,
        )

        if item is None:
            return None

        value = item.data(Qt.ItemDataRole.UserRole)

        if value is None:
            return None

        return int(value)

    # =========================================================
    # Excel 导出
    # =========================================================

    def export_original_excel(self):
        """
        导出当前选中记录为附表2.1原表。
        """

        survey_record_id = self._get_selected_record_id()

        if survey_record_id is None:
            QMessageBox.warning(
                self,
                "未选择记录",
                ("请先选择一条渠道渠段" "调查记录，再导出附表2.1原表。"),
            )
            return

        selected_record = next(
            (
                record
                for record in self.all_records
                if record["survey_record_id"] == survey_record_id
            ),
            None,
        )

        if selected_record is None:
            QMessageBox.warning(
                self,
                "导出失败",
                "没有找到当前选中的调查记录。",
            )
            return

        business_code = selected_record["business_code"] or ""

        asset_name = selected_record["asset_name"] or "渠道渠段"

        invalid_chars = '\\/:*?"<>|'

        safe_business_code = business_code

        safe_asset_name = asset_name

        for char in invalid_chars:
            safe_business_code = safe_business_code.replace(
                char,
                "_",
            )

            safe_asset_name = safe_asset_name.replace(
                char,
                "_",
            )

        default_name = (
            "附表2.1_防渗衬砌渠道渠段"
            "工程状况调查表_"
            f"{safe_business_code}_"
            f"{safe_asset_name}.xlsx"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出附表2.1原表",
            default_name,
            "Excel 工作簿 (*.xlsx)",
        )

        if not file_path:
            return

        if not (file_path.lower().endswith(".xlsx")):
            file_path += ".xlsx"

        try:
            result = export_lined_channel_original_form(
                survey_record_id=(survey_record_id),
                file_path=file_path,
            )

            QMessageBox.information(
                self,
                "导出成功",
                (
                    "附表2.1原表已导出。\n\n"
                    f"渠道名称："
                    f"{result['asset_name']}\n"
                    f"业务编号："
                    f"{result['business_code']}\n\n"
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
                    "如果该文件正在 Excel 中打开，"
                    "请先关闭文件后重新导出。"
                ),
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "导出失败",
                str(error),
            )

    # =========================================================
    # 删除
    # =========================================================

    def delete_selected_record(self):
        survey_record_id = self._get_selected_record_id()

        if survey_record_id is None:
            QMessageBox.warning(
                self,
                "未选择记录",
                "请先选择需要删除的调查记录。",
            )
            return

        selected_record = next(
            (
                record
                for record in self.all_records
                if record["survey_record_id"] == survey_record_id
            ),
            None,
        )

        if selected_record is None:
            QMessageBox.warning(
                self,
                "删除失败",
                "没有找到当前选中的调查记录。",
            )
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            (
                "确定删除这条渠道渠段调查记录吗？"
                "\n\n"
                f"渠道名称："
                f"{selected_record['asset_name']}\n"
                f"业务编号："
                f"{selected_record['business_code']}\n"
                f"渠段："
                f"{selected_record['start_stake_text']}"
                " ～ "
                f"{selected_record['end_stake_text']}\n\n"
                "如果该工程已没有其他调查记录，"
                "对应工程台账对象也会一并删除。"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = delete_lined_channel_section_record(survey_record_id)

            if result["asset_deleted"]:
                extra_text = "\n对应工程台账对象" "已同时删除。"
            else:
                extra_text = "\n工程台账对象仍有其他" "调查记录，因此予以保留。"

            QMessageBox.information(
                self,
                "删除成功",
                ("渠道渠段调查记录已删除。" f"{extra_text}"),
            )

            self.load_data()

        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                str(error),
            )

    # =========================================================
    # 打开
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
