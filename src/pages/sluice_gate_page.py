from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import (
    QDoubleValidator,
    QIntValidator,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

from database import (
    create_engineering_survey,
    get_canal_units_for_organization,
    get_current_context,
    get_current_form_version,
    get_departments,
    get_engineering_business_codes,
    get_water_offices,
    get_sluice_gate_record,
    update_sluice_gate_draft,
    get_inspection_results,
    complete_sluice_gate_record,
)

from services.business_code import (
    build_business_code,
    get_engineering_type_code,
    suggest_next_sequence,
)
from services.sluice_gate_evaluation import (
    SLUICE_GATE_EVALUATION_ITEMS,
)
from services.stake import parse_stake


class SluiceGatePage(QWidget):
    survey_saved = Signal()
    back_requested = Signal()

    def __init__(self):
        super().__init__()

        self.editing_record_id = None
        self.current_context = get_current_context()
        self.form_version = get_current_form_version("form_2_2")

        # 动态评价控件
        # key = item_code
        self.evaluation_grade_combos = {}
        self.evaluation_standard_labels = {}

        self.init_ui()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(18)

        self.title_label = QLabel("附表2.2 水闸工程状况调查")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")

        root_layout.addWidget(self.title_label)

        description = QLabel(
            "当前正在补全附表2.2基本信息。"
            "新增字段本阶段仅完成界面，"
            "下一阶段再接入保存和草稿回填。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #607080; font-size: 14px;")

        root_layout.addWidget(description)

        # =========================
        # 可滚动表单区域
        # =========================

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        form_container = QWidget()
        form_container_layout = QVBoxLayout(form_container)
        form_container_layout.setContentsMargins(
            4,
            4,
            12,
            4,
        )
        form_container_layout.setSpacing(16)

        # =========================
        # 1. 归属与编号
        # =========================

        ownership_group = QGroupBox("一、归属与编号")

        ownership_layout = QFormLayout(ownership_group)
        ownership_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        ownership_layout.setHorizontalSpacing(20)
        ownership_layout.setVerticalSpacing(12)

        # 基层处
        self.department_combo = QComboBox()
        self.department_combo.currentIndexChanged.connect(self.department_changed)

        # 水管所
        self.office_combo = QComboBox()
        self.office_combo.currentIndexChanged.connect(self.office_changed)

        # 渠系
        self.canal_combo = QComboBox()
        self.canal_combo.currentIndexChanged.connect(self.update_business_code)

        # 业务编号
        self.business_code_edit = QLineEdit()
        self.business_code_edit.setReadOnly(True)
        self.business_code_edit.setPlaceholderText("选择基层处、水管所和渠系后自动生成")

        ownership_layout.addRow(
            "所属基层处：",
            self.department_combo,
        )
        ownership_layout.addRow(
            "所属水管所：",
            self.office_combo,
        )
        ownership_layout.addRow(
            "所属渠系：",
            self.canal_combo,
        )
        ownership_layout.addRow(
            "业务编号：",
            self.business_code_edit,
        )

        form_container_layout.addWidget(ownership_group)

        # =========================
        # 2. 工程基本信息
        # =========================

        basic_group = QGroupBox("二、工程基本信息")

        basic_layout = QFormLayout(basic_group)
        basic_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        basic_layout.setHorizontalSpacing(20)
        basic_layout.setVerticalSpacing(12)

        # 工程名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：1号节制闸")

        # 桩号
        self.stake_edit = QLineEdit()
        self.stake_edit.setPlaceholderText("例如：K12+350")

        # 设计流量
        self.design_flow_edit = self._create_decimal_edit("例如：4.5，可留空")

        # 建筑物等级
        self.structure_grade_edit = QLineEdit()
        self.structure_grade_edit.setPlaceholderText("按原始资料填写，可留空")

        # 建成年月
        self.build_date_edit = self._create_month_edit()
        self.build_date_edit.setPlaceholderText("例如：2008-06，可留空")

        # 加固改造年月
        self.renovation_date_edit = self._create_month_edit()
        self.renovation_date_edit.setPlaceholderText("例如：2021-09，可留空")

        # 加大流量
        self.increased_flow_edit = self._create_decimal_edit("可留空")

        basic_layout.addRow(
            "工程名称：",
            self.name_edit,
        )
        basic_layout.addRow(
            "桩号：",
            self.stake_edit,
        )
        basic_layout.addRow(
            "设计流量（m³/s）：",
            self.design_flow_edit,
        )
        basic_layout.addRow(
            "建筑物等级：",
            self.structure_grade_edit,
        )
        basic_layout.addRow(
            "建成年月：",
            self.build_date_edit,
        )
        basic_layout.addRow(
            "加固改造年月：",
            self.renovation_date_edit,
        )
        basic_layout.addRow(
            "加大流量（m³/s）：",
            self.increased_flow_edit,
        )

        form_container_layout.addWidget(basic_group)

        # =========================
        # 3. 结构与材料参数
        # =========================

        structure_group = QGroupBox("三、结构与材料参数")

        structure_layout = QFormLayout(structure_group)
        structure_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        structure_layout.setHorizontalSpacing(20)
        structure_layout.setVerticalSpacing(12)

        # 孔数
        self.opening_count_edit = self._create_integer_edit("可留空")

        # 孔宽
        self.opening_width_edit = self._create_decimal_edit("可留空")

        # 孔高
        self.opening_height_edit = self._create_decimal_edit("可留空")

        # 主要构件材料
        self.main_component_material_edit = QLineEdit()
        self.main_component_material_edit.setPlaceholderText("例如：钢筋混凝土，可留空")

        # 混凝土强度
        self.concrete_strength_edit = QLineEdit()
        self.concrete_strength_edit.setPlaceholderText("例如：C30，可留空")

        # 钢筋混凝土强度
        self.reinforced_concrete_strength_edit = QLineEdit()
        self.reinforced_concrete_strength_edit.setPlaceholderText(
            "按原始资料填写，可留空"
        )

        # 保护层厚度
        self.cover_thickness_edit = self._create_decimal_edit("可留空")

        # 裂缝限宽
        self.crack_width_limit_edit = self._create_decimal_edit("可留空")

        structure_layout.addRow(
            "孔数：",
            self.opening_count_edit,
        )
        structure_layout.addRow(
            "孔宽（m）：",
            self.opening_width_edit,
        )
        structure_layout.addRow(
            "孔高（m）：",
            self.opening_height_edit,
        )
        structure_layout.addRow(
            "主要构件材料：",
            self.main_component_material_edit,
        )
        structure_layout.addRow(
            "混凝土强度：",
            self.concrete_strength_edit,
        )
        structure_layout.addRow(
            "钢筋混凝土强度：",
            self.reinforced_concrete_strength_edit,
        )
        structure_layout.addRow(
            "保护层厚度（mm）：",
            self.cover_thickness_edit,
        )
        structure_layout.addRow(
            "裂缝限宽（mm）：",
            self.crack_width_limit_edit,
        )

        form_container_layout.addWidget(structure_group)

        # =========================
        # 4. 分项评价
        # =========================

        evaluation_group = self._create_evaluation_group()

        form_container_layout.addWidget(evaluation_group)

        # =========================
        # 5. 调查结论
        # =========================

        conclusion_group = QGroupBox("五、调查结论")

        conclusion_layout = QFormLayout(conclusion_group)

        conclusion_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        conclusion_layout.setHorizontalSpacing(20)
        conclusion_layout.setVerticalSpacing(12)

        # 工程状况类别
        self.overall_grade_combo = QComboBox()

        self.overall_grade_combo.addItem(
            "未确定",
            None,
        )
        self.overall_grade_combo.addItem(
            "A",
            "A",
        )
        self.overall_grade_combo.addItem(
            "B",
            "B",
        )
        self.overall_grade_combo.addItem(
            "C",
            "C",
        )
        self.overall_grade_combo.addItem(
            "D",
            "D",
        )

        # 调查时间
        self.survey_date_edit = self._create_date_edit()
        self.survey_date_edit.setPlaceholderText("例如：2026-09-12，可留空")

        # 调查意见与建议
        self.survey_comment_edit = QPlainTextEdit()
        self.survey_comment_edit.setPlaceholderText("填写调查意见与建议，可留空")
        self.survey_comment_edit.setMinimumHeight(100)

        conclusion_layout.addRow(
            "工程状况类别：",
            self.overall_grade_combo,
        )

        conclusion_layout.addRow(
            "调查时间：",
            self.survey_date_edit,
        )

        conclusion_layout.addRow(
            "调查意见与建议：",
            self.survey_comment_edit,
        )

        form_container_layout.addWidget(conclusion_group)

        form_container_layout.addStretch()

        scroll_area.setWidget(form_container)

        root_layout.addWidget(
            scroll_area,
            1,
        )

        # =========================
        # 底部按钮
        # =========================

        button_layout = QHBoxLayout()

        back_button = QPushButton("返回列表")
        back_button.clicked.connect(self.back_requested.emit)

        button_layout.addWidget(back_button)

        button_layout.addStretch()

        self.save_button = QPushButton("保存草稿")
        self.save_button.setMinimumWidth(120)
        self.save_button.clicked.connect(self.save_draft)

        self.complete_button = QPushButton("完成调查")
        self.complete_button.setMinimumWidth(120)

        # 新增模式下还没有 survey_record_id，
        # 因此暂时不能直接完成。
        self.complete_button.setEnabled(False)

        self.complete_button.clicked.connect(self.complete_survey)

        button_layout.addWidget(self.save_button)

        button_layout.addWidget(self.complete_button)

        root_layout.addLayout(button_layout)

    def _create_evaluation_group(self):
        """
        根据附表2.2评价配置，
        动态生成全部分项评价控件。
        """
        evaluation_group = QGroupBox("四、分项评价")

        evaluation_layout = QVBoxLayout(evaluation_group)
        evaluation_layout.setSpacing(14)

        description = QLabel(
            "各分项可选择 A、B、C、D。"
            "选择等级后，下方显示对应评价标准。"
            "当前阶段评价结果暂不保存。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #607080;")

        evaluation_layout.addWidget(description)

        # 按 category 分组
        categories = {}

        for item in SLUICE_GATE_EVALUATION_ITEMS:
            category = item["category"]

            if category not in categories:
                categories[category] = []

            categories[category].append(item)

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

                # -------------------------
                # 第一行：项目名称 + 等级选择
                # -------------------------

                header_layout = QHBoxLayout()

                item_label = QLabel(item["item_name"])
                item_label.setMinimumWidth(180)

                grade_combo = QComboBox()
                grade_combo.setMinimumWidth(120)

                grade_combo.addItem(
                    "未评价",
                    None,
                )
                grade_combo.addItem(
                    "A",
                    "A",
                )
                grade_combo.addItem(
                    "B",
                    "B",
                )
                grade_combo.addItem(
                    "C",
                    "C",
                )
                grade_combo.addItem(
                    "D",
                    "D",
                )

                header_layout.addWidget(item_label)
                header_layout.addStretch()
                header_layout.addWidget(grade_combo)

                item_layout.addLayout(header_layout)

                # -------------------------
                # 第二行：对应等级标准
                # -------------------------

                standard_label = QLabel("尚未选择评价等级。")
                standard_label.setWordWrap(True)
                standard_label.setStyleSheet("color: #607080;" "padding: 4px 8px;")

                item_layout.addWidget(standard_label)

                item_code = item["item_code"]

                self.evaluation_grade_combos[item_code] = grade_combo

                self.evaluation_standard_labels[item_code] = standard_label

                grade_combo.currentIndexChanged.connect(
                    lambda checked=False, current_item=item, current_combo=grade_combo, current_label=standard_label: self._update_evaluation_standard(
                        current_item,
                        current_combo,
                        current_label,
                    )
                )

                category_layout.addWidget(item_widget)

            evaluation_layout.addWidget(category_group)

        return evaluation_group

    def _update_evaluation_standard(
        self,
        item,
        combo,
        label,
    ):
        """
        根据当前选择的 A/B/C/D，
        显示对应评价标准。
        """
        grade = combo.currentData()

        if grade is None:
            label.setText("尚未选择评价等级。")
            return

        standard = item["standards"].get(grade) or ""

        label.setText(f"{grade}级标准：{standard}")

    def _set_record_read_only(
        self,
        read_only,
    ):
        """
        设置调查内容是否只读。

        只处理调查内容控件；
        工程归属控件由新增/编辑模式单独控制。
        """
        enabled = not read_only

        # 工程基本信息
        self.name_edit.setEnabled(enabled)
        self.stake_edit.setEnabled(enabled)
        self.design_flow_edit.setEnabled(enabled)
        self.structure_grade_edit.setEnabled(enabled)
        self.build_date_edit.setEnabled(enabled)
        self.renovation_date_edit.setEnabled(enabled)
        self.increased_flow_edit.setEnabled(enabled)

        # 结构与材料参数
        self.opening_count_edit.setEnabled(enabled)
        self.opening_width_edit.setEnabled(enabled)
        self.opening_height_edit.setEnabled(enabled)

        self.main_component_material_edit.setEnabled(enabled)
        self.concrete_strength_edit.setEnabled(enabled)
        self.reinforced_concrete_strength_edit.setEnabled(enabled)

        self.cover_thickness_edit.setEnabled(enabled)
        self.crack_width_limit_edit.setEnabled(enabled)

        # 分项评价
        for combo in self.evaluation_grade_combos.values():
            combo.setEnabled(enabled)

        # 调查结论
        self.overall_grade_combo.setEnabled(enabled)
        self.survey_date_edit.setEnabled(enabled)
        self.survey_comment_edit.setEnabled(enabled)

        # 操作按钮
        self.save_button.setEnabled(enabled)

        if read_only:
            self.complete_button.setEnabled(False)

    def _clear_evaluation_controls(self):
        """
        将全部分项评价恢复为未评价。
        """
        for combo in self.evaluation_grade_combos.values():
            combo.setCurrentIndex(0)

    def _load_evaluation_results(
        self,
        results,
    ):
        """
        将数据库中已有的分项评价结果
        回填到动态生成的评价控件。
        """

        # 先全部恢复为“未评价”
        self._clear_evaluation_controls()

        for result in results:
            item_code = result["item_code"]
            grade = result["grade"]

            combo = self.evaluation_grade_combos.get(item_code)

            # 数据库里如果存在旧版本/未知项目，
            # 当前页面直接忽略，避免报错。
            if combo is None:
                continue

            if grade not in (
                "A",
                "B",
                "C",
                "D",
            ):
                continue

            index = combo.findData(grade)

            if index >= 0:
                combo.setCurrentIndex(index)

    def _collect_evaluation_results(self):
        """
        收集当前页面已经选择等级的分项评价。

        未评价项目不提交数据库。
        """
        results = []

        for item in SLUICE_GATE_EVALUATION_ITEMS:
            item_code = item["item_code"]

            combo = self.evaluation_grade_combos[item_code]

            grade = combo.currentData()

            if grade is None:
                continue

            results.append(
                {
                    "item_code": item_code,
                    "category": item["category"],
                    "item_name": item["item_name"],
                    "grade": grade,
                    "description": None,
                    "remark": None,
                }
            )

        return results

    def _create_decimal_edit(
        self,
        placeholder="",
    ):
        """
        创建允许为空的非负小数输入框。
        """
        edit = QLineEdit()

        if placeholder:
            edit.setPlaceholderText(placeholder)

        validator = QDoubleValidator(
            0.0,
            999999999.0,
            6,
            edit,
        )
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        edit.setValidator(validator)

        return edit

    def _create_integer_edit(
        self,
        placeholder="",
    ):
        """
        创建允许为空的非负整数输入框。
        """
        edit = QLineEdit()

        if placeholder:
            edit.setPlaceholderText(placeholder)

        validator = QIntValidator(
            0,
            999999,
            edit,
        )

        edit.setValidator(validator)

        return edit

    def _create_date_edit(self):
        """
        创建 YYYY-MM-DD 格式日期输入框。
        """
        edit = QLineEdit()
        edit.setMaxLength(10)

        expression = QRegularExpression(
            r"^\d{4}-(0[1-9]|1[0-2])-" r"(0[1-9]|[12]\d|3[01])$"
        )

        validator = QRegularExpressionValidator(
            expression,
            edit,
        )

        edit.setValidator(validator)

        return edit

    def _get_optional_date(
        self,
        edit,
        field_name,
    ):
        """
        获取 YYYY-MM-DD 格式日期。
        空值返回 None。
        """
        text = edit.text().strip()

        if not text:
            return None

        expression = QRegularExpression(
            r"^\d{4}-(0[1-9]|1[0-2])-" r"(0[1-9]|[12]\d|3[01])$"
        )

        if not expression.match(text).hasMatch():
            raise ValueError(f"{field_name}格式应为 YYYY-MM-DD，" "例如：2026-09-12。")

        return text

    def _create_month_edit(self):
        """
        创建 YYYY-MM 格式的年月输入框。

        当前只负责输入格式控制，
        下一阶段保存时再做最终业务校验。
        """
        edit = QLineEdit()
        edit.setMaxLength(7)

        expression = QRegularExpression(r"^\d{4}-(0[1-9]|1[0-2])$")

        validator = QRegularExpressionValidator(
            expression,
            edit,
        )

        edit.setValidator(validator)

        return edit

    def _get_optional_float(
        self,
        edit,
    ):
        """
        获取可为空的小数字段。
        空值返回 None。
        """
        text = edit.text().strip()

        if not text:
            return None

        return float(text)

    def _get_optional_int(
        self,
        edit,
    ):
        """
        获取可为空的整数字段。
        空值返回 None。
        """
        text = edit.text().strip()

        if not text:
            return None

        return int(text)

    def _get_optional_month(
        self,
        edit,
        field_name,
    ):
        """
        获取 YYYY-MM 格式年月。

        空值返回 None；
        非空但格式不完整时阻止保存。
        """
        text = edit.text().strip()

        if not text:
            return None

        expression = QRegularExpression(r"^\d{4}-(0[1-9]|1[0-2])$")

        if not expression.match(text).hasMatch():
            raise ValueError(f"{field_name}格式应为 YYYY-MM，" "例如：2020-06。")

        return text

    def load_departments(self):
        self.department_combo.blockSignals(True)
        self.department_combo.clear()

        departments = get_departments()

        for department in departments:
            if department["status"] != "active":
                continue

            self.department_combo.addItem(
                department["name"],
                {
                    "id": department["id"],
                    "business_code": (department["business_code"]),
                },
            )

        self.department_combo.blockSignals(False)

        self.department_changed()

    def department_changed(self):
        self.office_combo.blockSignals(True)
        self.office_combo.clear()

        department_data = self.department_combo.currentData()

        if not department_data:
            self.office_combo.blockSignals(False)
            self.canal_combo.clear()
            self.business_code_edit.clear()
            return

        offices = get_water_offices(department_data["id"])

        for office in offices:
            if office["status"] != "active":
                continue

            self.office_combo.addItem(
                office["name"],
                {
                    "id": office["id"],
                    "business_code": (office["business_code"]),
                },
            )

        self.office_combo.blockSignals(False)

        self.office_changed()

    def office_changed(self):
        self.canal_combo.blockSignals(True)
        self.canal_combo.clear()

        office_data = self.office_combo.currentData()

        if not office_data:
            self.canal_combo.blockSignals(False)
            self.business_code_edit.clear()
            return

        canals = get_canal_units_for_organization(office_data["id"])

        for canal in canals:
            self.canal_combo.addItem(
                canal["name"],
                {
                    "id": canal["id"],
                    "canal_level": (canal["canal_level"]),
                },
            )

        self.canal_combo.blockSignals(False)

        self.update_business_code()

    def update_business_code(self):
        try:
            department_data = self.department_combo.currentData()

            office_data = self.office_combo.currentData()

            canal_data = self.canal_combo.currentData()

            if (
                not department_data
                or not office_data
                or not canal_data
                or not self.current_context
            ):
                self.business_code_edit.clear()
                return

            department_code = department_data["business_code"]

            office_code = office_data["business_code"]

            canal_level_code = canal_data["canal_level"]

            if not department_code:
                raise ValueError("当前基层处没有业务代码。")

            if not office_code:
                raise ValueError("当前水管所没有业务代码。")

            engineering_type_code = get_engineering_type_code("form_2_2")

            existing_codes = get_engineering_business_codes(
                self.current_context["project_id"]
            )

            sequence = suggest_next_sequence(
                existing_codes=existing_codes,
                department_code=str(department_code),
                water_office_code=str(office_code),
                canal_level_code=str(canal_level_code),
                engineering_type_code=(engineering_type_code),
            )

            business_code = build_business_code(
                department_code=str(department_code),
                water_office_code=str(office_code),
                canal_level_code=str(canal_level_code),
                engineering_type_code=(engineering_type_code),
                sequence=sequence,
            )

            self.business_code_edit.setText(business_code)

        except Exception as error:
            self.business_code_edit.clear()

            QMessageBox.warning(
                self,
                "业务编号生成失败",
                str(error),
            )

    def save_draft(self):
        try:
            if not self.current_context:
                raise ValueError("当前没有可用项目。")

            if self.current_context["batch_id"] is None:
                raise ValueError("当前没有启用的调查批次。")

            if self.form_version is None:
                raise ValueError("未找到附表2.2当前版本。")

            department_data = self.department_combo.currentData()

            office_data = self.office_combo.currentData()

            canal_data = self.canal_combo.currentData()

            if not department_data:
                raise ValueError("请选择基层处。")

            if not office_data:
                raise ValueError("请选择水管所。")

            if not canal_data:
                raise ValueError("请选择所属渠系。")

            asset_name = self.name_edit.text().strip()

            if not asset_name:
                raise ValueError("工程名称不能为空。")

            business_code = self.business_code_edit.text().strip()

            if not business_code:
                raise ValueError("业务编号尚未生成。")

            stake_text, stake_value = parse_stake(self.stake_edit.text())

            design_flow = self._get_optional_float(self.design_flow_edit)

            structure_grade = self.structure_grade_edit.text().strip() or None

            build_date = self._get_optional_month(
                self.build_date_edit,
                "建成年月",
            )

            renovation_date = self._get_optional_month(
                self.renovation_date_edit,
                "加固改造年月",
            )

            opening_count = self._get_optional_int(self.opening_count_edit)

            opening_width = self._get_optional_float(self.opening_width_edit)

            opening_height = self._get_optional_float(self.opening_height_edit)

            increased_flow = self._get_optional_float(self.increased_flow_edit)

            main_component_material = (
                self.main_component_material_edit.text().strip() or None
            )

            concrete_strength = self.concrete_strength_edit.text().strip() or None

            reinforced_concrete_strength = (
                self.reinforced_concrete_strength_edit.text().strip() or None
            )

            cover_thickness = self._get_optional_float(self.cover_thickness_edit)

            crack_width_limit = self._get_optional_float(self.crack_width_limit_edit)

            record_data = {
                "asset_name": asset_name,
                "stake": stake_text,
                "stake_value": stake_value,
                "design_flow": design_flow,
                "structure_grade": structure_grade,
                "build_date": build_date,
                "renovation_date": renovation_date,
                "opening_count": opening_count,
                "opening_width": opening_width,
                "opening_height": opening_height,
                "increased_flow": increased_flow,
                "main_component_material": (main_component_material),
                "concrete_strength": (concrete_strength),
                "reinforced_concrete_strength": (reinforced_concrete_strength),
                "cover_thickness": cover_thickness,
                "crack_width_limit": (crack_width_limit),
            }

            inspection_results = self._collect_evaluation_results()

            survey_date = self._get_optional_date(
                self.survey_date_edit,
                "调查时间",
            )

            overall_grade = self.overall_grade_combo.currentData()

            survey_comment = self.survey_comment_edit.toPlainText().strip() or None

            if self.editing_record_id is None:
                result = create_engineering_survey(
                    project_id=self.current_context["project_id"],
                    survey_batch_id=self.current_context["batch_id"],
                    form_version_id=self.form_version["id"],
                    asset_name=asset_name,
                    asset_type=self.form_version["asset_type"],
                    organization_unit_id=(office_data["id"]),
                    canal_unit_id=(canal_data["id"]),
                    business_code=business_code,
                    record_data=record_data,
                    single_stake_text=stake_text,
                    single_stake_value=stake_value,
                    inspection_results=inspection_results,
                    survey_date=survey_date,
                    overall_grade=overall_grade,
                    survey_comment=survey_comment,
                )

                message = (
                    "水闸调查草稿已保存。\n\n"
                    f"业务编号："
                    f"{result['business_code']}\n"
                    f"工程对象ID："
                    f"{result['engineering_asset_id']}\n"
                    f"调查记录ID："
                    f"{result['survey_record_id']}"
                )

            else:
                update_sluice_gate_draft(
                    survey_record_id=self.editing_record_id,
                    asset_name=asset_name,
                    record_data=record_data,
                    single_stake_text=stake_text,
                    single_stake_value=stake_value,
                    inspection_results=inspection_results,
                    survey_date=survey_date,
                    overall_grade=overall_grade,
                    survey_comment=survey_comment,
                )

                message = "水闸调查草稿已更新。\n\n" f"业务编号：{business_code}"

            QMessageBox.information(
                self,
                "保存成功",
                message,
            )

            self.prepare_new()
            self.survey_saved.emit()

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )

    def complete_survey(self):
        """
        将当前已经保存的草稿标记为完成。

        D2-1阶段暂不自动保存页面上的未保存修改。
        """
        try:
            if self.editing_record_id is None:
                raise ValueError("请先保存草稿，再从列表重新打开该草稿后完成调查。")

            reply = QMessageBox.question(
                self,
                "确认完成调查",
                (
                    "完成后该记录将变为“已完成”，"
                    "当前阶段将不再允许直接编辑。\n\n"
                    "请确认当前修改已经通过“保存草稿”保存。\n\n"
                    "是否确认完成本次调查？"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            result = complete_sluice_gate_record(self.editing_record_id)

            QMessageBox.information(
                self,
                "完成成功",
                (
                    "本次水闸调查已标记为已完成。\n\n"
                    f"调查记录ID："
                    f"{result['survey_record_id']}\n"
                    f"已填写分项评价："
                    f"{result['inspection_count']} 项"
                ),
            )

            self.survey_saved.emit()
            self.back_requested.emit()

        except Exception as error:
            QMessageBox.warning(
                self,
                "完成失败",
                str(error),
            )

    def prepare_new(self):
        """
        切换到新增模式。
        """
        self.editing_record_id = None

        self.complete_button.setEnabled(False)

        self._set_record_read_only(False)

        self.complete_button.setEnabled(False)

        self.title_label.setText("附表2.2 水闸工程状况调查 - 新增")

        self.department_combo.setEnabled(True)
        self.office_combo.setEnabled(True)
        self.canal_combo.setEnabled(True)

        self.name_edit.clear()
        self.stake_edit.clear()
        self.design_flow_edit.clear()

        self.structure_grade_edit.clear()
        self.build_date_edit.clear()
        self.renovation_date_edit.clear()

        self.opening_count_edit.clear()
        self.opening_width_edit.clear()
        self.opening_height_edit.clear()

        self.increased_flow_edit.clear()

        self.main_component_material_edit.clear()
        self.concrete_strength_edit.clear()
        self.reinforced_concrete_strength_edit.clear()

        self.cover_thickness_edit.clear()
        self.crack_width_limit_edit.clear()
        self._clear_evaluation_controls()

        self.overall_grade_combo.setCurrentIndex(0)
        self.survey_date_edit.clear()
        self.survey_comment_edit.clear()

        self.load_departments()
        self.update_business_code()

    def _set_combo_by_id(
        self,
        combo,
        target_id,
    ):
        """
        根据 combo 中 currentData()['id']
        找到指定对象。
        """
        for index in range(combo.count()):
            data = combo.itemData(index)

            if isinstance(data, dict) and data.get("id") == target_id:
                combo.setCurrentIndex(index)
                return True

        return False

    def load_record(
        self,
        survey_record_id,
    ):
        """
        打开已有水闸草稿进入编辑模式。
        """
        record = get_sluice_gate_record(survey_record_id)

        if record is None:
            raise ValueError("没有找到该调查记录。")

        self._clear_evaluation_controls()

        record_status = record["record_status"]

        if record_status not in (
            "draft",
            "completed",
        ):
            raise ValueError("当前记录状态暂不支持打开。")

        self.editing_record_id = survey_record_id

        self.title_label.setText("附表2.2 水闸工程状况调查 - 编辑草稿")

        # 先加载基层处
        self.load_departments()

        self._set_combo_by_id(
            self.department_combo,
            record["department_id"],
        )

        # 按选中的基层处重新加载水管所
        self.department_changed()

        self._set_combo_by_id(
            self.office_combo,
            record["office_id"],
        )

        # 按选中的水管所重新加载渠系
        self.office_changed()

        self._set_combo_by_id(
            self.canal_combo,
            record["canal_id"],
        )

        self.business_code_edit.setText(record["business_code"])

        record_data = record["record_data"]

        self.name_edit.setText(record["asset_name"])

        self.stake_edit.setText(record_data.get("stake") or "")

        # =========================
        # 工程基本信息回填
        # =========================

        design_flow = record_data.get("design_flow")

        self.design_flow_edit.setText("" if design_flow is None else str(design_flow))

        self.structure_grade_edit.setText(record_data.get("structure_grade") or "")

        self.build_date_edit.setText(record_data.get("build_date") or "")

        self.renovation_date_edit.setText(record_data.get("renovation_date") or "")

        increased_flow = record_data.get("increased_flow")

        self.increased_flow_edit.setText(
            "" if increased_flow is None else str(increased_flow)
        )

        # =========================
        # 结构与材料参数回填
        # =========================

        opening_count = record_data.get("opening_count")

        self.opening_count_edit.setText(
            "" if opening_count is None else str(opening_count)
        )

        opening_width = record_data.get("opening_width")

        self.opening_width_edit.setText(
            "" if opening_width is None else str(opening_width)
        )

        opening_height = record_data.get("opening_height")

        self.opening_height_edit.setText(
            "" if opening_height is None else str(opening_height)
        )

        self.main_component_material_edit.setText(
            record_data.get("main_component_material") or ""
        )

        self.concrete_strength_edit.setText(record_data.get("concrete_strength") or "")

        self.reinforced_concrete_strength_edit.setText(
            record_data.get("reinforced_concrete_strength") or ""
        )

        cover_thickness = record_data.get("cover_thickness")

        self.cover_thickness_edit.setText(
            "" if cover_thickness is None else str(cover_thickness)
        )

        crack_width_limit = record_data.get("crack_width_limit")

        self.crack_width_limit_edit.setText(
            "" if crack_width_limit is None else str(crack_width_limit)
        )

        # =========================
        # 分项评价结果回填
        # =========================

        inspection_results = get_inspection_results(survey_record_id)

        self._load_evaluation_results(inspection_results)

        # =========================
        # 调查结论回填
        # =========================

        survey_date = record.get("survey_date")

        self.survey_date_edit.setText(survey_date or "")

        survey_comment = record.get("survey_comment")

        self.survey_comment_edit.setPlainText(survey_comment or "")

        overall_grade = record.get("overall_grade")

        if overall_grade in (
            "A",
            "B",
            "C",
            "D",
        ):
            index = self.overall_grade_combo.findData(overall_grade)

            if index >= 0:
                self.overall_grade_combo.setCurrentIndex(index)
        else:
            self.overall_grade_combo.setCurrentIndex(0)

        # 编辑模式暂时禁止修改工程归属
        self.department_combo.setEnabled(False)
        self.office_combo.setEnabled(False)
        self.canal_combo.setEnabled(False)

        # =========================
        # 根据记录状态设置页面模式
        # =========================

        if record_status == "draft":
            self.title_label.setText("附表2.2 水闸工程状况调查 - 编辑草稿")

            self._set_record_read_only(False)

            # 已登记工程的归属暂不允许修改
            self.department_combo.setEnabled(False)
            self.office_combo.setEnabled(False)
            self.canal_combo.setEnabled(False)

            self.complete_button.setEnabled(True)

        elif record_status == "completed":
            self.title_label.setText("附表2.2 水闸工程状况调查 - 已完成 / 只读")

            self._set_record_read_only(True)

            self.department_combo.setEnabled(False)
            self.office_combo.setEnabled(False)
            self.canal_combo.setEnabled(False)
