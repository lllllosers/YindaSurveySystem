from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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

    本组件只负责：
    1. 根据配置生成评价界面；
    2. A/B/C/D选择；
    3. 显示对应评价标准；
    4. 清空、回填和收集评价结果。

    不负责：
    - SurveyRecord 保存；
    - 完成调查校验；
    - 页面脏数据状态；
    - 各附表自己的业务规则。
    """

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

        self.grade_combos = {}
        self.standard_labels = {}

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

            category_layout.setSpacing(12)

            for item in items:
                item_widget = QWidget()

                item_layout = QVBoxLayout(item_widget)

                item_layout.setContentsMargins(
                    8,
                    4,
                    8,
                    8,
                )

                item_layout.setSpacing(6)

                # =============================================
                # 项目名称 + 等级
                # =============================================

                header_layout = QHBoxLayout()

                item_label = QLabel(item["item_name"])

                item_label.setMinimumWidth(180)

                grade_combo = QComboBox()

                grade_combo.setMinimumWidth(120)

                grade_combo.addItem(
                    "未评价",
                    None,
                )

                for grade in self.VALID_GRADES:
                    grade_combo.addItem(
                        grade,
                        grade,
                    )

                header_layout.addWidget(item_label)

                header_layout.addStretch()

                header_layout.addWidget(grade_combo)

                item_layout.addLayout(header_layout)

                # =============================================
                # 评价标准
                # =============================================

                standard_label = QLabel("尚未选择评价等级。")

                standard_label.setWordWrap(True)

                standard_label.setStyleSheet("color: #607080;" "padding: 4px 8px;")

                item_layout.addWidget(standard_label)

                item_code = item["item_code"]

                self.grade_combos[item_code] = grade_combo

                self.standard_labels[item_code] = standard_label

                grade_combo.currentIndexChanged.connect(
                    lambda checked=False, current_item=item, current_combo=grade_combo, current_label=standard_label: self._update_standard(
                        current_item,
                        current_combo,
                        current_label,
                    )
                )

                category_layout.addWidget(item_widget)

            layout.addWidget(category_group)

    # =========================================================
    # 标准显示
    # =========================================================

    def _update_standard(
        self,
        item,
        combo,
        label,
    ):
        grade = combo.currentData()

        if grade is None:
            label.setText("尚未选择评价等级。")
            return

        standard = (
            item.get(
                "standards",
                {},
            ).get(grade)
            or ""
        )

        label.setText(f"{grade}级标准：" f"{standard}")

    # =========================================================
    # 控件访问
    # =========================================================

    def get_grade_combos(self):
        """
        返回全部评价下拉框。

        页面可用于：
        - dirty tracking
        - enabled/read-only 控制
        """

        return self.grade_combos

    # =========================================================
    # 清空
    # =========================================================

    def clear(self):
        """
        全部评价恢复为“未评价”。
        """

        for combo in self.grade_combos.values():
            combo.setCurrentIndex(0)

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

            combo = self.grade_combos.get(item_code)

            # 兼容旧版本未知评价项目。
            if combo is None:
                continue

            if grade not in (self.VALID_GRADES):
                continue

            index = combo.findData(grade)

            if index >= 0:
                combo.setCurrentIndex(index)

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

            combo = self.grade_combos[item_code]

            grade = combo.currentData()

            if grade not in (self.VALID_GRADES):
                continue

            results.append(
                {
                    "item_code": (item_code),
                    "category": (item["category"]),
                    "item_name": (item["item_name"]),
                    "grade": grade,
                    "description": None,
                    "remark": None,
                }
            )

        return results
