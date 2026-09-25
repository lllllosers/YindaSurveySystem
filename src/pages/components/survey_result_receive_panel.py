from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.survey_result_import import (
    import_survey_result_package,
)
from services.survey_result_import_preflight import (
    preflight_survey_result_import,
)


class SurveyResultImportWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        package_path,
        *,
        accept_updates=False,
    ):
        super().__init__()
        self.package_path = Path(
            package_path
        )
        self.accept_updates = bool(
            accept_updates
        )

    @Slot()
    def run(self):
        try:
            result = (
                import_survey_result_package(
                    self.package_path,
                    accept_updates=(
                        self.accept_updates
                    ),
                )
            )
        except Exception as error:
            self.failed.emit(
                str(error)
            )
            return

        self.finished.emit(
            result
        )


class SurveyResultReceivePanel(QWidget):
    """
    下级 .ydresult 成果接收面板。

    Stage 12.8：
    - 选择成果包；
    - 调用 Stage 12.5 只读检查；
    - 展示新增 / 已存在 / 冲突；
    - 仅在检查通过且存在新增数据时允许正式导入；
    - 正式导入调用 Stage 12.7 事务化导入核心；
    - 导入完成后发出 result_imported 信号。
    """

    result_imported = Signal(object)

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self._last_report = None
        self._last_package_path = None

        self._import_thread = None
        self._import_worker = None

        self._init_ui()
        self._reset_summary()

    def _init_ui(self):
        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root.setSpacing(
            10
        )

        description = QLabel(
            "用于接收下级调查端或管理单位提交的 .ydresult。"
            "选择成果包后，系统会先进行只读检查；"
            "只有不存在必须处理的问题且确有新增数据时，"
            "才允许正式导入。"
        )
        description.setObjectName("workflowLead")
        description.setWordWrap(
            True
        )
        description.setStyleSheet(
            "color: #607080;"
        )
        root.addWidget(
            description
        )

        action_row = QHBoxLayout()

        self.preflight_button = QPushButton(
            "选择成果包并检查"
        )
        self.preflight_button.setProperty("uiRole", "secondary")
        self.preflight_button.clicked.connect(
            self.choose_and_preflight
        )

        self.import_button = QPushButton(
            "正式导入成果"
        )
        self.import_button.setProperty("uiRole", "primary")
        self.import_button.setEnabled(
            False
        )
        self.import_button.clicked.connect(
            self.import_current_package
        )


        action_row.addWidget(self.preflight_button)
        action_row.addStretch()
        action_row.addWidget(self.import_button)
        root.addLayout(
            action_row
        )

        self.package_label = QLabel(
            "尚未选择成果包"
        )
        self.package_label.setObjectName("workflowSummary")
        self.package_label.setWordWrap(
            True
        )
        self.package_label.setStyleSheet(
            "color: #52606d;"
        )
        root.addWidget(
            self.package_label
        )

        summary_form = QFormLayout()
        summary_form.setHorizontalSpacing(18)
        summary_form.setVerticalSpacing(10)

        self.overall_label = QLabel(
            "-"
        )
        self.asset_label = QLabel(
            "-"
        )
        self.record_label = QLabel(
            "-"
        )
        self.inspection_label = QLabel(
            "-"
        )
        self.media_label = QLabel(
            "-"
        )

        for label in (
            self.overall_label,
            self.asset_label,
            self.record_label,
            self.inspection_label,
            self.media_label,
        ):
            label.setWordWrap(
                True
            )

        summary_form.addRow(
            "检查结论：",
            self.overall_label,
        )
        summary_form.addRow(
            "工程：",
            self.asset_label,
        )
        summary_form.addRow(
            "调查记录：",
            self.record_label,
        )
        summary_form.addRow(
            "分项评价：",
            self.inspection_label,
        )
        summary_form.addRow(
            "影像：",
            self.media_label,
        )

        root.addLayout(
            summary_form
        )

        self.details_edit = QPlainTextEdit()
        self.details_edit.setObjectName("workflowDetails")
        self.details_edit.setReadOnly(
            True
        )
        self.details_edit.setMinimumHeight(
            150
        )
        self.details_edit.setPlaceholderText(
            "检查明细将在这里显示。"
        )

        root.addWidget(
            self.details_edit
        )

        self.status_label = QLabel(
            "等待检查。"
        )
        self.status_label.setObjectName("workflowStatus")
        self.status_label.setWordWrap(
            True
        )
        self.status_label.setStyleSheet(
            "color: #52606d;"
        )
        root.addWidget(
            self.status_label
        )

    def _reset_summary(self):
        self._last_report = None
        self._last_package_path = None

        self.import_button.setEnabled(
            False
        )

        self.package_label.setText(
            "尚未选择成果包"
        )
        self.overall_label.setText(
            "-"
        )
        self.asset_label.setText(
            "-"
        )
        self.record_label.setText(
            "-"
        )
        self.inspection_label.setText(
            "-"
        )
        self.media_label.setText(
            "-"
        )
        self.details_edit.clear()
        self.status_label.setText(
            "等待检查。"
        )
        self.status_label.setStyleSheet(
            "color: #52606d;"
        )

    def choose_and_preflight(
        self,
    ):
        if self._import_thread is not None:
            return None

        selected_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "选择调查成果包",
                "",
                (
                    "调查成果包 (*.ydresult);;"
                    "所有文件 (*)"
                ),
            )
        )

        if not selected_path:
            return None

        return self.preflight_path(
            selected_path
        )

    def preflight_path(
        self,
        package_path,
    ):
        """
        对指定 .ydresult 检查。

        检查始终只读，不会写数据库。
        """

        if self._import_thread is not None:
            return None

        path = Path(
            package_path
        )

        self.preflight_button.setEnabled(
            False
        )
        self.import_button.setEnabled(
            False
        )

        self.status_label.setText(
            "正在检查成果包..."
        )
        self.status_label.setStyleSheet(
            "color: #52606d;"
        )

        try:
            report = (
                preflight_survey_result_import(
                    path
                )
            )

        except Exception as error:
            self._last_report = None
            self._last_package_path = None

            self.package_label.setText(
                str(path)
            )
            self.overall_label.setText(
                "检查失败"
            )
            self.asset_label.setText(
                "-"
            )
            self.record_label.setText(
                "-"
            )
            self.inspection_label.setText(
                "-"
            )
            self.media_label.setText(
                "-"
            )
            self.details_edit.setPlainText(
                str(error)
            )
            self.status_label.setText(
                "成果包无法通过基础检查。"
            )
            self.status_label.setStyleSheet(
                "color: #a33;"
            )

            QMessageBox.warning(
                self,
                "成果包检查失败",
                str(error),
            )

            return None

        finally:
            self.preflight_button.setEnabled(
                True
            )

        self._last_report = report
        self._last_package_path = path

        self.package_label.setText(
            str(path)
        )

        self.asset_label.setText(
            (
                f"新增 {report.new_assets}，"
                f"已存在 {report.existing_assets}，"
                f"待更新 {report.updated_assets}，"
                f"旧版本 {report.stale_assets}"
            )
        )
        self.record_label.setText(
            (
                f"新增 {report.new_records}，"
                f"已存在 {report.existing_records}，"
                f"待更新 {report.updated_records}，"
                f"旧版本 {report.stale_records}"
            )
        )
        self.inspection_label.setText(
            (
                f"新增 {report.new_inspections}，"
                f"已存在 {report.existing_inspections}，"
                f"随修订更新 {report.updated_inspections}"
            )
        )
        self.media_label.setText(
            (
                f"新增 {report.new_media}，"
                f"已存在 {report.existing_media}"
            )
        )

        if not report.can_import:
            conclusion = (
                f"存在 {report.error_count} 个错误，"
                "当前禁止导入。"
            )
            status = (
                "检查未通过。请先处理身份冲突、"
                "同版本内容冲突或上下级双向修改。"
            )
            style = (
                "color: #a33;"
            )

        elif not report.has_importable_changes:
            if (
                report.stale_assets
                or report.stale_records
            ):
                conclusion = (
                    "检查通过；没有需要新增或更新的数据。"
                )
                status = (
                    "一致数据将跳过；旧版本不会回退上级数据。"
                )
            else:
                conclusion = (
                    "检查通过；成果内容均已存在。"
                )
                status = (
                    "该成果包没有需要新增或更新的数据，"
                    "正式导入阶段将按重复成果处理。"
                )
            style = (
                "color: #52606d;"
            )

        elif report.has_updates:
            conclusion = (
                "检查通过；检测到下级更新，确认后可以导入。"
            )
            status = (
                "新增数据将直接合并；待更新数据只有在本次"
                "确认后才覆盖最近一次已接收的下级版本。"
                "系统会先创建安全备份。"
            )
            style = (
                "color: #2f6f44;"
            )

        else:
            conclusion = (
                "检查通过，可以正式导入。"
            )
            status = (
                "已存在且一致的数据将自动跳过，"
                "只导入本次新增内容。"
                "系统会先创建安全备份。"
            )
            style = (
                "color: #2f6f44;"
            )

        if report.warning_count:
            conclusion += (
                f" 另有 {report.warning_count} 条需要注意的信息。"
            )
        elif report.info_count:
            conclusion += (
                f" 另有 {report.info_count} 条说明。"
            )

        self.overall_label.setText(
            conclusion
        )
        self.details_edit.setPlainText(
            report.format_user_text()
        )
        self.status_label.setText(
            status
        )
        self.status_label.setStyleSheet(
            style
        )

        self.import_button.setEnabled(
            (
                report.can_import
                and report.has_importable_changes
            )
        )

        return report

    def import_current_package(
        self,
    ):
        if self._import_thread is not None:
            return None

        report = self._last_report
        package_path = self._last_package_path

        if (
            report is None
            or package_path is None
        ):
            QMessageBox.information(
                self,
                "请先检查成果包",
                (
                    "正式导入前必须先选择 .ydresult "
                    "并通过目标数据库检查。"
                ),
            )
            return None

        if not report.can_import:
            QMessageBox.warning(
                self,
                "当前成果包不可导入",
                (
                    "检查仍存在必须处理的问题，"
                    "请先处理冲突。"
                ),
            )
            return None

        if not report.has_importable_changes:
            QMessageBox.information(
                self,
                "没有可导入变更",
                (
                    "该成果包没有新增或需要更新的数据。"
                    "一致内容已存在；旧版本不会回退上级数据。"
                ),
            )
            return None

        reply = QMessageBox.question(
            self,
            "确认正式导入成果",
            (
                "系统将把当前成果包写入本地数据库，"
                "并在导入前自动创建数据库备份。\n\n"
                f"新增工程：{report.new_assets}\n"
                f"待更新工程：{report.updated_assets}\n"
                f"新增调查记录：{report.new_records}\n"
                f"待更新调查记录：{report.updated_records}\n"
                f"旧版本调查记录：{report.stale_records}（自动忽略）\n"
                f"新增分项评价：{report.new_inspections}\n"
                f"随修订更新分项评价：{report.updated_inspections}\n"
                f"新增影像：{report.new_media}\n\n"
                "已存在且一致的数据会自动跳过；"
                "旧版本不会覆盖当前数据。\n"
                "“待更新”表示下级修改了以前提交过的记录，"
                "本次确认后才会更新。\n\n"
                "导入过程中如果发生异常，"
                "系统不会保留未完成的更改，"
                "本次新安装的文件也会清理。\n\n"
                "是否继续？"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return None

        if report.has_updates:
            self._begin_import(
                package_path,
                accept_updates=True,
            )
        else:
            self._begin_import(
                package_path
            )

        return package_path

    def _begin_import(
        self,
        package_path,
        *,
        accept_updates=False,
    ):
        self.preflight_button.setEnabled(
            False
        )
        self.import_button.setEnabled(
            False
        )

        self.status_label.setText(
            (
                "正在创建安全备份并导入成果，"
                "请勿关闭程序..."
            )
        )
        self.status_label.setStyleSheet(
            "color: #52606d;"
        )

        thread = QThread(
            self
        )
        worker = SurveyResultImportWorker(
            package_path,
            accept_updates=accept_updates,
        )
        worker.moveToThread(
            thread
        )

        thread.started.connect(
            worker.run
        )
        worker.finished.connect(
            self._import_finished
        )
        worker.failed.connect(
            self._import_failed
        )
        worker.finished.connect(
            thread.quit
        )
        worker.failed.connect(
            thread.quit
        )
        thread.finished.connect(
            self._import_thread_finished
        )

        self._import_thread = thread
        self._import_worker = worker

        thread.start()

    @Slot(object)
    def _import_finished(
        self,
        result,
    ):
        self.import_button.setEnabled(
            False
        )

        if result.already_imported:
            headline = (
                "该成果包此前已经接收，"
                "本次没有重复写入。"
            )
        else:
            headline = (
                "成果导入完成。"
            )

        self.overall_label.setText(
            headline
        )

        self.asset_label.setText(
            (
                f"本次新增 {result.imported_assets}，"
                f"已存在 {result.existing_assets}，"
                f"已更新 {result.updated_assets}，"
                f"旧版本忽略 {result.stale_assets}"
            )
        )
        self.record_label.setText(
            (
                f"本次新增 {result.imported_records}，"
                f"已存在 {result.existing_records}，"
                f"已更新 {result.updated_records}，"
                f"旧版本忽略 {result.stale_records}"
            )
        )
        self.inspection_label.setText(
            (
                f"本次新增 {result.imported_inspections}，"
                f"已存在 {result.existing_inspections}，"
                f"随修订更新 {result.updated_inspections}"
            )
        )
        self.media_label.setText(
            (
                f"本次新增 {result.imported_media}，"
                f"已存在 {result.existing_media}"
            )
        )

        details = [
            headline,
        ]

        if result.backup_path is not None:
            details.extend(
                [
                    "",
                    (
                        "导入前备份："
                        f"{result.backup_path}"
                    ),
                ]
            )

        if (
            result.managed_package_path
            is not None
        ):
            details.append(
                (
                    "成果包保存位置："
                    f"{result.managed_package_path}"
                )
            )

        self.details_edit.setPlainText(
            "\n".join(
                details
            )
        )

        self.status_label.setText(
            (
                "成果已安全合并到当前项目。"
                "返回工程台账、数据查询或成果提交时"
                "即可读取合并后的数据。"
            )
        )
        self.status_label.setStyleSheet(
            "color: #2f6f44;"
        )

        self.result_imported.emit(
            result
        )

        QMessageBox.information(
            self,
            "成果导入完成",
            (
                f"{headline}\n\n"
                f"工程新增：{result.imported_assets}\n"
                f"工程更新：{result.updated_assets}\n"
                f"调查记录新增：{result.imported_records}\n"
                f"调查记录更新：{result.updated_records}\n"
                f"旧版本记录忽略：{result.stale_records}\n"
                f"分项评价新增：{result.imported_inspections}\n"
                f"分项评价更新：{result.updated_inspections}\n"
                f"影像新增：{result.imported_media}"
            ),
        )

    @Slot(str)
    def _import_failed(
        self,
        message,
    ):
        self.status_label.setText(
            (
                "成果导入失败。"
                "系统已恢复到导入前状态；"
                "本次新增的文件也已尝试清理。"
            )
        )
        self.status_label.setStyleSheet(
            "color: #a33;"
        )

        self.preflight_button.setEnabled(
            True
        )

        self.import_button.setEnabled(
            bool(
                self._last_report
                and self._last_report.can_import
                and self._last_report.has_new_data
            )
        )

        QMessageBox.warning(
            self,
            "成果导入失败",
            message,
        )

    @Slot()
    def _import_thread_finished(
        self,
    ):
        if self._import_worker is not None:
            self._import_worker.deleteLater()

        if self._import_thread is not None:
            self._import_thread.deleteLater()

        self._import_worker = None
        self._import_thread = None

        self.preflight_button.setEnabled(
            True
        )

    @property
    def last_report(
        self,
    ):
        return self._last_report

    @property
    def last_package_path(
        self,
    ):
        return self._last_package_path
