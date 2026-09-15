from datetime import datetime
from PySide6.QtCore import (
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database import (
    complete_tunnel_record,
    create_range_engineering_survey,
    get_canal_units_for_organization,
    get_current_context,
    get_current_form_version,
    get_departments,
    get_engineering_business_codes,
    get_inspection_results,
    get_range_engineering_record,
    get_water_offices,
    update_range_engineering_survey,
)

from pages.components.survey_input_fields import (
    create_date_edit,
    create_month_edit,
    create_nonnegative_decimal_edit,
    get_optional_date,
    get_optional_float,
    get_optional_month,
    get_optional_text,
)

from pages.components.evaluation_section import (
    EvaluationSection,
)

from services.tunnel_evaluation import (
    TUNNEL_EVALUATION_ITEMS,
)

from services.business_code import (
    build_business_code,
    get_engineering_type_code,
    suggest_next_sequence,
)

from services.stake import parse_stake


class TunnelPage(QWidget):
    """
    附表2.5 隧洞工程状况调查页面。

    B1阶段先负责：
    - 工程归属；
    - 业务编号；
    - 正式基本信息；
    - 表单数据收集。

    分项评价、调查结论和完成调查
    在后续阶段接入。
    """

    survey_saved = Signal()
    back_requested = Signal()

    def __init__(self):
        super().__init__()

        self.editing_record_id = None
        self.editing_record_status = None

        self.is_dirty = False

        self.current_context = get_current_context()

        self.form_version = get_current_form_version("form_2_5")

        self.evaluation_section: EvaluationSection

        self.init_ui()

        self._setup_tab_order()
        self._setup_keyboard_shortcuts()
        self._connect_dirty_tracking()

    # =========================================================
    # UI
    # =========================================================

    def init_ui(self):
        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.setSpacing(18)

        self.title_label = QLabel("附表2.5 隧洞工程状况调查")

        self.title_label.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        root_layout.addWidget(self.title_label)

        description = QLabel(
            "填写附表2.5基本信息、分项评价及调查结论。"
            "草稿允许暂时不完整；"
            "完成调查前系统将检查全部必填内容。"
        )

        description.setWordWrap(True)

        description.setStyleSheet("color: #607080; " "font-size: 15px;")

        root_layout.addWidget(description)

        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(True)

        form_container = QWidget()

        form_layout = QVBoxLayout(form_container)

        form_layout.setContentsMargins(
            4,
            4,
            12,
            4,
        )

        form_layout.setSpacing(16)

        # =====================================================
        # 一、归属与编号
        # =====================================================

        ownership_group = QGroupBox("一、归属与编号")

        ownership_layout = QFormLayout(ownership_group)

        self._setup_form_layout(ownership_layout)

        self.department_combo = QComboBox()

        self.office_combo = QComboBox()

        self.canal_combo = QComboBox()

        self.business_code_edit = QLineEdit()

        self.business_code_edit.setReadOnly(True)

        self.business_code_edit.setPlaceholderText("选择基层处、水管所和渠系后自动生成")

        self.department_combo.currentIndexChanged.connect(self.department_changed)

        self.office_combo.currentIndexChanged.connect(self.office_changed)

        self.canal_combo.currentIndexChanged.connect(self.update_business_code)

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

        form_layout.addWidget(ownership_group)

        # =====================================================
        # 二、工程基本信息
        # =====================================================

        basic_group = QGroupBox("二、工程基本信息")

        basic_layout = QFormLayout(basic_group)

        self._setup_form_layout(basic_layout)

        self.name_edit = QLineEdit()

        self.name_edit.setPlaceholderText("填写隧洞名称")

        self.start_stake_edit = QLineEdit()
        self.end_stake_edit = QLineEdit()

        self.start_stake_edit.setPlaceholderText("例如：CH20+000")

        self.end_stake_edit.setPlaceholderText("例如：CH21+200")

        self.design_flow_edit = create_nonnegative_decimal_edit()

        self.structure_grade_edit = QLineEdit()

        self.structure_grade_edit.setPlaceholderText("按原始资料填写")

        self.build_date_edit = create_month_edit("直接输入6位数字，例如：201006")

        self.renovation_date_edit = create_month_edit("例如：202109，可留空")

        self.length_edit = create_nonnegative_decimal_edit()

        self.increased_flow_edit = create_nonnegative_decimal_edit()

        basic_layout.addRow(
            "名称：",
            self.name_edit,
        )

        basic_layout.addRow(
            "起始桩号：",
            self.start_stake_edit,
        )

        basic_layout.addRow(
            "终止桩号：",
            self.end_stake_edit,
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

        # 正式原表没有给长度标注单位，
        # UI 不自行增加。
        basic_layout.addRow(
            "长度：",
            self.length_edit,
        )

        basic_layout.addRow(
            "加大流量（m³/s）：",
            self.increased_flow_edit,
        )

        form_layout.addWidget(basic_group)

        # =====================================================
        # 三、结构参数
        # =====================================================

        structure_group = QGroupBox("三、结构与断面参数")

        structure_layout = QFormLayout(structure_group)

        self._setup_form_layout(structure_layout)

        self.lining_form_edit = QLineEdit()

        self.lining_thickness_edit = create_nonnegative_decimal_edit()

        self.concrete_strength_edit = QLineEdit()

        self.inlet_outlet_bottom_elevation_edit = QLineEdit()

        self.longitudinal_slope_edit = create_nonnegative_decimal_edit()

        self.section_form_edit = QLineEdit()

        self.section_width_edit = create_nonnegative_decimal_edit()

        self.section_height_edit = create_nonnegative_decimal_edit()

        self.cover_thickness_edit = create_nonnegative_decimal_edit()

        self.lining_form_edit.setPlaceholderText("按原始资料填写")

        self.concrete_strength_edit.setPlaceholderText("例如：C30")

        self.inlet_outlet_bottom_elevation_edit.setPlaceholderText("按原始资料填写")

        self.section_form_edit.setPlaceholderText("按原始资料填写")

        structure_layout.addRow(
            "衬砌形式：",
            self.lining_form_edit,
        )

        structure_layout.addRow(
            "衬砌厚度：",
            self.lining_thickness_edit,
        )

        structure_layout.addRow(
            "混凝土强度：",
            self.concrete_strength_edit,
        )

        structure_layout.addRow(
            "进出口底部高程：",
            self.inlet_outlet_bottom_elevation_edit,
        )

        structure_layout.addRow(
            "纵坡（n/1000）：",
            self.longitudinal_slope_edit,
        )

        structure_layout.addRow(
            "断面型式：",
            self.section_form_edit,
        )

        structure_layout.addRow(
            "尺寸（宽）：",
            self.section_width_edit,
        )

        structure_layout.addRow(
            "尺寸（高）：",
            self.section_height_edit,
        )

        structure_layout.addRow(
            "钢筋保护层厚度：",
            self.cover_thickness_edit,
        )

        form_layout.addWidget(structure_group)

        self.scroll_area.setWidget(form_container)

        root_layout.addWidget(
            self.scroll_area,
            1,
        )

        # =====================================================
        # 四、分项评价
        # =====================================================

        self.evaluation_section = EvaluationSection(
            title="四、分项评价",
            evaluation_items=(TUNNEL_EVALUATION_ITEMS),
            description=(
                "各项目始终显示 "
                "A、B、C、D 四级评价标准，"
                "请根据现场情况直接选择"
                "对应等级。"
            ),
        )

        form_layout.addWidget(self.evaluation_section)

        # =====================================================
        # 五、调查结论
        # =====================================================

        conclusion_group = QGroupBox("五、调查结论")

        conclusion_layout = QFormLayout(conclusion_group)

        self._setup_form_layout(conclusion_layout)

        # -------------------------
        # 工程状况类别
        # -------------------------

        self.overall_grade_widget = QWidget()

        grade_layout = QHBoxLayout(self.overall_grade_widget)

        grade_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        grade_layout.setSpacing(20)

        self.overall_grade_group = QButtonGroup(self)

        self.overall_grade_group.setExclusive(True)

        self.overall_grade_buttons = {}

        for grade in (
            "A",
            "B",
            "C",
            "D",
        ):
            button = QRadioButton(grade)

            self.overall_grade_group.addButton(button)

            self.overall_grade_buttons[grade] = button

            grade_layout.addWidget(button)

        grade_layout.addStretch()

        # -------------------------
        # 调查时间
        # -------------------------

        self.survey_date_edit = create_date_edit()

        # -------------------------
        # 调查意见与建议
        # -------------------------

        self.survey_comment_edit = QPlainTextEdit()

        self.survey_comment_edit.setPlaceholderText("填写调查意见与建议")

        self.survey_comment_edit.setMinimumHeight(100)

        self.survey_comment_edit.setTabChangesFocus(True)

        conclusion_layout.addRow(
            "工程状况类别：",
            self.overall_grade_widget,
        )

        conclusion_layout.addRow(
            "调查时间：",
            self.survey_date_edit,
        )

        conclusion_layout.addRow(
            "调查意见与建议：",
            self.survey_comment_edit,
        )

        form_layout.addWidget(conclusion_group)

        form_layout.addStretch()

        # =====================================================
        # 底部
        # =====================================================

        self.back_button = QPushButton("返回")

        self.back_button.clicked.connect(self.request_back)

        shortcut_hint = QLabel("快捷键：Ctrl+S 保存　|　" "Ctrl+Enter 完成调查")

        shortcut_hint.setStyleSheet("color: #607080;")

        self.save_button = QPushButton("保存草稿")

        self.save_button.setMinimumWidth(120)

        self.complete_button = QPushButton("完成调查")

        self.complete_button.setMinimumWidth(120)

        self.complete_button.setToolTip("完成调查（Ctrl+Enter）")

        self.complete_button.clicked.connect(self.complete_survey)

        self.save_button.setToolTip("保存当前草稿（Ctrl+S）")

        self.save_button.clicked.connect(self.save_draft)

        button_layout = QHBoxLayout()

        button_layout.addWidget(self.back_button)

        button_layout.addStretch()

        button_layout.addWidget(shortcut_hint)

        button_layout.addSpacing(12)

        button_layout.addWidget(self.save_button)

        button_layout.addWidget(self.complete_button)

        root_layout.addLayout(button_layout)

    def _get_overall_grade(self):
        for grade, button in self.overall_grade_buttons.items():
            if button.isChecked():
                return grade

        return None

    def _clear_overall_grade(self):
        self.overall_grade_group.setExclusive(False)

        for button in self.overall_grade_buttons.values():
            button.setChecked(False)

        self.overall_grade_group.setExclusive(True)

    def _set_overall_grade(
        self,
        grade,
    ):
        self._clear_overall_grade()

        button = self.overall_grade_buttons.get(grade)

        if button is not None:
            button.setChecked(True)

    def _clear_evaluation_controls(self):
        self.evaluation_section.clear()

    def _load_evaluation_results(
        self,
        results,
    ):
        self.evaluation_section.load_results(results)

    def _collect_evaluation_results(
        self,
    ):
        return self.evaluation_section.collect_results()

    def _setup_form_layout(
        self,
        layout,
    ):
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(12)

    # =========================================================
    # Tab 顺序
    # =========================================================

    def _setup_tab_order(self):
        widgets = [
            self.department_combo,
            self.office_combo,
            self.canal_combo,
            self.name_edit,
            self.start_stake_edit,
            self.end_stake_edit,
            self.design_flow_edit,
            self.structure_grade_edit,
            self.build_date_edit,
            self.renovation_date_edit,
            self.length_edit,
            self.increased_flow_edit,
            self.lining_form_edit,
            self.lining_thickness_edit,
            self.concrete_strength_edit,
            self.inlet_outlet_bottom_elevation_edit,
            self.longitudinal_slope_edit,
            self.section_form_edit,
            self.section_width_edit,
            self.section_height_edit,
            self.cover_thickness_edit,
            self.overall_grade_buttons["A"],
            self.overall_grade_buttons["B"],
            self.overall_grade_buttons["C"],
            self.overall_grade_buttons["D"],
            self.survey_date_edit,
            self.survey_comment_edit,
            self.save_button,
            self.complete_button,
            self.back_button,
        ]

        for current_widget, next_widget in zip(
            widgets,
            widgets[1:],
        ):
            QWidget.setTabOrder(
                current_widget,
                next_widget,
            )

    def _setup_keyboard_shortcuts(self):
        """
        高频调查录入快捷键。

        Ctrl+S：
            保存当前调查。

        Ctrl+Enter：
            执行完成调查，
            不绕过完整性校验和确认。
        """

        self.save_shortcut = QShortcut(
            QKeySequence("Ctrl+S"),
            self,
        )

        self.save_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self.save_shortcut.activated.connect(self.save_draft)

        # 主键盘 Enter。
        self.complete_shortcut = QShortcut(
            QKeySequence("Ctrl+Return"),
            self,
        )

        self.complete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self.complete_shortcut.activated.connect(self._complete_from_shortcut)

        # 数字小键盘 Enter。
        self.complete_enter_shortcut = QShortcut(
            QKeySequence("Ctrl+Enter"),
            self,
        )

        self.complete_enter_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )

        self.complete_enter_shortcut.activated.connect(self._complete_from_shortcut)

    def _complete_from_shortcut(self):
        if not self.complete_button.isEnabled():
            return

        self.complete_survey()

    def _connect_dirty_tracking(self):
        """
        监听用户实际修改。

        程序进行 setText() 回填时，
        不应错误标记为用户修改。
        """

        line_edits = [
            self.name_edit,
            self.start_stake_edit,
            self.end_stake_edit,
            self.design_flow_edit,
            self.structure_grade_edit,
            self.build_date_edit,
            self.renovation_date_edit,
            self.length_edit,
            self.increased_flow_edit,
            self.lining_form_edit,
            self.lining_thickness_edit,
            self.concrete_strength_edit,
            self.inlet_outlet_bottom_elevation_edit,
            self.longitudinal_slope_edit,
            self.section_form_edit,
            self.section_width_edit,
            self.section_height_edit,
            self.cover_thickness_edit,
            self.survey_date_edit,
        ]

        for edit in line_edits:
            edit.textEdited.connect(self._mark_dirty)

        user_combos = [
            self.department_combo,
            self.office_combo,
            self.canal_combo,
        ]

        for combo in user_combos:
            combo.activated.connect(self._mark_dirty)

        for button in self.overall_grade_buttons.values():
            button.clicked.connect(self._mark_dirty)

        self.evaluation_section.grade_changed.connect(self._mark_dirty)

        self.survey_comment_edit.textChanged.connect(self._mark_dirty)

    def _mark_dirty(
        self,
        *args,
    ):
        self.is_dirty = True

    def confirm_leave_changes(self):
        """
        页面存在未保存修改时，
        询问用户如何处理。

        True：
            允许离开。

        False：
            继续停留当前页面。
        """

        if not self.is_dirty:
            return True

        reply = QMessageBox.question(
            self,
            "存在未保存修改",
            (
                "当前调查表存在尚未保存的修改。\n\n"
                "选择“保存”将先保存当前草稿再离开；\n"
                "选择“不保存”将放弃本次修改；\n"
                "选择“取消”将继续留在当前页面。"
            ),
            (
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            ),
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Save:
            return bool(self._save_current_draft(show_message=True))

        if reply == QMessageBox.StandardButton.Discard:
            self.is_dirty = False
            return True

        return False

    def request_back(self):
        if not self.confirm_leave_changes():
            return

        self.back_requested.emit()

    # =========================================================
    # 组织机构与渠系
    # =========================================================

    def load_departments(self):
        self.department_combo.blockSignals(True)

        self.department_combo.clear()

        for department in get_departments():
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

    # =========================================================
    # 业务编号
    # =========================================================

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

            if not department_code:
                raise ValueError("当前基层处没有业务代码。")

            if not office_code:
                raise ValueError("当前水管所没有业务代码。")

            engineering_type_code = get_engineering_type_code("form_2_5")

            existing_codes = get_engineering_business_codes(
                self.current_context["project_id"]
            )

            sequence = suggest_next_sequence(
                existing_codes=existing_codes,
                department_code=str(department_code),
                water_office_code=str(office_code),
                canal_level_code=str(canal_data["canal_level"]),
                engineering_type_code=(engineering_type_code),
            )

            business_code = build_business_code(
                department_code=str(department_code),
                water_office_code=str(office_code),
                canal_level_code=str(canal_data["canal_level"]),
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

    # =========================================================
    # 基本数据
    # =========================================================

    def collect_basic_data(self):
        """
        收集附表2.5正式基本信息。
        """

        asset_name = self.name_edit.text().strip()

        (
            start_stake_text,
            start_stake_value,
        ) = parse_stake(self.start_stake_edit.text())

        (
            end_stake_text,
            end_stake_value,
        ) = parse_stake(self.end_stake_edit.text())

        record_data = {
            "asset_name": (asset_name or None),
            "start_stake": (start_stake_text),
            "start_stake_value": (start_stake_value),
            "end_stake": (end_stake_text),
            "end_stake_value": (end_stake_value),
            "design_flow": (get_optional_float(self.design_flow_edit)),
            "structure_grade": (get_optional_text(self.structure_grade_edit)),
            "build_date": (
                get_optional_month(
                    self.build_date_edit,
                    "建成年月",
                )
            ),
            "renovation_date": (
                get_optional_month(
                    self.renovation_date_edit,
                    "加固改造年月",
                )
            ),
            "length": (get_optional_float(self.length_edit)),
            "increased_flow": (get_optional_float(self.increased_flow_edit)),
            "lining_form": (get_optional_text(self.lining_form_edit)),
            "lining_thickness": (get_optional_float(self.lining_thickness_edit)),
            "concrete_strength": (get_optional_text(self.concrete_strength_edit)),
            "inlet_outlet_bottom_elevation": (
                get_optional_text(self.inlet_outlet_bottom_elevation_edit)
            ),
            "longitudinal_slope": (get_optional_float(self.longitudinal_slope_edit)),
            "section_form": (get_optional_text(self.section_form_edit)),
            "section_width": (get_optional_float(self.section_width_edit)),
            "section_height": (get_optional_float(self.section_height_edit)),
            "cover_thickness": (get_optional_float(self.cover_thickness_edit)),
        }

        return {
            "asset_name": asset_name,
            "start_stake_text": (start_stake_text),
            "start_stake_value": (start_stake_value),
            "end_stake_text": (end_stake_text),
            "end_stake_value": (end_stake_value),
            "record_data": record_data,
        }

    # =========================================================
    # 草稿保存
    # =========================================================

    def _save_current_draft(
        self,
        show_message=True,
    ):
        try:
            # 已完成记录允许继续修改，
            # 但保存后必须仍然满足
            # completed 的全部完整性要求。
            if self.editing_record_status == "completed":
                self._validate_completion_fields()

            self.current_context = get_current_context()

            if not self.current_context:
                raise ValueError("当前没有可用项目。")

            if self.current_context["batch_id"] is None:
                raise ValueError("当前没有启用的调查批次。")

            self.form_version = get_current_form_version("form_2_5")

            if self.form_version is None:
                raise ValueError("未找到附表2.5当前版本。")

            # =============================================
            # 工程归属
            # =============================================

            department_data = self.department_combo.currentData()

            office_data = self.office_combo.currentData()

            canal_data = self.canal_combo.currentData()

            if not department_data:
                raise ValueError("请选择基层处。")

            if not office_data:
                raise ValueError("请选择水管所。")

            if not canal_data:
                raise ValueError("请选择所属渠系。")

            # =============================================
            # 基本信息
            # =============================================

            basic_data = self.collect_basic_data()

            asset_name = basic_data["asset_name"]

            if not asset_name:
                raise ValueError("名称不能为空。")

            business_code = self.business_code_edit.text().strip()

            if not business_code:
                raise ValueError("业务编号尚未生成。")

            start_stake_text = basic_data["start_stake_text"]

            start_stake_value = basic_data["start_stake_value"]

            end_stake_text = basic_data["end_stake_text"]

            end_stake_value = basic_data["end_stake_value"]

            record_data = basic_data["record_data"]

            inspection_results = self._collect_evaluation_results()

            survey_date = get_optional_date(
                self.survey_date_edit,
                "调查时间",
            )

            overall_grade = self._get_overall_grade()

            survey_comment = self.survey_comment_edit.toPlainText().strip() or None

            # =============================================
            # 第一次保存：创建
            # =============================================

            if self.editing_record_id is None:
                result = create_range_engineering_survey(
                    project_id=(self.current_context["project_id"]),
                    survey_batch_id=(self.current_context["batch_id"]),
                    form_version_id=(self.form_version["id"]),
                    asset_name=(basic_data["asset_name"]),
                    asset_type="tunnel",
                    organization_unit_id=(office_data["id"]),
                    canal_unit_id=(canal_data["id"]),
                    business_code=(business_code),
                    record_data=(basic_data["record_data"]),
                    start_stake_text=(basic_data["start_stake_text"]),
                    start_stake_value=(basic_data["start_stake_value"]),
                    end_stake_text=(basic_data["end_stake_text"]),
                    end_stake_value=(basic_data["end_stake_value"]),
                    inspection_results=(inspection_results),
                    survey_date=survey_date,
                    overall_grade=overall_grade,
                    survey_comment=survey_comment,
                )

                self.editing_record_id = int(result["survey_record_id"])

                self.editing_record_status = "draft"

            # =============================================
            # 后续保存：修改原记录
            # =============================================

            else:
                update_range_engineering_survey(
                    survey_record_id=(self.editing_record_id),
                    form_code="form_2_5",
                    asset_name=(basic_data["asset_name"]),
                    record_data=(basic_data["record_data"]),
                    start_stake_text=(basic_data["start_stake_text"]),
                    start_stake_value=(basic_data["start_stake_value"]),
                    end_stake_text=(basic_data["end_stake_text"]),
                    end_stake_value=(basic_data["end_stake_value"]),
                    inspection_results=(inspection_results),
                    survey_date=survey_date,
                    overall_grade=overall_grade,
                    survey_comment=survey_comment,
                )

            # =============================================
            # 工程建立后锁定归属
            # =============================================

            self.department_combo.setEnabled(False)

            self.office_combo.setEnabled(False)

            self.canal_combo.setEnabled(False)

            if self.editing_record_status == "completed":
                self.title_label.setText(
                    "附表2.5 隧洞" "工程状况调查 - " "编辑已完成记录"
                )

                self.save_button.setText("保存修改")

                self.complete_button.setEnabled(False)

            else:
                self.title_label.setText("附表2.5 隧洞" "工程状况调查 - 编辑草稿")

                self.save_button.setText("保存草稿")

                self.complete_button.setEnabled(True)

            self.is_dirty = False

            self.save_button.setEnabled(True)

            self.complete_button.setEnabled(True)

            self.survey_saved.emit()

            if show_message:
                if self.editing_record_status == "completed":
                    message = (
                        "当前已完成调查的修改"
                        "已保存。\n\n"
                        f"业务编号："
                        f"{business_code}"
                    )

                else:
                    message = (
                        "当前调查草稿已保存。\n\n" f"业务编号：" f"{business_code}"
                    )

                QMessageBox.information(
                    self,
                    "保存成功",
                    message,
                )

            return True

        except Exception as error:
            if show_message:
                QMessageBox.warning(
                    self,
                    "保存失败",
                    str(error),
                )

                return False

            raise

    def save_draft(self):
        """
        保存当前附表2.5草稿。
        """

        self._save_current_draft(show_message=True)

    def _validate_completion_fields(self):
        """
        校验附表2.5完成调查所需内容。

        草稿允许不完整；
        completed 保存修改和完成调查时
        必须满足全部正式要求。
        """

        required_line_edits = [
            (
                self.name_edit,
                "名称",
            ),
            (
                self.start_stake_edit,
                "起始桩号",
            ),
            (
                self.end_stake_edit,
                "终止桩号",
            ),
            (
                self.design_flow_edit,
                "设计流量",
            ),
            (
                self.structure_grade_edit,
                "建筑物等级",
            ),
            (
                self.build_date_edit,
                "建成年月",
            ),
            (
                self.length_edit,
                "长度",
            ),
            (
                self.increased_flow_edit,
                "加大流量",
            ),
            (
                self.lining_form_edit,
                "衬砌形式",
            ),
            (
                self.lining_thickness_edit,
                "衬砌厚度",
            ),
            (
                self.concrete_strength_edit,
                "混凝土强度",
            ),
            (
                self.inlet_outlet_bottom_elevation_edit,
                "进出口底部高程",
            ),
            (
                self.longitudinal_slope_edit,
                "纵坡（n/1000）",
            ),
            (
                self.section_form_edit,
                "断面型式",
            ),
            (
                self.section_width_edit,
                "尺寸（宽）",
            ),
            (
                self.section_height_edit,
                "尺寸（高）",
            ),
            (
                self.cover_thickness_edit,
                "钢筋保护层厚度",
            ),
            (
                self.survey_date_edit,
                "调查时间",
            ),
        ]

        missing_fields = []

        for edit, field_name in required_line_edits:
            if not edit.text().strip():
                missing_fields.append(field_name)

        if not (self.survey_comment_edit.toPlainText().strip()):
            missing_fields.append("调查意见与建议")

        if self._get_overall_grade() not in (
            "A",
            "B",
            "C",
            "D",
        ):
            missing_fields.append("工程状况类别")

        evaluation_results = self._collect_evaluation_results()

        evaluated_count = sum(
            1
            for result in evaluation_results
            if result.get("grade")
            in (
                "A",
                "B",
                "C",
                "D",
            )
        )

        evaluation_total = len(TUNNEL_EVALUATION_ITEMS)

        if evaluated_count != evaluation_total:
            missing_fields.append("全部13项分项评价")

        if missing_fields:
            raise ValueError(
                "完成调查前仍有必填内容未填写：" + "、".join(missing_fields) + "。"
            )

        # collect_basic_data 会统一校验：
        # 桩号、年月、数值输入格式等。
        basic_data = self.collect_basic_data()

        start_stake_value = basic_data["start_stake_value"]

        end_stake_value = basic_data["end_stake_value"]

        if (
            start_stake_value is not None
            and end_stake_value is not None
            and end_stake_value < start_stake_value
        ):
            raise ValueError("终止桩号不能小于起始桩号。")

        # 再触发正式调查日期格式校验。
        get_optional_date(
            self.survey_date_edit,
            "调查时间",
        )

    def complete_survey(self):
        """
        保存页面最新内容，
        再将附表2.5调查推进为 completed。
        """

        try:
            # 已完成记录不应再次执行
            # draft -> completed。
            #
            # 正常UI中已完成记录的
            # “完成调查”按钮本身会禁用；
            # 这里保留数据库操作前的
            # 防御性检查。
            if (
                self.editing_record_status
                == "completed"
            ):
                raise ValueError(
                    "当前调查已经完成，"
                    "无需再次执行完成调查。"
                )

            self._validate_completion_fields()

            # =================================================
            # 1. 页面端完整性校验
            # =================================================

            self._validate_completion_fields()

            # =================================================
            # 2. 用户确认
            # =================================================

            reply = QMessageBox.question(
                self,
                "确认完成调查",
                (
                    "系统将先保存当前页面的全部修改，"
                    "然后把本次调查标记为“已完成”。\n\n"
                    "是否确认完成本次调查？"
                ),
                (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # =================================================
            # 3. 先保存最新页面内容
            # =================================================

            saved = self._save_current_draft(show_message=False)

            if not saved:
                raise ValueError("当前页面保存失败，" "因此没有执行完成调查。")

            if self.editing_record_id is None:
                raise ValueError("没有有效的调查记录ID。")

            # =================================================
            # 4. 数据库正式完成
            # =================================================

            result = complete_tunnel_record(self.editing_record_id)

            self.editing_record_status = "completed"

            self.is_dirty = False

            # 先刷新列表数据源。
            self.survey_saved.emit()

            # 保存当前调查日期。
            # 连续录入下一条时继续沿用。
            previous_survey_date = self.survey_date_edit.text().strip()

            success_box = QMessageBox(self)

            success_box.setIcon(QMessageBox.Icon.Information)

            success_box.setWindowTitle("完成成功")

            success_box.setText(
                (
                    "当前隧洞调查"
                    "已标记为已完成。\n\n"
                    f"调查记录ID："
                    f"{result['survey_record_id']}\n"
                    f"已填写分项评价："
                    f"{result['inspection_count']} 项\n\n"
                    "是否继续录入下一条"
                    "隧洞调查？"
                )
            )

            continue_button = success_box.addButton(
                "继续录入下一条",
                QMessageBox.ButtonRole.AcceptRole,
            )

            return_button = success_box.addButton(
                "返回列表",
                QMessageBox.ButtonRole.RejectRole,
            )

            success_box.setDefaultButton(continue_button)

            success_box.setEscapeButton(return_button)

            success_box.exec()

            # =================================================
            # 继续下一条
            # =================================================

            if success_box.clickedButton() is continue_button:
                # prepare_new()：
                # 1. 保留处 / 所 / 渠系；
                # 2. 重新生成业务编号；
                # 3. 清空工程信息；
                # 4. 清空评价与调查结论。
                self.prepare_new()

                # 连续录入时保留上一条调查日期，
                # 而不是重新使用系统当天。
                if previous_survey_date:
                    self.survey_date_edit.setText(previous_survey_date)

                # 上述初始化均属于程序行为。
                self.is_dirty = False

                QTimer.singleShot(
                    0,
                    self._focus_new_entry_start,
                )

                return

            # =================================================
            # 返回列表
            # =================================================

            self.back_requested.emit()
            return

        except Exception as error:
            QMessageBox.warning(
                self,
                "完成失败",
                str(error),
            )

    # =========================================================
    # Combo 辅助
    # =========================================================

    def _set_combo_by_id(
        self,
        combo,
        target_id,
    ):
        """
        根据 combo 数据中的 id
        找到并选中指定对象。
        """

        if target_id is None:
            return False

        for index in range(combo.count()):
            data = combo.itemData(index)

            if isinstance(data, dict) and data.get("id") == target_id:
                combo.setCurrentIndex(index)

                return True

        return False

    # =========================================================
    # 打开已有草稿
    # =========================================================

    def load_record(
        self,
        survey_record_id,
    ):
        """
        打开已有附表2.5隧洞调查记录。

        支持：
        - draft 草稿继续编辑；
        - completed 已完成记录继续修改。
        """

        record = get_range_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_5",
        )

        if record is None:
            raise ValueError("没有找到该附表2.5调查记录。")

        assert record is not None

        record_status = record["record_status"]

        if record_status not in (
            "draft",
            "completed",
        ):
            raise ValueError("当前记录状态暂不支持打开。")

        self.current_context = get_current_context()

        self.form_version = get_current_form_version("form_2_5")

        self.editing_record_id = int(record["survey_record_id"])

        self.editing_record_status = record_status

        # =====================================================
        # 1. 回填归属
        # =====================================================

        self.load_departments()

        department_found = self._set_combo_by_id(
            self.department_combo,
            record["department_id"],
        )

        if not department_found:
            raise ValueError("该调查记录所属基层处" "已不存在或不可用。")

        self.department_changed()

        office_found = self._set_combo_by_id(
            self.office_combo,
            record["office_id"],
        )

        if not office_found:
            raise ValueError("该调查记录所属水管所" "已不存在或不可用。")

        self.office_changed()

        canal_found = self._set_combo_by_id(
            self.canal_combo,
            record["canal_id"],
        )

        if not canal_found:
            raise ValueError("该调查记录所属渠系" "已不存在或不可用。")

        self.business_code_edit.setText(record["business_code"] or "")

        self.department_combo.setEnabled(False)

        self.office_combo.setEnabled(False)

        self.canal_combo.setEnabled(False)

        # =====================================================
        # 2. 回填基本信息
        # =====================================================

        data = record["record_data"] or {}

        self.name_edit.setText(record["asset_name"] or "")

        self.start_stake_edit.setText(record["start_stake_text"] or "")

        self.end_stake_edit.setText(record["end_stake_text"] or "")

        def set_optional(
            edit,
            value,
        ):
            edit.setText("" if value is None else str(value))

        set_optional(
            self.design_flow_edit,
            data.get("design_flow"),
        )

        self.structure_grade_edit.setText(data.get("structure_grade") or "")

        self.build_date_edit.setText(data.get("build_date") or "")

        self.renovation_date_edit.setText(data.get("renovation_date") or "")

        set_optional(
            self.length_edit,
            data.get("length"),
        )

        set_optional(
            self.increased_flow_edit,
            data.get("increased_flow"),
        )

        self.lining_form_edit.setText(data.get("lining_form") or "")

        set_optional(
            self.lining_thickness_edit,
            data.get("lining_thickness"),
        )

        self.concrete_strength_edit.setText(data.get("concrete_strength") or "")

        self.inlet_outlet_bottom_elevation_edit.setText(
            data.get("inlet_outlet_bottom_elevation") or ""
        )

        set_optional(
            self.longitudinal_slope_edit,
            data.get("longitudinal_slope"),
        )

        self.section_form_edit.setText(data.get("section_form") or "")

        set_optional(
            self.section_width_edit,
            data.get("section_width"),
        )

        set_optional(
            self.section_height_edit,
            data.get("section_height"),
        )

        set_optional(
            self.cover_thickness_edit,
            data.get("cover_thickness"),
        )

        # =====================================================
        # 3. 分项评价
        # =====================================================

        self._clear_evaluation_controls()

        inspection_results = get_inspection_results(survey_record_id)

        self._load_evaluation_results(inspection_results)

        # =====================================================
        # 4. 调查结论
        # =====================================================

        self._set_overall_grade(record.get("overall_grade"))

        self.survey_date_edit.setText(record.get("survey_date") or "")

        self.survey_comment_edit.setPlainText(record.get("survey_comment") or "")

        # =====================================================
        # 5. 页面状态
        # =====================================================

        if record_status == "draft":
            self.title_label.setText("附表2.5 隧洞工程状况调查" " - 编辑草稿")

            self.save_button.setText("保存草稿")

            self.save_button.setEnabled(True)

            self.complete_button.setEnabled(True)

        else:
            self.title_label.setText("附表2.5 隧洞工程状况调查" " - 编辑已完成记录")

            self.save_button.setText("保存修改")

            self.save_button.setEnabled(True)

            self.complete_button.setEnabled(False)

        self.department_combo.setEnabled(False)

        self.office_combo.setEnabled(False)

        self.canal_combo.setEnabled(False)

        self.is_dirty = False

    # =========================================================
    # 新增状态
    # =========================================================
    def _focus_new_entry_start(self):
        """
        连续录入下一条时回到表单顶部，
        并聚焦第一个工程信息字段。
        """

        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().minimum()
        )

        self.name_edit.setFocus()

    def prepare_new(self):
        """
        切换到附表2.5新增模式。

        优先保留上一条记录的
        基层处、水管所和渠系。
        """

        previous_department_data = self.department_combo.currentData()

        previous_office_data = self.office_combo.currentData()

        previous_canal_data = self.canal_combo.currentData()

        previous_department_id = (
            previous_department_data.get("id")
            if isinstance(
                previous_department_data,
                dict,
            )
            else None
        )

        previous_office_id = (
            previous_office_data.get("id")
            if isinstance(
                previous_office_data,
                dict,
            )
            else None
        )

        previous_canal_id = (
            previous_canal_data.get("id")
            if isinstance(
                previous_canal_data,
                dict,
            )
            else None
        )

        self.current_context = get_current_context()

        self.form_version = get_current_form_version("form_2_5")

        self.editing_record_id = None
        self.editing_record_status = None

        self.title_label.setText("附表2.5 隧洞工程状况调查 - 新增")

        self.save_button.setText("保存草稿")

        self.save_button.setEnabled(True)

        self.complete_button.setEnabled(True)

        self.department_combo.setEnabled(True)

        self.office_combo.setEnabled(True)

        self.canal_combo.setEnabled(True)

        # 基本信息
        self.name_edit.clear()

        self.start_stake_edit.clear()
        self.end_stake_edit.clear()

        self.design_flow_edit.clear()

        self.structure_grade_edit.clear()

        self.build_date_edit.clear()

        self.renovation_date_edit.clear()

        self.length_edit.clear()

        self.increased_flow_edit.clear()

        # 结构与断面参数
        self.lining_form_edit.clear()

        self.lining_thickness_edit.clear()

        self.concrete_strength_edit.clear()

        self.inlet_outlet_bottom_elevation_edit.clear()

        self.longitudinal_slope_edit.clear()

        self.section_form_edit.clear()

        self.section_width_edit.clear()

        self.section_height_edit.clear()

        self.cover_thickness_edit.clear()

        # 评价与调查结论
        self._clear_evaluation_controls()

        self._clear_overall_grade()

        self.survey_comment_edit.clear()

        self.survey_date_edit.setText(datetime.now().strftime("%Y-%m-%d"))

        # 重新加载归属
        self.load_departments()

        department_restored = False
        office_restored = False

        if previous_department_id is not None:
            department_restored = self._set_combo_by_id(
                self.department_combo,
                previous_department_id,
            )

        if department_restored:
            self.department_changed()

            if previous_office_id is not None:
                office_restored = self._set_combo_by_id(
                    self.office_combo,
                    previous_office_id,
                )

        if office_restored:
            self.office_changed()

            if previous_canal_id is not None:
                self._set_combo_by_id(
                    self.canal_combo,
                    previous_canal_id,
                )

        self.update_business_code()

        self.is_dirty = False
