from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.survey_task_package_reader import (
    load_survey_task_package,
)
from services.survey_task_workspace import (
    get_current_task_workspace,
    receive_survey_task_package,
)


class SurveyTaskReceivePanel(QWidget):
    """
    .ydtask 接收入口。

    Stage 12.2 只负责：
    - 预览并确认任务；
    - 调用 Stage 12.1 接收核心；
    - 展示当前本地任务工作区；
    - 接收成功后通知父页面刷新。

    暂不在这里实现工程录入范围强制，
    该部分进入下一阶段统一落到录入链路。
    """

    task_received = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._init_ui()
        self.refresh_current_task()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root.setSpacing(8)

        group = QGroupBox(
            "接收调查任务"
        )
        layout = QVBoxLayout(group)

        description = QLabel(
            "收到 .ydtask 后，从这里接收。"
            "系统会校验任务包，将项目、调查批次、管理单位和分管范围"
            "建立为本机当前任务工作区，并把原任务包复制到本地托管目录。"
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            "color: #607080;"
        )
        layout.addWidget(
            description
        )

        action_row = QHBoxLayout()

        self.receive_button = QPushButton(
            "接收 .ydtask"
        )
        self.receive_button.clicked.connect(
            self.receive_task_package
        )

        self.refresh_button = QPushButton(
            "刷新当前任务"
        )
        self.refresh_button.clicked.connect(
            self.refresh_current_task
        )

        action_row.addWidget(
            self.receive_button
        )
        action_row.addWidget(
            self.refresh_button
        )
        action_row.addStretch()

        layout.addLayout(
            action_row
        )

        current_group = QGroupBox(
            "当前本地任务工作区"
        )
        current_form = QFormLayout(
            current_group
        )

        self.task_name_label = QLabel(
            "未接收调查任务"
        )
        self.project_batch_label = QLabel(
            "-"
        )
        self.organization_label = QLabel(
            "-"
        )
        self.scope_summary_label = QLabel(
            "-"
        )
        self.received_at_label = QLabel(
            "-"
        )

        for label in (
            self.task_name_label,
            self.project_batch_label,
            self.organization_label,
            self.scope_summary_label,
            self.received_at_label,
        ):
            label.setWordWrap(True)
            label.setTextInteractionFlags(
                label.textInteractionFlags()
            )

        current_form.addRow(
            "任务：",
            self.task_name_label,
        )
        current_form.addRow(
            "项目 / 批次：",
            self.project_batch_label,
        )
        current_form.addRow(
            "管理单位：",
            self.organization_label,
        )
        current_form.addRow(
            "任务分管范围：",
            self.scope_summary_label,
        )
        current_form.addRow(
            "接收时间：",
            self.received_at_label,
        )

        layout.addWidget(
            current_group
        )

        self.status_label = QLabel(
            "等待接收任务。"
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: #52606d;"
        )
        layout.addWidget(
            self.status_label
        )

        root.addWidget(
            group
        )

    @staticmethod
    def _task_preview_text(
        contents,
    ):
        task = contents.task or {}

        project = (
            task.get("project")
            if isinstance(
                task.get("project"),
                dict,
            )
            else {}
        )

        batch = (
            task.get("survey_batch")
            if isinstance(
                task.get("survey_batch"),
                dict,
            )
            else {}
        )

        assignment = (
            task.get("assignment")
            if isinstance(
                task.get("assignment"),
                dict,
            )
            else {}
        )

        scope = (
            task.get("scope")
            if isinstance(
                task.get("scope"),
                dict,
            )
            else {}
        )

        task_name = (
            str(
                task.get(
                    "task_name"
                )
                or "未命名任务"
            )
        )

        project_name = (
            str(
                project.get("name")
                or "-"
            )
        )

        batch_name = (
            str(
                batch.get(
                    "batch_name"
                )
                or "-"
            )
        )

        department_name = (
            str(
                assignment.get(
                    "department_name"
                )
                or "-"
            )
        )

        organization_name = (
            str(
                assignment.get(
                    "organization_name"
                )
                or "-"
            )
        )

        scope_count = scope.get(
            "selected_management_scope_count"
        )

        if scope_count is None:
            scope_count = len(
                scope.get(
                    "selected_management_scope_uids"
                )
                or []
            )

        return (
            f"任务：{task_name}\n"
            f"项目：{project_name}\n"
            f"调查批次：{batch_name}\n"
            f"基层处：{department_name}\n"
            f"管理单位：{organization_name}\n"
            f"分管范围：{scope_count} 项\n\n"
            "确认接收并切换到该任务工作区吗？"
        )

    def receive_task_package(self):
        selected_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "接收调查任务",
                "",
                (
                    "调查任务包 (*.ydtask);;"
                    "所有文件 (*)"
                ),
            )
        )

        if not selected_path:
            return None

        try:
            contents = (
                load_survey_task_package(
                    selected_path
                )
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "任务包检查未通过",
                str(error),
            )
            return None

        answer = QMessageBox.question(
            self,
            "确认接收调查任务",
            self._task_preview_text(
                contents
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.Yes,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return None

        self.receive_button.setEnabled(
            False
        )

        try:
            result = (
                receive_survey_task_package(
                    Path(
                        selected_path
                    )
                )
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "接收调查任务失败",
                str(error),
            )
            self.status_label.setText(
                "调查任务接收失败。"
            )
            return None

        finally:
            self.receive_button.setEnabled(
                True
            )

        self.refresh_current_task()

        if result.already_received:
            action_text = (
                "该任务此前已经接收，"
                "现已切换为当前任务工作区。"
            )
        else:
            action_text = (
                "调查任务已接收并设为当前任务工作区。"
            )

        context_lines = []

        if result.created_project:
            context_lines.append(
                "已按任务稳定 UID 创建本地项目。"
            )

        if result.created_batch:
            context_lines.append(
                "已按任务稳定 UID 创建本地调查批次。"
            )

        extra_text = (
            "\n".join(
                context_lines
            )
        )

        message = (
            f"{action_text}\n\n"
            f"任务：{result.task_name}\n"
            f"分管范围："
            f"{result.selected_management_scope_count} 条\n"
            f"本地托管："
            f"{result.managed_package_path}"
        )

        if extra_text:
            message += (
                "\n\n"
                + extra_text
            )

        QMessageBox.information(
            self,
            "调查任务已就绪",
            message,
        )

        self.status_label.setText(
            "当前任务工作区已更新。"
        )

        self.task_received.emit()

        return result

    def refresh_current_task(self):
        try:
            workspace = (
                get_current_task_workspace()
            )
        except Exception as error:
            self.task_name_label.setText(
                "当前任务读取失败"
            )
            self.project_batch_label.setText(
                "-"
            )
            self.organization_label.setText(
                "-"
            )
            self.scope_summary_label.setText(
                "-"
            )
            self.received_at_label.setText(
                "-"
            )
            self.status_label.setText(
                f"无法读取当前任务：{error}"
            )
            return None

        if not workspace:
            self.task_name_label.setText(
                "未接收调查任务"
            )
            self.project_batch_label.setText(
                "-"
            )
            self.organization_label.setText(
                "-"
            )
            self.scope_summary_label.setText(
                "-"
            )
            self.received_at_label.setText(
                "-"
            )
            self.status_label.setText(
                "当前数据库没有已激活的调查任务工作区。"
            )
            return None

        self.task_name_label.setText(
            str(
                workspace[
                    "task_name"
                ]
            )
        )

        self.project_batch_label.setText(
            (
                f"{workspace['project_name']}"
                " / "
                f"{workspace['batch_name']}"
            )
        )

        self.organization_label.setText(
            str(
                workspace[
                    "organization_name"
                ]
            )
        )

        scopes = tuple(
            workspace.get(
                "management_scopes"
            )
            or ()
        )

        labels = []

        for item in scopes:
            canal_name = str(
                item.get(
                    "canal_name"
                )
                or "-"
            )

            range_mode = str(
                item.get(
                    "range_mode"
                )
                or ""
            )

            if range_mode == "whole":
                range_text = "全渠"
            elif (
                range_mode
                == "segment_unknown"
            ):
                range_text = "边界未知"
            else:
                start = (
                    item.get(
                        "start_stake_text"
                    )
                    or item.get(
                        "start_stake_value"
                    )
                    or "?"
                )
                end = (
                    item.get(
                        "end_stake_text"
                    )
                    or item.get(
                        "end_stake_value"
                    )
                    or "?"
                )
                range_text = (
                    f"{start}～{end}"
                )

            labels.append(
                f"{canal_name}（{range_text}）"
            )

        if not labels:
            scope_text = "-"
        elif len(labels) <= 6:
            scope_text = "、".join(
                labels
            )
        else:
            scope_text = (
                "、".join(
                    labels[:6]
                )
                + f" 等 {len(labels)} 项"
            )

        self.scope_summary_label.setText(
            scope_text
        )

        self.received_at_label.setText(
            str(
                workspace[
                    "received_at"
                ]
                or "-"
            )
        )

        self.status_label.setText(
            "当前任务工作区可用。"
        )

        return workspace
