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
from services.survey_task_package_reader import (
    inspect_survey_task_package,
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
    - 上方“基层处 / 管理单位 / 渠系 / 调查表”决定成果包范围；
    - 只取 completed 工程调查记录；
    - 可选关联一个 .ydtask；
    - 不执行数据库导入。
    """

    def __init__(
        self,
        *,
        context_provider,
        scope_provider,
        output_parent_provider=None,
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

        self._source_task_uid = None
        self._source_task_info = None

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
            "数据交换成果包（.ydresult）用于把当前成果范围中的已完成工程调查记录、"
            "工程对象、分项评价和托管影像打包移交。"
            "本功能只生成/检查成果包，不执行跨数据库导入。"
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #607080;"
        )
        root.addWidget(description)

        form = QFormLayout()

        self.result_name_edit = (
            QLineEdit()
        )
        self.result_name_edit.setPlaceholderText(
            "例如：通远水管所2026调查成果"
        )

        self.creator_edit = QLineEdit()
        self.creator_edit.setPlaceholderText(
            "可选"
        )

        self.notes_edit = QLineEdit()
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

        task_row = QHBoxLayout()

        self.task_value_label = QLabel(
            "未关联来源任务（当前集中录入可不关联）"
        )
        self.task_value_label.setWordWrap(
            True
        )
        self.task_value_label.setStyleSheet(
            "color: #607080;"
        )

        self.choose_task_button = QPushButton(
            "关联来源任务（可选）"
        )
        self.clear_task_button = QPushButton(
            "清除关联"
        )
        self.clear_task_button.setEnabled(
            False
        )

        self.choose_task_button.clicked.connect(
            self.choose_source_task
        )
        self.clear_task_button.clicked.connect(
            self.clear_source_task
        )

        task_row.addWidget(
            self.task_value_label,
            1,
        )
        task_row.addWidget(
            self.choose_task_button
        )
        task_row.addWidget(
            self.clear_task_button
        )

        root.addLayout(task_row)

        scope_row = QHBoxLayout()

        self.scope_summary_label = QLabel(
            "当前范围尚未检查。"
        )
        self.scope_summary_label.setWordWrap(
            True
        )


        scope_row.addWidget(
            self.scope_summary_label,
            1,
        )

        root.addLayout(scope_row)

        action_row = QHBoxLayout()

        self.inspect_button = QPushButton(
            "检查已有 .ydresult"
        )
        self.export_button = QPushButton(
            "导出当前范围 .ydresult"
        )

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

            self.scope_summary_label.setText(
                (
                    "当前筛选范围可打包 "
                    f"{len(record_ids)} 条已完成工程调查记录。"
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

    # =========================================================
    # optional task link
    # =========================================================

    def choose_source_task(self):
        selected_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "关联调查任务包",
                "",
                (
                    "调查任务包 (*.ydtask);;"
                    "所有文件 (*)"
                ),
            )
        )

        if not selected_path:
            return None

        inspection = (
            inspect_survey_task_package(
                selected_path
            )
        )

        if not inspection.valid:
            QMessageBox.warning(
                self,
                "任务包检查未通过",
                inspection.format_text(),
            )
            return None

        try:
            identity = (
                self._current_local_identity()
            )

            manifest = (
                inspection.manifest
                or {}
            )

            if (
                manifest.get(
                    "project_uid"
                )
                != identity[
                    "project_uid"
                ]
            ):
                raise ValueError(
                    "所选任务包不属于当前项目。"
                )

            if (
                manifest.get(
                    "survey_batch_uid"
                )
                != identity[
                    "survey_batch_uid"
                ]
            ):
                raise ValueError(
                    "所选任务包不属于当前调查批次。"
                )

            task = inspection.task or {}

            self._source_task_uid = (
                manifest.get(
                    "task_uid"
                )
            )
            self._source_task_info = {
                "path": str(
                    selected_path
                ),
                "task": task,
            }

            task_name = (
                task.get(
                    "task_name"
                )
                or self._source_task_uid
                or "已关联任务"
            )

            self.task_value_label.setText(
                (
                    "已关联："
                    f"{task_name}"
                )
            )
            self.clear_task_button.setEnabled(
                True
            )

            self.status_label.setText(
                "任务包关联成功。"
            )

            return self._source_task_uid

        except Exception as error:
            QMessageBox.warning(
                self,
                "无法关联任务包",
                str(error),
            )
            return None

    def clear_source_task(self):
        self._source_task_uid = None
        self._source_task_info = None

        self.task_value_label.setText(
            "未关联来源任务（当前集中录入可不关联）"
        )
        self.clear_task_button.setEnabled(
            False
        )
        self.status_label.setText(
            "已清除任务包关联。"
        )

    def _validate_linked_task_scope(
        self,
        record_ids,
    ):
        if not self._source_task_info:
            return

        task = (
            self._source_task_info[
                "task"
            ]
        )

        assignment = (
            task.get(
                "assignment"
            )
            if isinstance(
                task,
                dict,
            )
            else None
        )
        scope = (
            task.get(
                "scope"
            )
            if isinstance(
                task,
                dict,
            )
            else None
        )

        if not isinstance(
            assignment,
            dict,
        ) or not isinstance(
            scope,
            dict,
        ):
            raise ValueError(
                "已关联任务包缺少任务范围信息。"
            )

        office_uid = (
            assignment.get(
                "organization_unit_uid"
            )
        )
        selected_canal_uids = set(
            scope.get(
                "selected_canal_uids"
            )
            or []
        )

        placeholders = ",".join(
            "?"
            for _ in record_ids
        )

        with database.get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    sr.id,
                    ou.organization_unit_uid,
                    cu.canal_unit_uid
                FROM survey_records AS sr
                LEFT JOIN organization_units AS ou
                  ON ou.id = sr.organization_unit_id
                LEFT JOIN canal_units AS cu
                  ON cu.id = sr.canal_unit_id
                WHERE sr.id IN (
                    {placeholders}
                )
                """,
                record_ids,
            ).fetchall()

        for row in rows:
            if (
                office_uid
                and row[
                    "organization_unit_uid"
                ]
                != office_uid
            ):
                raise ValueError(
                    "当前成果范围包含不属于已关联任务管理单位的调查记录。"
                )

            if (
                selected_canal_uids
                and row[
                    "canal_unit_uid"
                ]
                not in selected_canal_uids
            ):
                raise ValueError(
                    "当前成果范围包含不在已关联任务渠系范围内的调查记录。"
                )

    # =========================================================
    # export / inspect
    # =========================================================

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
            return

        try:
            identity = (
                self._current_local_identity()
            )

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
                    "当前成果范围没有已完成工程调查记录。"
                )

            self._validate_linked_task_scope(
                record_ids
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
                    source_task_uid=(
                        self._source_task_uid
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
                "正在生成 .ydresult，"
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

    @Slot(object)
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
