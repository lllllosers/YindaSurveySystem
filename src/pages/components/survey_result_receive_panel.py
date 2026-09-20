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
    - 调用 Stage 12.5 只读预检；
    - 展示新增 / 已存在 / 冲突；
    - 仅在预检通过且存在新增数据时允许正式导入；
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
            "选择成果包后，系统会先进行只读预检；"
            "只有不存在阻断性冲突且确有新增数据时，"
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
            "选择成果包并预检"
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
            "预检结论：",
            self.overall_label,
        )
        summary_form.addRow(
            "工程对象：",
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
            "预检明细将在这里显示。"
        )

        root.addWidget(
            self.details_edit
        )

        self.status_label = QLabel(
            "等待预检。"
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
            "等待预检。"
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
        对指定 .ydresult 预检。

        预检始终只读，不会写数据库。
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
            "正在预检成果包..."
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
                "预检失败"
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
                "成果包预检失败",
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
                "预检未通过。请先处理身份冲突、"
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
                    "预检通过；没有需要写入的新增或修订数据。"
                )
                status = (
                    "一致数据将跳过；旧版本不会回退上级数据。"
                )
            else:
                conclusion = (
                    "预检通过；成果内容均已存在。"
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
                "预检通过；检测到下级修订，确认后可以导入。"
            )
            status = (
                "新增数据将直接合并；待更新数据只有在本次"
                "确认后才覆盖最近一次已接收的下级版本。"
                "系统会先创建安全备份并使用事务执行。"
            )
            style = (
                "color: #2f6f44;"
            )

        else:
            conclusion = (
                "预检通过，可以正式导入（增量合并）。"
            )
            status = (
                "已存在且一致的数据将自动跳过，"
                "只写入本次新增内容。"
                "系统会先创建安全备份并使用事务执行。"
            )
            style = (
                "color: #2f6f44;"
            )

        if report.warning_count:
            conclusion += (
                f" 另有 {report.warning_count} 个警告。"
            )

        self.overall_label.setText(
            conclusion
        )
        self.details_edit.setPlainText(
            report.format_text()
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
                "请先预检成果包",
                (
                    "正式导入前必须先选择 .ydresult "
                    "并通过目标数据库预检。"
                ),
            )
            return None

        if not report.can_import:
            QMessageBox.warning(
                self,
                "当前成果包不可导入",
                (
                    "预检仍存在阻断性错误，"
                    "请先处理冲突。"
                ),
            )
            return None

        if not report.has_importable_changes:
            QMessageBox.information(
                self,
                "没有可导入变更",
                (
                    "该成果包没有新增或可确认修订数据。"
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
                f"新增工程对象：{report.new_assets}\n"
                f"待更新工程对象：{report.updated_assets}\n"
                f"新增调查记录：{report.new_records}\n"
                f"待更新调查记录：{report.updated_records}\n"
                f"旧版本调查记录：{report.stale_records}（自动忽略）\n"
                f"新增分项评价：{report.new_inspections}\n"
                f"随修订更新分项评价：{report.updated_inspections}\n"
                f"新增影像：{report.new_media}\n\n"
                "已存在且一致的数据会自动跳过；"
                "旧版本不会覆盖当前数据。\n"
                "待更新数据表示下级提交了更高 revision，"
                "本次确认后才会写入。\n\n"
                "导入过程中如果发生异常，"
                "数据库事务会回滚，"
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
            "",
            f"package_uid：{result.package_uid}",
            f"result_uid：{result.result_uid}",
        ]

        if result.backup_path is not None:
            details.extend(
                [
                    "",
                    (
                        "导入前数据库备份："
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
                    "托管成果包："
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
                "成果已安全写入当前数据库。"
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
                f"工程对象新增：{result.imported_assets}\n"
                f"工程对象更新：{result.updated_assets}\n"
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
                "数据库事务已经回滚；"
                "如有本次新安装文件，系统已尝试清理。"
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
