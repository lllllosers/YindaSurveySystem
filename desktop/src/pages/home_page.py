from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import (
    get_current_context,
    get_survey_readiness,
)
from services.survey_progress import (
    get_engineering_progress,
)
from version import (
    APP_STAGE,
    APP_VERSION_LABEL,
)


class HomePage(QWidget):
    navigate_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.refresh_data()

    def init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        page_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(
            True
        )
        self.scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.scroll_content = QWidget()
        self.scroll_area.setWidget(
            self.scroll_content
        )
        page_layout.addWidget(
            self.scroll_area
        )

        layout = QVBoxLayout(
            self.scroll_content
        )
        layout.setContentsMargins(
            2,
            2,
            8,
            2,
        )
        layout.setSpacing(18)

        heading = QLabel("工程现状调查工作台")
        heading.setObjectName("homeHeading")
        layout.addWidget(heading)

        intro = QLabel(
            "当前正式支持附表2.1～2.14工程现状调查，"
            "覆盖调查录入、工程台账、数据查询、任务管理和成果管理。"
        )
        intro.setWordWrap(True)
        intro.setObjectName("homeIntro")
        layout.addWidget(intro)

        context_card = QFrame()
        context_card.setObjectName("homeCard")
        context_layout = QVBoxLayout(context_card)
        context_layout.setContentsMargins(18, 16, 18, 16)
        context_layout.setSpacing(8)

        context_title = QLabel("当前工作环境")
        context_title.setObjectName("homeSectionTitle")
        context_layout.addWidget(context_title)

        self.project_label = QLabel()
        self.batch_label = QLabel()
        self.readiness_label = QLabel()

        context_layout.addWidget(self.project_label)
        context_layout.addWidget(self.batch_label)
        context_layout.addWidget(self.readiness_label)
        layout.addWidget(context_card)

        progress_card = QFrame()
        progress_card.setObjectName("homeCard")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(18, 16, 18, 16)
        progress_layout.setSpacing(10)

        progress_title = QLabel("完成情况统计")
        progress_title.setObjectName("homeSectionTitle")
        progress_layout.addWidget(progress_title)

        progress_note = QLabel(
            "按当前项目、当前调查批次统计。"
            "“已录记录完成率”=录入完成记录÷已录记录；"
            "系统当前没有“应调查工程总量”基准，"
            "因此该比例不代表辖区最终工作量完成率。"
        )
        progress_note.setWordWrap(True)
        progress_note.setObjectName("progressNote")
        progress_layout.addWidget(progress_note)

        summary_row = QHBoxLayout()

        self.progress_total_label = QLabel()
        self.progress_completed_label = QLabel()
        self.progress_draft_label = QLabel()
        self.progress_rate_label = QLabel()

        for label in (
            self.progress_total_label,
            self.progress_completed_label,
            self.progress_draft_label,
            self.progress_rate_label,
        ):
            label.setObjectName("progressSummary")
            summary_row.addWidget(label)

        summary_row.addStretch()
        progress_layout.addLayout(summary_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)

        self.progress_tree = QTreeWidget()
        self.progress_tree.setObjectName("progressTree")
        self.progress_tree.setColumnCount(9)
        self.progress_tree.setHeaderLabels(
            [
                "单位",
                "已录",
                "录入完成",
                "草稿",
                "已录记录完成率",
                "A",
                "B",
                "C",
                "D",
            ]
        )
        self.progress_tree.setMinimumHeight(210)
        self.progress_tree.setMaximumHeight(280)
        self.progress_tree.setColumnWidth(0, 220)
        self.progress_tree.setColumnWidth(4, 110)
        self.progress_tree.setRootIsDecorated(True)
        self.progress_tree.setAlternatingRowColors(True)
        progress_layout.addWidget(self.progress_tree)

        layout.addWidget(progress_card, 1)

        scope_card = QFrame()
        scope_card.setObjectName("homeCard")
        scope_layout = QVBoxLayout(scope_card)
        scope_layout.setContentsMargins(18, 16, 18, 16)
        scope_layout.setSpacing(8)

        scope_title = QLabel("当前业务范围")
        scope_title.setObjectName("homeSectionTitle")
        scope_layout.addWidget(scope_title)

        scope_text = QLabel(
            "正式业务：附表2.1～2.14工程现状调查。\n"
            "预留业务：附表1.1～1.15灌区综合与水土资源调查，"
            "当前仍按内业统计和Excel流程开展。"
        )
        scope_text.setWordWrap(True)
        scope_layout.addWidget(scope_text)
        layout.addWidget(scope_card)

        quick_card = QFrame()
        quick_card.setObjectName("homeCard")
        quick_layout = QVBoxLayout(quick_card)
        quick_layout.setContentsMargins(18, 16, 18, 16)
        quick_layout.setSpacing(12)

        quick_title = QLabel("常用功能")
        quick_title.setObjectName("homeSectionTitle")
        quick_layout.addWidget(quick_title)

        button_grid = QGridLayout()
        button_grid.setHorizontalSpacing(12)
        button_grid.setVerticalSpacing(10)

        actions = (
            ("开始调查录入", "调查录入"),
            ("查看工程台账", "工程台账"),
            ("查询调查数据", "数据查询"),
            ("提交调查成果", "成果提交"),
        )

        for index, (text, target) in enumerate(actions):
            button = QPushButton(text)
            button.setMinimumHeight(42)
            button.clicked.connect(
                lambda checked=False, page=target: self.navigate_requested.emit(page)
            )
            button_grid.addWidget(
                button,
                index // 2,
                index % 2,
            )

        quick_layout.addLayout(button_grid)
        layout.addWidget(quick_card)

        footer_row = QHBoxLayout()
        footer_row.addStretch()

        version_label = QLabel(
            f"{APP_VERSION_LABEL} {APP_STAGE}"
        )
        version_label.setObjectName("homeVersion")
        footer_row.addWidget(version_label)

        layout.addLayout(footer_row)
        layout.addStretch()

        self.setStyleSheet(
            '''
            #homeHeading {
                font-size: 22px;
                font-weight: 700;
                color: #263238;
            }

            #homeIntro {
                color: #607080;
                font-size: 14px;
            }

            #homeCard {
                background: #ffffff;
                border: 1px solid #e2e5e9;
                border-radius: 8px;
            }

            #homeSectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #263238;
            }

            #homeVersion {
                color: #7a8793;
                font-size: 13px;
            }

            #progressNote {
                color: #607080;
                font-size: 13px;
            }

            #progressSummary {
                font-weight: 600;
                color: #37474f;
                padding-right: 14px;
            }
            '''
        )

    def refresh_data(self):
        context = get_current_context()

        if context:
            project_name = (
                context.get("project_name")
                or "未选择项目"
            )
            batch_name = (
                context.get("batch_name")
                or "未选择调查批次"
            )
            project_id = context.get("project_id")
            batch_id = context.get("batch_id")
        else:
            project_name = "未选择项目"
            batch_name = "未选择调查批次"
            project_id = None
            batch_id = None

        self.project_label.setText(
            f"当前项目：{project_name}"
        )
        self.batch_label.setText(
            f"当前调查批次：{batch_name}"
        )

        readiness = get_survey_readiness()

        if readiness.get("ready"):
            self.readiness_label.setText(
                "调查准备状态：已具备调查录入条件"
            )
        else:
            missing = readiness.get("missing") or []
            missing_text = "、".join(
                str(item)
                for item in missing
            )

            if missing_text:
                self.readiness_label.setText(
                    "调查准备状态：尚需完善 "
                    f"{missing_text}"
                )
            else:
                self.readiness_label.setText(
                    "调查准备状态：尚未完成基础配置"
                )

        self._refresh_progress(
            project_id,
            batch_id,
        )

    def _format_progress_rate(
        self,
        rate,
    ) -> str:
        if rate is None:
            return "—"

        return f"{float(rate):.1f}%"

    def _make_progress_item(
        self,
        summary,
    ):
        grades = (
            summary.get("grades")
            or {}
        )

        return QTreeWidgetItem(
            [
                "",
                str(
                    int(
                        summary.get(
                            "total_records",
                            0,
                        )
                    )
                ),
                str(
                    int(
                        summary.get(
                            "completed_records",
                            0,
                        )
                    )
                ),
                str(
                    int(
                        summary.get(
                            "draft_records",
                            0,
                        )
                    )
                ),
                self._format_progress_rate(
                    summary.get(
                        "completion_rate"
                    )
                ),
                str(int(grades.get("A", 0))),
                str(int(grades.get("B", 0))),
                str(int(grades.get("C", 0))),
                str(int(grades.get("D", 0))),
            ]
        )

    def _refresh_progress(
        self,
        project_id,
        batch_id,
    ):
        self.progress_tree.clear()

        if (
            project_id is None
            or batch_id is None
        ):
            progress = {
                "total_records": 0,
                "completed_records": 0,
                "draft_records": 0,
                "completion_rate": None,
                "departments": [],
            }
        else:
            progress = (
                get_engineering_progress(
                    int(project_id),
                    int(batch_id),
                )
            )

        total = int(
            progress.get(
                "total_records",
                0,
            )
        )
        completed = int(
            progress.get(
                "completed_records",
                0,
            )
        )
        draft = int(
            progress.get(
                "draft_records",
                0,
            )
        )
        rate = progress.get(
            "completion_rate"
        )

        self.progress_total_label.setText(
            f"已录：{total}"
        )
        self.progress_completed_label.setText(
            f"已完成：{completed}"
        )
        self.progress_draft_label.setText(
            f"草稿：{draft}"
        )
        self.progress_rate_label.setText(
            "已录记录完成率："
            + self._format_progress_rate(rate)
        )

        if rate is None:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat(
                "暂无已录记录"
            )
        else:
            self.progress_bar.setValue(
                int(
                    round(
                        float(rate)
                        * 10
                    )
                )
            )
            self.progress_bar.setFormat(
                "已录记录完成率 "
                f"{float(rate):.1f}%"
            )

        for department in (
            progress.get("departments")
            or []
        ):
            department_item = (
                self._make_progress_item(
                    department
                )
            )
            department_item.setText(
                0,
                str(
                    department.get(
                        "department_name",
                        "",
                    )
                ),
            )

            for column in range(
                self.progress_tree.columnCount()
            ):
                font = department_item.font(
                    column
                )
                font.setBold(True)
                department_item.setFont(
                    column,
                    font,
                )

            self.progress_tree.addTopLevelItem(
                department_item
            )

            for office in (
                department.get("offices")
                or []
            ):
                office_item = (
                    self._make_progress_item(
                        office
                    )
                )
                office_item.setText(
                    0,
                    str(
                        office.get(
                            "office_name",
                            "",
                        )
                    ),
                )
                department_item.addChild(
                    office_item
                )

        self.progress_tree.expandAll()
