from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import (
    get_current_context,
    get_engineering_survey_query_records,
)


class AqueductListPage(QWidget):
    """
    附表2.3渡槽（座槽）调查记录列表。

    B1阶段只承担：
    - 当前调查批次记录展示；
    - 新增入口；
    - 打开已有草稿；
    - 返回调查首页。

    筛选、删除、成果导出等功能
    在后续阶段继续补充。
    """

    new_requested = Signal()
    back_requested = Signal()
    edit_requested = Signal(int)

    def __init__(self):
        super().__init__()

        self.current_context = None
        self.records = []

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

        button_layout.addWidget(back_button)

        button_layout.addWidget(new_button)

        button_layout.addWidget(refresh_button)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        # =====================================================
        # 标题
        # =====================================================

        title = QLabel("附表2.3 渡槽（座槽）工程状况调查记录")

        title.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        layout.addWidget(title)

        description = QLabel(
            "双击草稿记录可重新打开调查表。"
            "当前B1阶段先验证基本信息录入、"
            "草稿保存和重新打开；"
            "分项评价、完成调查、筛选和导出"
            "将在后续阶段继续接入。"
        )

        description.setWordWrap(True)

        description.setStyleSheet("color: #607080; " "font-size: 14px;")

        layout.addWidget(description)

        self.count_label = QLabel()

        self.count_label.setStyleSheet("color: #52606d; " "font-size: 14px;")

        layout.addWidget(self.count_label)

        # =====================================================
        # 表格
        # =====================================================

        self.table = QTableWidget()

        self.table.setColumnCount(4)

        self.table.setHorizontalHeaderLabels(
            [
                "工程名称",
                "桩号",
                "状态",
                "调查记录ID",
            ]
        )

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setAlternatingRowColors(True)

        self.table.cellDoubleClicked.connect(self.open_record)

        widths = [
            260,
            160,
            110,
            120,
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
            self.records = []

            self.table.setRowCount(0)

            self.count_label.setText("当前没有可用调查批次。")

            return

        self.records = get_engineering_survey_query_records(
            project_id=(self.current_context["project_id"]),
            survey_batch_id=(self.current_context["batch_id"]),
            form_code="form_2_3",
        )

        self._render_records()

        self.count_label.setText(f"当前批次共 " f"{len(self.records)} 条渡槽调查记录。")

    # =========================================================
    # 表格
    # =========================================================

    def _render_records(self):
        self.table.setRowCount(len(self.records))

        for row_index, record in enumerate(self.records):
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                record["record_status"],
                record["record_status"],
            )

            values = [
                record["asset_name"],
                record["engineering_position"],
                status_text,
                record["survey_record_id"],
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

        survey_record_id = item.data(Qt.ItemDataRole.UserRole)

        if survey_record_id is None:
            return

        self.edit_requested.emit(int(survey_record_id))
