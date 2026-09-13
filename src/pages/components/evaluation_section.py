from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class EvaluationSection(QGroupBox):
    """
    工程调查表通用 A/B/C/D 分项评价区域。

    evaluation_items 中每一项应具有：

    {
        "item_code": "...",
        "category": "...",
        "item_name": "...",
        "standards": {
            "A": "...",
            "B": "...",
            "C": "...",
            "D": "...",
        },
    }

    本组件负责：
    1. 根据配置生成评价界面；
    2. 始终显示 A/B/C/D 四级评价标准；
    3. 通过单选按钮直接选择等级；
    4. 清空、回填和收集评价结果；
    5. 对外通知用户评价发生变化。

    不负责：
    - SurveyRecord 保存；
    - 完成调查校验；
    - 页面脏数据状态；
    - 各附表自己的业务规则。
    """

    grade_changed = Signal()

    VALID_GRADES = (
        "A",
        "B",
        "C",
        "D",
    )

    def __init__(
        self,
        title,
        evaluation_items,
        description=None,
        parent=None,
    ):
        super().__init__(
            title,
            parent,
        )

        self.evaluation_items = list(evaluation_items)

        # key = item_code
        # value = QButtonGroup
        self.grade_groups = {}

        # key = item_code
        # value = {
        #     "A": QRadioButton,
        #     "B": QRadioButton,
        #     ...
        # }
        self.grade_buttons = {}

        self._init_ui(description=description)

    # =========================================================
    # UI
    # =========================================================

    def _init_ui(
        self,
        description=None,
    ):
        layout = QVBoxLayout(self)

        layout.setSpacing(14)

        if description:
            description_label = QLabel(description)

            description_label.setWordWrap(True)

            description_label.setStyleSheet("color: #607080;")

            layout.addWidget(description_label)

        # 按正式调查表中的评价类别分组。
        categories = {}

        for item in self.evaluation_items:
            category = item["category"]

            categories.setdefault(
                category,
                [],
            ).append(item)

        for category, items in categories.items():
            category_group = QGroupBox(category)

            category_layout = QVBoxLayout(category_group)

            category_layout.setSpacing(14)

            for item in items:
                item_widget = QWidget()

                item_layout = QVBoxLayout(item_widget)

                item_layout.setContentsMargins(
                    8,
                    6,
                    8,
                    10,
                )

                item_layout.setSpacing(8)

                # ---------------------------------------------
                # 评价项目名称
                # ---------------------------------------------

                item_label = QLabel(item["item_name"])

                item_label.setStyleSheet("font-weight: bold;")

                item_layout.addWidget(item_label)

                # ---------------------------------------------
                # A / B / C / D
                # 四级标准始终可见
                # ---------------------------------------------

                item_code = item["item_code"]

                standards = item.get(
                    "standards",
                    {},
                )

                button_group = QButtonGroup(self)

                button_group.setExclusive(True)

                buttons = {}

                for grade in self.VALID_GRADES:
                    row_layout = QHBoxLayout()

                    row_layout.setSpacing(10)

                    grade_button = QRadioButton(grade)

                    grade_button.setMinimumWidth(45)

                    standard_text = standards.get(grade) or "未配置评价标准。"

                    standard_label = QLabel(standard_text)

                    standard_label.setWordWrap(True)

                    standard_label.setStyleSheet("color: #52606d;")

                    row_layout.addWidget(grade_button)

                    row_layout.addWidget(
                        standard_label,
                        1,
                    )

                    item_layout.addLayout(row_layout)

                    button_group.addButton(grade_button)

                    buttons[grade] = grade_button

                    # clicked 只由用户实际点击触发。
                    # 程序回填 setChecked() 不会因此
                    # 被误判为用户修改。
                    grade_button.clicked.connect(
                        lambda checked=False: self.grade_changed.emit()
                    )

                self.grade_groups[item_code] = button_group

                self.grade_buttons[item_code] = buttons

                category_layout.addWidget(item_widget)

            layout.addWidget(category_group)

    # =========================================================
    # 编辑状态
    # =========================================================

    def set_editable(
        self,
        enabled,
    ):
        """
        设置全部评价按钮是否允许操作。
        """

        for buttons in self.grade_buttons.values():
            for button in buttons.values():
                button.setEnabled(enabled)

    # =========================================================
    # 清空
    # =========================================================

    def clear(self):
        """
        全部评价恢复为未评价状态。
        """

        for group in self.grade_groups.values():
            # 独占按钮组正常情况下
            # 无法直接取消当前选中项。
            # 清空时临时关闭独占状态。
            group.setExclusive(False)

            for button in group.buttons():
                button.setChecked(False)

            group.setExclusive(True)

    # =========================================================
    # 回填
    # =========================================================

    def load_results(
        self,
        results,
    ):
        """
        将数据库 inspection_results
        回填到评价控件。
        """

        self.clear()

        for result in results:
            item_code = result["item_code"]

            grade = result["grade"]

            if grade not in (self.VALID_GRADES):
                continue

            buttons = self.grade_buttons.get(item_code)

            # 兼容旧版本未知评价项目。
            if buttons is None:
                continue

            button = buttons.get(grade)

            if button is not None:
                button.setChecked(True)

    # =========================================================
    # 收集
    # =========================================================

    def collect_results(self):
        """
        收集已经选择 A/B/C/D 的项目。

        未评价项目不返回，
        与 inspection_results 当前保存规则一致。
        """

        results = []

        for item in self.evaluation_items:
            item_code = item["item_code"]

            buttons = self.grade_buttons[item_code]

            selected_grade = None

            for grade in self.VALID_GRADES:
                if buttons[grade].isChecked():
                    selected_grade = grade
                    break

            if selected_grade is None:
                continue

            results.append(
                {
                    "item_code": (item_code),
                    "category": (item["category"]),
                    "item_name": (item["item_name"]),
                    "grade": (selected_grade),
                    "description": None,
                    "remark": None,
                }
            )

        return results
