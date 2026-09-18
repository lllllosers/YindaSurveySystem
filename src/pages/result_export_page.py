from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QStandardPaths,
    QThread,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database import (
    get_canal_units,
    get_current_context,
    get_departments,
    get_water_offices,
)
from forms.engineering.registry import (
    get_engineering_form_definitions,
)
from services.engineering_batch_export import (
    BatchExportRequest,
    build_batch_export_plan,
    execute_batch_export,
    sanitize_filename,
)
from services.engineering_result_preflight import (
    inspect_batch_export_plan,
)
from services.survey_scope import SurveyScope
from pages.components.survey_result_package_panel import SurveyResultPackagePanel
from pages.components.survey_result_receive_panel import SurveyResultReceivePanel


class BatchExportWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, plan):
        super().__init__()
        self.plan = plan

    @Slot()
    def run(self):
        try:
            result = execute_batch_export(
                self.plan
            )
        except Exception as error:
            self.failed.emit(str(error))
            return

        self.finished.emit(result)


class ResultExportPage(QWidget):
    """附表2正式成果批量导出页面。"""

    def __init__(self):
        super().__init__()

        self.current_context = None
        self.departments = []
        self.water_offices = []
        self.canals = []

        self._export_thread = None
        self._export_worker = None
        self._last_output_root = None

        self.init_ui()
        self.load_data()

    def init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(
            0, 0, 0, 0
        )
        page_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(
            True
        )
        self.scroll_area.setFrameShape(
            QScrollArea.Shape.NoFrame
        )

        self.scroll_content = QWidget()
        self.scroll_area.setWidget(
            self.scroll_content
        )
        page_layout.addWidget(
            self.scroll_area
        )

        root_layout = QVBoxLayout(
            self.scroll_content
        )
        root_layout.setContentsMargins(
            0, 0, 0, 0
        )
        root_layout.setSpacing(16)
        root_layout.setSizeConstraint(
            QLayout.SizeConstraint.SetMinimumSize
        )

        description = QLabel(
            "生成当前调查批次的附表2正式成果。"
            "正式成果默认只包含“录入完成”记录；"
            "草稿不会进入正式成果。"
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #607080; font-size: 14px;"
        )
        root_layout.addWidget(description)

        context_group = QGroupBox(
            "一、成果所属调查批次"
        )
        context_layout = QFormLayout(
            context_group
        )

        self.project_value_label = QLabel(
            "未选择项目"
        )
        self.batch_value_label = QLabel(
            "未选择调查批次"
        )

        context_layout.addRow(
            "当前项目：",
            self.project_value_label,
        )
        context_layout.addRow(
            "当前调查批次：",
            self.batch_value_label,
        )
        root_layout.addWidget(context_group)

        scope_group = QGroupBox(
            "二、成果范围"
        )
        scope_layout = QFormLayout(
            scope_group
        )

        self.department_combo = QComboBox()
        self.office_combo = QComboBox()
        self.canal_combo = QComboBox()
        self.form_combo = QComboBox()

        self.include_canal_descendants_check = (
            QCheckBox(
                "包含所选渠系的全部下级渠系"
            )
        )
        self.include_canal_descendants_check.setChecked(
            True
        )

        self.department_combo.currentIndexChanged.connect(
            self._department_changed
        )

        scope_layout.addRow(
            "基层处：",
            self.department_combo,
        )
        scope_layout.addRow(
            "水管所：",
            self.office_combo,
        )
        scope_layout.addRow(
            "渠系：",
            self.canal_combo,
        )
        scope_layout.addRow(
            "",
            self.include_canal_descendants_check,
        )
        scope_layout.addRow(
            "调查表：",
            self.form_combo,
        )
        root_layout.addWidget(scope_group)

        output_group = QGroupBox(
            "三、输出设置"
        )
        output_layout = QVBoxLayout(
            output_group
        )

        output_path_row = QHBoxLayout()

        self.output_parent_edit = QLineEdit()
        self.output_parent_edit.setReadOnly(
            True
        )

        browse_button = QPushButton(
            "选择成果保存位置"
        )
        browse_button.clicked.connect(
            self.choose_output_parent
        )

        output_path_row.addWidget(
            self.output_parent_edit,
            1,
        )
        output_path_row.addWidget(
            browse_button
        )
        output_layout.addLayout(
            output_path_row
        )

        self.create_zip_check = QCheckBox(
            "全部成果成功后，同时生成 ZIP 压缩包"
        )
        output_layout.addWidget(
            self.create_zip_check
        )

        output_note = QLabel(
            "系统将在所选位置自动新建本次成果目录，"
            "不会覆盖已有成果。"
        )
        output_note.setWordWrap(True)
        output_note.setStyleSheet(
            "color: #7a8793;"
        )
        output_layout.addWidget(output_note)

        root_layout.addWidget(output_group)

        action_row = QHBoxLayout()

        self.export_button = QPushButton(
            "预检并开始导出"
        )
        self.export_button.clicked.connect(
            self.start_export
        )

        self.open_output_button = QPushButton(
            "打开成果目录"
        )
        self.open_output_button.setEnabled(
            False
        )
        self.open_output_button.clicked.connect(
            self.open_output_directory
        )

        action_row.addWidget(
            self.export_button
        )
        action_row.addWidget(
            self.open_output_button
        )
        action_row.addStretch()
        root_layout.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        root_layout.addWidget(
            self.progress_bar
        )

        self.status_label = QLabel(
            "等待导出。"
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: #52606d;"
        )
        root_layout.addWidget(
            self.status_label
        )

        package_group = QGroupBox(
            "四、数据交换成果包（.ydresult）"
        )
        package_layout = QVBoxLayout(
            package_group
        )

        self.result_package_panel = (
            SurveyResultPackagePanel(
                context_provider=(
                    lambda: self.current_context
                ),
                scope_provider=(
                    self._build_scope
                ),
                output_parent_provider=(
                    lambda: (
                        self.output_parent_edit
                        .text()
                        .strip()
                    )
                ),
            )
        )

        package_layout.addWidget(
            self.result_package_panel
        )

        root_layout.addWidget(
            package_group
        )

        receive_group = QGroupBox(
            "五、接收下级成果包（.ydresult）"
        )
        receive_layout = QVBoxLayout(
            receive_group
        )

        self.result_receive_panel = (
            SurveyResultReceivePanel()
        )

        receive_layout.addWidget(
            self.result_receive_panel
        )

        self.result_receive_panel.result_imported.connect(
            lambda result: (
                self.result_package_panel.refresh_scope_summary()
            )
        )

        root_layout.addWidget(
            receive_group
        )

        # Stage 11.3e: auto refresh .ydresult scope
        self.department_combo.currentIndexChanged.connect(
            self.result_package_panel.refresh_scope_summary
        )
        self.office_combo.currentIndexChanged.connect(
            self.result_package_panel.refresh_scope_summary
        )
        self.canal_combo.currentIndexChanged.connect(
            self.result_package_panel.refresh_scope_summary
        )
        self.form_combo.currentIndexChanged.connect(
            self.result_package_panel.refresh_scope_summary
        )
        self.include_canal_descendants_check.toggled.connect(
            self.result_package_panel.refresh_scope_summary
        )

        root_layout.addStretch()

    def _context_value(
        self,
        key,
        default=None,
    ):
        if self.current_context is None:
            return default

        try:
            value = self.current_context[key]
        except (
            KeyError,
            IndexError,
            TypeError,
        ):
            return default

        return (
            default
            if value is None
            else value
        )

    def load_data(self):
        self.current_context = (
            get_current_context()
        )

        project_id = self._context_value(
            "project_id"
        )
        batch_id = self._context_value(
            "batch_id"
        )

        self.project_value_label.setText(
            str(
                self._context_value(
                    "project_name",
                    "未选择项目",
                )
            )
        )
        self.batch_value_label.setText(
            str(
                self._context_value(
                    "batch_name",
                    "未选择调查批次",
                )
            )
        )

        ready = (
            project_id is not None
            and batch_id is not None
        )

        self.export_button.setEnabled(ready)

        if not ready:
            self.status_label.setText(
                "当前没有可用的项目和调查批次。"
            )
            self.department_combo.clear()
            self.office_combo.clear()
            self.canal_combo.clear()
            self.form_combo.clear()
            return

        self.departments = list(
            get_departments()
        )
        self.water_offices = list(
            get_water_offices()
        )
        self.canals = list(
            get_canal_units()
        )

        self._load_department_options()
        self._load_canal_options()
        self._load_form_options()
        self._set_default_output_parent()

        self.status_label.setText(
            "已加载当前调查批次。"
            "请选择成果范围后开始导出。"
        )

    def _load_department_options(self):
        self.department_combo.blockSignals(
            True
        )
        self.department_combo.clear()
        self.department_combo.addItem(
            "全部基层处",
            None,
        )

        for department in self.departments:
            self.department_combo.addItem(
                department["name"],
                int(department["id"]),
            )

        self.department_combo.blockSignals(
            False
        )
        self._load_office_options()

    def _department_changed(self):
        self._load_office_options()

    def _load_office_options(self):
        current_value = (
            self.office_combo.currentData()
        )
        department_id = (
            self.department_combo.currentData()
        )

        self.office_combo.blockSignals(True)
        self.office_combo.clear()
        self.office_combo.addItem(
            "全部水管所",
            None,
        )

        department_names = {
            int(item["id"]): item["name"]
            for item in self.departments
        }

        for office in self.water_offices:
            parent_id = int(
                office["parent_id"]
            )

            if (
                department_id is not None
                and parent_id
                != int(department_id)
            ):
                continue

            display_name = office["name"]

            if department_id is None:
                display_name = (
                    f"{department_names.get(parent_id, '')}"
                    f" / {display_name}"
                )

            self.office_combo.addItem(
                display_name,
                int(office["id"]),
            )

        if current_value is not None:
            index = (
                self.office_combo
                .findData(current_value)
            )
            if index >= 0:
                self.office_combo.setCurrentIndex(
                    index
                )

        self.office_combo.blockSignals(False)

    def _canal_display_name(self, canal):
        names = []
        current = canal
        visited = set()

        by_id = {
            int(item["id"]): item
            for item in self.canals
        }

        while current is not None:
            current_id = int(current["id"])

            if current_id in visited:
                break

            visited.add(current_id)
            names.append(current["name"])

            parent_id = current["parent_id"]

            if parent_id is None:
                break

            current = by_id.get(
                int(parent_id)
            )

        names.reverse()

        return " / ".join(
            str(name)
            for name in names
        )

    def _load_canal_options(self):
        self.canal_combo.clear()
        self.canal_combo.addItem(
            "全部渠系",
            None,
        )

        for canal in self.canals:
            self.canal_combo.addItem(
                self._canal_display_name(
                    canal
                ),
                int(canal["id"]),
            )

    def _load_form_options(self):
        self.form_combo.clear()
        self.form_combo.addItem(
            "全部附表2工程调查表",
            None,
        )

        for definition in (
            get_engineering_form_definitions()
        ):
            self.form_combo.addItem(
                definition.display_name,
                definition.form_code,
            )

    def _set_default_output_parent(self):
        if self.output_parent_edit.text():
            return

        documents_path = (
            QStandardPaths.writableLocation(
                QStandardPaths
                .StandardLocation
                .DocumentsLocation
            )
        )

        if not documents_path:
            documents_path = str(
                Path.home()
            )

        self.output_parent_edit.setText(
            str(
                Path(documents_path)
                / "引大调查成果"
            )
        )

    def _build_scope(self):
        project_id = self._context_value(
            "project_id"
        )
        batch_id = self._context_value(
            "batch_id"
        )

        if (
            project_id is None
            or batch_id is None
        ):
            raise ValueError(
                "当前没有可用的项目和调查批次。"
            )

        department_id = (
            self.department_combo.currentData()
        )
        office_id = (
            self.office_combo.currentData()
        )
        canal_id = (
            self.canal_combo.currentData()
        )
        form_code = (
            self.form_combo.currentData()
        )

        if office_id is not None:
            organization_unit_ids = (
                int(office_id),
            )
        elif department_id is not None:
            organization_unit_ids = (
                int(department_id),
            )
        else:
            organization_unit_ids = ()

        return SurveyScope(
            project_id=int(project_id),
            survey_batch_id=int(batch_id),
            organization_unit_ids=(
                organization_unit_ids
            ),
            canal_unit_ids=(
                (int(canal_id),)
                if canal_id is not None
                else ()
            ),
            form_codes=(
                (str(form_code),)
                if form_code is not None
                else ()
            ),
            record_statuses=(
                "completed",
            ),
            include_organization_descendants=True,
            include_canal_descendants=(
                self
                .include_canal_descendants_check
                .isChecked()
            ),
        )

    def choose_output_parent(self):
        selected = (
            QFileDialog.getExistingDirectory(
                self,
                "选择成果保存位置",
                (
                    self.output_parent_edit
                    .text()
                    .strip()
                ),
            )
        )

        if selected:
            self.output_parent_edit.setText(
                selected
            )

    def _next_output_root(
        self,
        output_parent,
    ):
        batch_name = self._context_value(
            "batch_name",
            "当前调查批次",
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        base_name = sanitize_filename(
            (
                f"{batch_name}_"
                f"附表2成果_{timestamp}"
            )
        )

        candidate = (
            output_parent / base_name
        )

        index = 2

        while candidate.exists():
            candidate = (
                output_parent
                / f"{base_name}_{index}"
            )
            index += 1

        return candidate

    def start_export(self):
        if self._export_thread is not None:
            return

        output_parent_text = (
            self.output_parent_edit
            .text()
            .strip()
        )

        if not output_parent_text:
            QMessageBox.warning(
                self,
                "请选择保存位置",
                "请先选择成果保存位置。",
            )
            return

        output_parent = Path(
            output_parent_text
        )

        try:
            output_parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            request = BatchExportRequest(
                scope=self._build_scope(),
                output_root=(
                    self._next_output_root(
                        output_parent
                    )
                ),
                create_zip=(
                    self.create_zip_check
                    .isChecked()
                ),
            )

            self.status_label.setText(
                "正在预检成果范围……"
            )

            plan = build_batch_export_plan(
                request
            )

            preflight_report = (
                inspect_batch_export_plan(
                    plan
                )
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "成果预检失败",
                str(error),
            )
            self.status_label.setText(
                "成果预检失败。"
            )
            return

        if preflight_report.error_count:
            QMessageBox.warning(
                self,
                "成果预检未通过",
                (
                    "正式成果导出前发现"
                    f" {preflight_report.error_count} "
                    "个必须处理的影像错误。\n"
                    f"另有 "
                    f"{preflight_report.warning_count} "
                    "个警告。\n\n"
                    "错误修正后才能开始正式导出。"
                    "\n\n"
                    f"{preflight_report.format_preview()}"
                ),
            )

            self.status_label.setText(
                "成果预检未通过。"
            )
            return

        form_names = "、".join(
            (
                f"附表"
                f"{group.definition.form_number}"
            )
            for group in plan.groups
        )

        answer = QMessageBox.question(
            self,
            "确认导出正式成果",
            (
                "本次将生成正式成果：\n\n"
                f"记录数：{len(plan.records)} 条\n"
                f"调查表：{len(plan.groups)} 类\n"
                f"范围：{form_names}\n"
                f"影像预检：0 个错误，"
                f"{preflight_report.warning_count} "
                "个警告\n\n"
                + (
                    (
                        "以下警告不会阻止本次导出：\n"
                        f"{preflight_report.format_preview(limit=5)}"
                        "\n\n"
                    )
                    if preflight_report.warning_count
                    else ""
                )
                + "正式成果仅包含“录入完成”记录。\n"
                "是否开始导出？"
            ),
            (
                QMessageBox
                .StandardButton
                .Yes
                | QMessageBox
                .StandardButton
                .No
            ),
            QMessageBox.StandardButton.Yes,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            self.status_label.setText(
                "已取消导出。"
            )
            return

        self._last_output_root = (
            request.output_root
        )
        self.open_output_button.setEnabled(
            False
        )
        self._set_export_running(True)

        self.status_label.setText(
            "正在生成详细汇总、正式调查表"
            "和成果清单，请勿关闭程序……"
        )

        thread = QThread(self)
        worker = BatchExportWorker(plan)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(
            self._export_finished
        )
        worker.failed.connect(
            self._export_failed
        )
        worker.finished.connect(
            thread.quit
        )
        worker.failed.connect(
            thread.quit
        )
        thread.finished.connect(
            worker.deleteLater
        )
        thread.finished.connect(
            thread.deleteLater
        )
        thread.finished.connect(
            self._export_thread_finished
        )

        self._export_thread = thread
        self._export_worker = worker

        thread.start()

    def _set_export_running(
        self,
        running,
    ):
        for widget in (
            self.export_button,
            self.department_combo,
            self.office_combo,
            self.canal_combo,
            self.form_combo,
            self.include_canal_descendants_check,
            self.create_zip_check,
        ):
            widget.setEnabled(
                not running
            )

        self.progress_bar.setVisible(
            running
        )

        if running:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)

    @Slot(object)
    def _export_finished(
        self,
        result,
    ):
        self._set_export_running(False)

        self._last_output_root = (
            result.output_root
        )
        self.open_output_button.setEnabled(
            result.output_root.exists()
        )

        if result.completed:
            message = (
                "附表2正式成果导出完成。\n\n"
                f"正式调查记录："
                f"{result.total_records} 条\n"
                f"详细汇总："
                f"{result.summary_success_count} 个\n"
                f"正式原表："
                f"{result.original_success_count} 个\n"
                f"影像资料："
                f"{result.media_success_count} 个\n\n"
                f"成果目录：\n"
                f"{result.output_root}"
            )

            if result.archive_path is not None:
                message += (
                    "\n\nZIP：\n"
                    f"{result.archive_path}"
                )

            self.status_label.setText(
                "正式成果导出完成。"
            )
            QMessageBox.information(
                self,
                "成果导出完成",
                message,
            )
        else:
            self.status_label.setText(
                "成果导出存在失败项，"
                "请查看成果清单和"
                "“导出未完成.txt”。"
            )
            QMessageBox.warning(
                self,
                "成果导出未完成",
                (
                    "本次导出存在失败项，"
                    "系统没有生成完整成果 ZIP。\n\n"
                    f"失败项：{len(result.errors)}\n"
                    f"成果目录：\n"
                    f"{result.output_root}\n\n"
                    "请查看“00_成果清单.xlsx”"
                    "和“导出未完成.txt”。"
                ),
            )

    @Slot(str)
    def _export_failed(
        self,
        error_message,
    ):
        self._set_export_running(False)

        if (
            self._last_output_root
            is not None
            and self._last_output_root.exists()
        ):
            self.open_output_button.setEnabled(
                True
            )

        self.status_label.setText(
            "成果导出失败。"
        )
        QMessageBox.warning(
            self,
            "成果导出失败",
            error_message,
        )

    @Slot()
    def _export_thread_finished(self):
        self._export_thread = None
        self._export_worker = None

    def open_output_directory(self):
        if self._last_output_root is None:
            return

        if not self._last_output_root.exists():
            QMessageBox.warning(
                self,
                "成果目录不存在",
                "没有找到最近一次成果目录。",
            )
            return

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(self._last_output_root)
            )
        )
