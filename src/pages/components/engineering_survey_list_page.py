from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
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
    delete_engineering_survey_record,
    get_current_context,
    get_engineering_survey_query_records,
)


class EngineeringSurveyListPage(QWidget):
    """
    附表2工程现状调查当前批次公共列表页。

    本类只负责工程调查列表层面的公共行为：
    - 当前批次数据加载；
    - 关键词和组织机构筛选；
    - 状态和工程状况类别筛选；
    - 轻量统计；
    - 表格选择和双击打开；
    - 删除调查记录；
    - 正式原表导出的公共交互流程。

    各附表仍自行定义：
    - form_code；
    - 页面文字；
    - 表格列；
    - 一条记录如何显示；
    - 如有需要，特殊查询/删除方式；
    - 正式原表实际导出函数。

    本类仅服务附表2工程现状调查，
    不作为附表1综合调查的公共基类。
    """

    new_requested = Signal()
    back_requested = Signal()
    edit_requested = Signal(int)

    # =========================================================
    # 子类必须/可以配置的内容
    # =========================================================

    FORM_CODE = ""

    PAGE_TITLE = ""
    NEW_BUTTON_TEXT = "新增调查"

    KEYWORD_PLACEHOLDER = "业务编号 / 工程名称 / 工程位置"

    POSITION_LABEL = "工程位置"

    TABLE_HEADERS = ()
    TABLE_WIDTHS = ()

    # 当前2.1～2.9均为 A/B/C/D。
    # 后续2.10等三级评价表可以单独覆盖。
    GRADE_OPTIONS = (
        "A",
        "B",
        "C",
        "D",
    )

    # 现有2.3列表显示A/B/C/D统计；
    # 2.1、2.2当前仅显示录入进度。
    # 迁移时保持各表原行为。
    SHOW_GRADE_STATISTICS = True

    EXPORT_FILENAME_PREFIX = "工程调查表"
    EXPORT_FALLBACK_ASSET_NAME = "工程"

    def __init__(self):
        super().__init__()

        self._validate_configuration()

        self.current_context = None

        self.all_records = []
        self.filtered_records = []

        self.init_ui()
        self.load_data()

    # =========================================================
    # 配置检查
    # =========================================================

    def _validate_configuration(self):
        if not self.FORM_CODE:
            raise ValueError("工程调查列表页必须设置 FORM_CODE。")

        if not self.TABLE_HEADERS:
            raise ValueError("工程调查列表页必须设置 TABLE_HEADERS。")

        if len(self.TABLE_HEADERS) != len(self.TABLE_WIDTHS):
            raise ValueError("TABLE_HEADERS 与 TABLE_WIDTHS " "数量必须一致。")

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

        new_button = QPushButton(self.NEW_BUTTON_TEXT)
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

        title = QLabel(self.PAGE_TITLE)

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

        self.keyword_edit.setPlaceholderText(self.KEYWORD_PLACEHOLDER)

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

        for grade in self.GRADE_OPTIONS:
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

        self.count_label.setStyleSheet("font-size: 14px; " "color: #52606d;")

        layout.addWidget(self.count_label)

        # =====================================================
        # 表格
        # =====================================================

        self.table = QTableWidget()

        self.table.setColumnCount(len(self.TABLE_HEADERS))

        self.table.setHorizontalHeaderLabels(list(self.TABLE_HEADERS))

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setAlternatingRowColors(True)

        self.table.cellDoubleClicked.connect(self.open_record)

        for column, width in enumerate(self.TABLE_WIDTHS):
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

        self.all_records = self._load_records()

        self._refresh_filter_options()

        # 数据刷新后保留当前筛选条件。
        self.apply_filters()

    def _load_records(self):
        """
        默认使用工程调查统一查询。

        现有旧表如仍使用专属查询函数，
        后续迁移时可以在子类覆盖本方法，
        不要求同时修改数据库层。
        """

        current_context = self.current_context

        if current_context is None:
            return []

        return get_engineering_survey_query_records(
            project_id=(current_context["project_id"]),
            survey_batch_id=(current_context["batch_id"]),
            form_code=self.FORM_CODE,
        )

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

    def _keyword_values(self, record):
        """
        默认工程调查关键词字段。

        单桩号工程以及统一工程查询结果
        可以直接使用。
        """

        return [
            record["business_code"],
            record["asset_name"],
            record["engineering_position"],
        ]

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
                matched = any(
                    keyword in str(value or "").casefold()
                    for value in self._keyword_values(record)
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

    def _build_table_values(
        self,
        record,
    ):
        """
        子类负责定义一条记录在表格中如何显示。
        """

        raise NotImplementedError

    def _render_records(
        self,
        records,
    ):
        self.table.setRowCount(len(records))

        for row_index, record in enumerate(records):
            values = self._build_table_values(record)

            if len(values) != len(self.TABLE_HEADERS):
                raise ValueError("列表行数据数量与表格列数量不一致。")

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
        draft_count = sum(1 for record in records if record["record_status"] == "draft")

        completed_count = sum(
            1 for record in records if record["record_status"] == "completed"
        )

        parts = [
            f"当前批次共 " f"{len(self.all_records)} 条",
            f"当前筛选 {len(records)} 条",
            f"草稿 {draft_count}",
            f"已完成 {completed_count}",
        ]

        if self.SHOW_GRADE_STATISTICS:
            grade_counts = {grade: 0 for grade in self.GRADE_OPTIONS}

            ungraded_count = 0

            for record in records:
                grade = record["overall_grade"]

                if grade in grade_counts:
                    grade_counts[grade] += 1
                else:
                    ungraded_count += 1

            for grade in self.GRADE_OPTIONS:
                parts.append(f"{grade} " f"{grade_counts[grade]}")

            parts.append(f"未定 {ungraded_count}")

        self.count_label.setText("  |  ".join(parts))

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

    def _get_selected_record(self):
        survey_record_id = self._get_selected_record_id()

        if survey_record_id is None:
            return None

        for record in self.all_records:
            if int(record["survey_record_id"]) == survey_record_id:
                return record

        return None

    # =========================================================
    # 删除
    # =========================================================

    def _position_text(self, record):
        return str(record["engineering_position"] or "")

    def _delete_record(
        self,
        survey_record_id,
    ):
        """
        默认使用工程调查统一删除能力。

        旧表迁移时如需保留专属删除函数，
        子类可以覆盖。
        """

        return delete_engineering_survey_record(
            survey_record_id=(survey_record_id),
            form_code=self.FORM_CODE,
        )

    def delete_selected_record(self):
        selected_record = self._get_selected_record()

        if selected_record is None:
            QMessageBox.warning(
                self,
                "未选择记录",
                "请先在列表中选择一条调查记录。",
            )
            return

        survey_record_id = int(selected_record["survey_record_id"])

        business_code = str(selected_record["business_code"] or "")

        asset_name = str(selected_record["asset_name"] or "")

        position_text = self._position_text(selected_record)

        status_text = {
            "draft": "草稿",
            "completed": "录入完成",
        }.get(
            selected_record["record_status"],
            selected_record["record_status"],
        )

        reply = QMessageBox.question(
            self,
            "确认删除调查记录",
            (
                "确定要永久删除这条调查记录吗？\n\n"
                f"名称：{asset_name}\n"
                f"业务编号：{business_code}\n"
                f"{self.POSITION_LABEL}："
                f"{position_text}\n"
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
            result = self._delete_record(survey_record_id)

            if result["asset_deleted"]:
                extra_message = (
                    "\n\n该工程已无其他调查记录，" "对应工程台账对象也已删除。"
                )
            else:
                extra_message = "\n\n该工程仍有其他调查记录，" "工程台账对象已保留。"

            QMessageBox.information(
                self,
                "删除成功",
                ("调查记录已删除。" f"{extra_message}"),
            )

            self.load_data()

        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                str(error),
            )

    # =========================================================
    # 正式原表导出
    # =========================================================

    def _safe_filename_part(
        self,
        value,
    ):
        text = str(value or "")

        invalid_chars = '\\/:*?"<>|'

        for char in invalid_chars:
            text = text.replace(
                char,
                "_",
            )

        return text

    def _export_original_form(
        self,
        survey_record_id,
        file_path,
    ):
        """
        子类负责调用本附表正式原表导出函数。
        """

        raise NotImplementedError

    def export_original_excel(self):
        selected_record = self._get_selected_record()

        if selected_record is None:
            QMessageBox.warning(
                self,
                "未选择记录",
                ("请先在列表中选择一条" "调查记录，再导出正式原表。"),
            )
            return

        survey_record_id = int(selected_record["survey_record_id"])

        business_code = str(selected_record["business_code"] or "")

        asset_name = str(
            selected_record["asset_name"] or self.EXPORT_FALLBACK_ASSET_NAME
        )

        safe_business_code = self._safe_filename_part(business_code or "未编号")

        safe_asset_name = self._safe_filename_part(asset_name)

        default_name = (
            f"{self.EXPORT_FILENAME_PREFIX}_"
            f"{safe_business_code}_"
            f"{safe_asset_name}.xlsx"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出正式原表",
            default_name,
            "Excel 工作簿 (*.xlsx)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"

        try:
            self._export_original_form(
                survey_record_id,
                file_path,
            )

            QMessageBox.information(
                self,
                "导出成功",
                (
                    "正式原表已导出。\n\n"
                    f"名称：{asset_name}\n"
                    f"业务编号：{business_code}\n\n"
                    f"保存位置：\n"
                    f"{file_path}"
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
