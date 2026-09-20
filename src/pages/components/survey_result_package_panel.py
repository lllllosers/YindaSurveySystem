from __future__ import annotations

from pathlib import Path
import re

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
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import database

from services.engineering_batch_export import (
    load_scope_records,
)
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_result_package_reader import (
    inspect_survey_result_package,
)
from services.survey_department_aggregate import (
    preview_current_department_aggregate,
)


_INVALID_FILENAME_CHARS = re.compile(
    r'[<>:"/\\|?*\x00-\x1f]'
)


def _safe_filename(value):
    text = str(value or "").strip()
    text = _INVALID_FILENAME_CHARS.sub(
        "_",
        text,
    ).strip(" .")
    return text or "调查成果"


class SurveyResultPackageWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, request):
        super().__init__()
        self.request = request

    @Slot()
    def run(self):
        try:
            result = (
                export_survey_result_package(
                    self.request
                )
            )

            inspection = (
                inspect_survey_result_package(
                    result.output_path
                )
            )

            if not inspection.valid:
                raise ValueError(
                    "成果包已生成，但导出后完整性检查未通过。\n\n"
                    + inspection.format_text()
                )

        except Exception as error:
            self.failed.emit(str(error))
            return

        self.finished.emit(result)


class SurveyResultPackagePanel(QWidget):
    """
    成果导出页中的 .ydresult 数据交换面板。

    直接复用父页面现有 SurveyScope：
    - 上方筛选范围决定成果包范围；
    - 只取 completed 工程调查记录；
    - 任务来源从 SurveyRecord.source_task_uid 自动汇总；
    - 用户不再手动关联 .ydtask；
    - 不执行数据库导入。
    """

    def __init__(
        self,
        *,
        context_provider,
        scope_provider,
        output_parent_provider=None,
        workspace_provider=None,
        parent=None,
    ):
        super().__init__(parent)

        self.context_provider = (
            context_provider
        )
        self.scope_provider = (
            scope_provider
        )
        self.output_parent_provider = (
            output_parent_provider
        )
        self.workspace_provider = (
            workspace_provider
        )

        self._export_thread = None
        self._export_worker = None

        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root.setSpacing(10)

        description = QLabel(
            "调查成果包（.ydresult）用于把当前范围中的录入完成工程调查记录、"
            "工程对象、分项评价和托管影像打包移交。"
            "任务来源由调查记录自动追踪，无需手动关联 .ydtask。"
        )
        description.setObjectName("workflowLead")
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #607080;"
        )
        root.addWidget(description)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        self.result_name_edit = (
            QLineEdit()
        )
        self.result_name_edit.setProperty("uiWidthRole", "form")
        self.result_name_edit.setPlaceholderText(
            "例如：通远水管所2026调查成果"
        )

        self.creator_edit = QLineEdit()
        self.creator_edit.setProperty("uiWidthRole", "form")
        self.creator_edit.setPlaceholderText(
            "可选"
        )

        self.notes_edit = QLineEdit()
        self.notes_edit.setProperty("uiWidthRole", "form")
        self.notes_edit.setPlaceholderText(
            "可选：交接说明"
        )

        form.addRow(
            "成果包名称：",
            self.result_name_edit,
        )
        form.addRow(
            "制作人：",
            self.creator_edit,
        )
        form.addRow(
            "备注：",
            self.notes_edit,
        )

        root.addLayout(form)

        self.scope_summary_label = QLabel(
            "当前范围尚未检查。"
        )
        self.scope_summary_label.setObjectName("workflowSummary")
        self.scope_summary_label.setWordWrap(
            True
        )
        root.addWidget(
            self.scope_summary_label
        )

        action_row = QHBoxLayout()

        self.inspect_button = QPushButton(
            "检查已有成果包"
        )
        self.inspect_button.setProperty("uiRole", "secondary")
        self.export_button = QPushButton(
            "生成调查成果包"
        )
        self.export_button.setProperty("uiRole", "primary")

        self.inspect_button.clicked.connect(
            self.inspect_existing_package
        )
        self.export_button.clicked.connect(
            self.export_current_scope
        )

        action_row.addWidget(
            self.inspect_button
        )
        action_row.addStretch()
        action_row.addWidget(
            self.export_button
        )

        root.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status_label = QLabel(
            "等待操作。"
        )
        self.status_label.setObjectName("workflowStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: #52606d;"
        )
        root.addWidget(
            self.status_label
        )

    # =========================================================
    # context / scope
    # =========================================================

    def _context(self):
        context = (
            self.context_provider()
            if self.context_provider
            else None
        )

        if not context:
            raise ValueError(
                "当前没有可用项目和调查批次。"
            )

        return context

    def _workspace(self):
        if not self.workspace_provider:
            return None

        return self.workspace_provider()

    @staticmethod
    def _context_value(
        context,
        key,
        default=None,
    ):
        try:
            value = context[key]
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

    def _current_local_identity(self):
        context = self._context()

        project_id = self._context_value(
            context,
            "project_id",
        )
        batch_id = self._context_value(
            context,
            "batch_id",
        )

        if (
            project_id is None
            or batch_id is None
        ):
            raise ValueError(
                "当前没有可用项目和调查批次。"
            )

        with database.get_connection() as connection:
            project = connection.execute(
                """
                SELECT
                    project_uid,
                    name
                FROM projects
                WHERE id = ?
                """,
                (
                    int(project_id),
                ),
            ).fetchone()

            batch = connection.execute(
                """
                SELECT
                    survey_batch_uid,
                    batch_name
                FROM survey_batches
                WHERE id = ?
                """,
                (
                    int(batch_id),
                ),
            ).fetchone()

        if (
            project is None
            or batch is None
        ):
            raise ValueError(
                "当前项目或调查批次不存在。"
            )

        return {
            "project_id": int(project_id),
            "project_uid": (
                project["project_uid"]
            ),
            "project_name": (
                project["name"]
            ),
            "batch_id": int(batch_id),
            "survey_batch_uid": (
                batch["survey_batch_uid"]
            ),
            "batch_name": (
                batch["batch_name"]
            ),
        }

    def _scope_records(self):
        scope = self.scope_provider()

        records = tuple(
            load_scope_records(
                scope
            )
        )

        return (
            scope,
            records,
        )

    @staticmethod
    def _record_ids(records):
        return tuple(
            int(
                record[
                    "survey_record_id"
                ]
            )
            for record in records
        )

    def refresh_scope_summary(self):
        try:
            identity = (
                self._current_local_identity()
            )

            workspace = (
                self._workspace()
            )

            if (
                workspace is not None
                and str(
                    workspace.get(
                        "target_unit_type"
                    )
                    or ""
                ).strip()
                == "department"
            ):
                preview = (
                    preview_current_department_aggregate()
                )

                if (
                    not self.result_name_edit
                    .text()
                    .strip()
                ):
                    self.result_name_edit.setText(
                        (
                            f"{identity['batch_name']}"
                            "处级汇总成果"
                        )
                    )

                self.export_button.setText(
                    "生成处级汇总成果包"
                )

                self.scope_summary_label.setText(
                    (
                        "当前为处级父任务汇总模式："
                        f"可汇总 {preview.record_count} 条记录，"
                        f"来源子任务 {preview.source_task_count} 个，"
                        f"涉及水管所 {preview.source_office_count} 个，"
                        f"分管范围 {preview.management_scope_count} 项。"
                        "上方成果范围筛选不会改变 .ydresult 的父任务授权边界。"
                    )
                )

                self.export_button.setEnabled(
                    bool(
                        preview.survey_record_ids
                    )
                )

                return tuple(
                    preview.survey_record_ids
                )

            _, records = (
                self._scope_records()
            )

            record_ids = (
                self._record_ids(
                    records
                )
            )

            if (
                not self.result_name_edit
                .text()
                .strip()
            ):
                self.result_name_edit.setText(
                    (
                        f"{identity['batch_name']}"
                        "调查成果"
                    )
                )

            self.export_button.setText(
                "生成调查成果包"
            )

            self.scope_summary_label.setText(
                (
                    "当前筛选范围可打包 "
                    f"{len(record_ids)} 条录入完成工程调查记录。"
                )
            )

            self.export_button.setEnabled(
                bool(record_ids)
            )

            return record_ids

        except Exception as error:
            self.scope_summary_label.setText(
                f"当前范围不可用：{error}"
            )
            self.export_button.setEnabled(
                False
            )
            return ()

    def _default_output_path(
        self,
        result_name,
    ):
        parent_path = None

        if self.output_parent_provider:
            raw_parent = (
                self.output_parent_provider()
            )

            if raw_parent:
                parent_path = Path(
                    str(raw_parent)
                )

        if parent_path is None:
            parent_path = Path.home()

        return (
            parent_path
            / (
                _safe_filename(
                    result_name
                )
                + ".ydresult"
            )
        )

    def export_current_scope(self):
        if self._export_thread is not None:
            return None

        try:
            identity = (
                self._current_local_identity()
            )

            workspace = (
                self._workspace()
            )

            submission_task_uid = ""

            if (
                workspace is not None
                and str(
                    workspace.get(
                        "target_unit_type"
                    )
                    or ""
                ).strip()
                == "department"
            ):
                preview = (
                    preview_current_department_aggregate()
                )

                record_ids = tuple(
                    preview.survey_record_ids
                )

                submission_task_uid = (
                    preview.parent_task_uid
                )

                if not record_ids:
                    raise ValueError(
                        "当前处级父任务下没有可汇总的已完成调查记录。"
                    )

                result_name = (
                    self.result_name_edit
                    .text()
                    .strip()
                    or (
                        f"{identity['batch_name']}"
                        "处级汇总成果"
                    )
                )

            else:
                _, records = (
                    self._scope_records()
                )

                record_ids = (
                    self._record_ids(
                        records
                    )
                )

                if not record_ids:
                    raise ValueError(
                        "当前成果范围没有录入完成的工程调查记录。"
                    )

                result_name = (
                    self.result_name_edit
                    .text()
                    .strip()
                    or (
                        f"{identity['batch_name']}"
                        "调查成果"
                    )
                )

                if (
                    workspace is not None
                    and str(
                        workspace.get(
                            "target_unit_type"
                        )
                        or ""
                    ).strip()
                    == "water_office"
                ):
                    submission_task_uid = str(
                        workspace.get(
                            "task_uid"
                        )
                        or ""
                    ).strip()

            default_path = (
                self._default_output_path(
                    result_name
                )
            )

            selected_path, _ = (
                QFileDialog.getSaveFileName(
                    self,
                    "导出调查成果包",
                    str(default_path),
                    (
                        "调查成果包 (*.ydresult);;"
                        "所有文件 (*)"
                    ),
                )
            )

            if not selected_path:
                return None

            request = (
                SurveyResultExportRequest(
                    project_id=(
                        identity[
                            "project_id"
                        ]
                    ),
                    survey_batch_id=(
                        identity[
                            "batch_id"
                        ]
                    ),
                    survey_record_ids=(
                        record_ids
                    ),
                    output_path=Path(
                        selected_path
                    ),
                    result_name=(
                        result_name
                    ),
                    creator=(
                        self.creator_edit
                        .text()
                        .strip()
                    ),
                    notes=(
                        self.notes_edit
                        .text()
                        .strip()
                    ),
                    submission_task_uid=(
                        submission_task_uid
                    ),
                )
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "无法导出成果包",
                str(error),
            )
            return None

        self.export_button.setEnabled(
            False
        )
        self.inspect_button.setEnabled(
            False
        )

        self.progress.setRange(
            0,
            0,
        )
        self.progress.setVisible(
            True
        )
        self.status_label.setText(
            (
                "正在生成调查成果包，"
                "并校验调查数据和托管影像..."
            )
        )

        thread = QThread(self)
        worker = (
            SurveyResultPackageWorker(
                request
            )
        )
        worker.moveToThread(thread)

        thread.started.connect(
            worker.run
        )
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
            self._export_thread_finished
        )

        self._export_thread = thread
        self._export_worker = worker

        thread.start()

        return request

    def _export_finished(
        self,
        result,
    ):
        self.progress.setVisible(
            False
        )
        self.status_label.setText(
            (
                "成果包导出完成："
                f"{result.output_path}"
            )
        )

        QMessageBox.information(
            self,
            "成果包导出完成",
            (
                "调查成果包已生成并通过完整性检查。\n\n"
                f"调查记录：{result.survey_record_count} 条\n"
                f"工程对象：{result.engineering_asset_count} 个\n"
                f"分项评价：{result.inspection_result_count} 项\n"
                f"影像：{result.media_count} 个\n\n"
                f"文件：{result.output_path}"
            ),
        )

    @Slot(str)
    def _export_failed(
        self,
        message,
    ):
        self.progress.setVisible(
            False
        )
        self.status_label.setText(
            "成果包导出失败。"
        )

        QMessageBox.warning(
            self,
            "成果包导出失败",
            message,
        )

    @Slot()
    def _export_thread_finished(self):
        if self._export_worker is not None:
            self._export_worker.deleteLater()

        if self._export_thread is not None:
            self._export_thread.deleteLater()

        self._export_worker = None
        self._export_thread = None

        self.inspect_button.setEnabled(
            True
        )

        self.refresh_scope_summary()

    def inspect_existing_package(self):
        selected_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "检查调查成果包",
                "",
                (
                    "调查成果包 (*.ydresult);;"
                    "所有文件 (*)"
                ),
            )
        )

        if not selected_path:
            return None

        inspection = (
            inspect_survey_result_package(
                selected_path
            )
        )

        if inspection.valid:
            QMessageBox.information(
                self,
                "成果包检查通过",
                inspection.format_text(),
            )
        else:
            QMessageBox.warning(
                self,
                "成果包检查未通过",
                inspection.format_text(),
            )

        return inspection

    def showEvent(self, event):
        super().showEvent(event)

        if (
            self._export_thread
            is None
        ):
            self.refresh_scope_summary()
