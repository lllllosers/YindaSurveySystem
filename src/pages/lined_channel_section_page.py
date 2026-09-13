from datetime import datetime
from PySide6.QtCore import (
    QRegularExpression,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QDoubleValidator,
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
    create_lined_channel_section_survey,
    get_canal_units_for_organization,
    get_current_context,
    get_current_form_version,
    get_departments,
    get_engineering_business_codes,
    get_lined_channel_section_record,
    get_water_offices,
    update_lined_channel_section_draft,
    complete_lined_channel_section_record,
    get_inspection_results,
)

from services.lined_channel_evaluation import (
    LINED_CHANNEL_EVALUATION_ITEMS,
)

from services.business_code import (
    build_business_code,
    get_engineering_type_code,
    suggest_next_sequence,
)

from services.stake import parse_stake
from pages.components.evaluation_section import (
    EvaluationSection,
)


class LinedChannelSectionPage(QWidget):
    survey_saved = Signal()
    back_requested = Signal()

    def __init__(self):
        super().__init__()

        self.editing_record_id = None
        self.editing_record_status = None

        self.current_context = None
        self.form_version = None

        self.is_dirty = False

        self.evaluation_section: EvaluationSection

        self.init_ui()
        self._connect_dirty_tracking()

    # =========================================================
    # UI
    # =========================================================

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(18)

        self.title_label = QLabel("附表2.1 防渗衬砌渠道渠段工程状况调查")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")

        root_layout.addWidget(self.title_label)

        description = QLabel(
            "填写附表2.1基本信息、分项评价及调查结论。"
            "草稿允许暂时不完整；"
            "完成调查前系统将检查全部必填内容。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #607080; font-size: 14px;")

        root_layout.addWidget(description)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        form_container = QWidget()

        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(
            4,
            4,
            12,
            4,
        )
        form_layout.setSpacing(16)

        # =========================
        # 一、归属与编号
        # =========================

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

        # =========================
        # 二、渠段基本信息
        # =========================

        basic_group = QGroupBox("二、渠段基本信息")

        basic_layout = QFormLayout(basic_group)

        self._setup_form_layout(basic_layout)

        self.channel_name_edit = QLineEdit()
        self.channel_name_edit.setPlaceholderText("填写渠道名称")

        self.start_stake_edit = QLineEdit()
        self.start_stake_edit.setPlaceholderText("例如：K12+000")

        self.end_stake_edit = QLineEdit()
        self.end_stake_edit.setPlaceholderText("例如：K13+250")

        self.section_length_edit = self._create_nonnegative_decimal_edit("例如：1250")

        self.build_date_edit = self._create_month_edit()
        self.build_date_edit.setPlaceholderText("例如：2008-06")

        self.renovation_date_edit = self._create_month_edit()
        self.renovation_date_edit.setPlaceholderText("例如：2021-09，可留空")

        self.longitudinal_slope_edit = QLineEdit()
        self.longitudinal_slope_edit.setPlaceholderText("按原始资料填写，例如 1/2000")

        self.design_flow_edit = self._create_nonnegative_decimal_edit()

        self.channel_grade_edit = QLineEdit()
        self.channel_grade_edit.setPlaceholderText("按原始资料填写")

        self.cross_section_form_edit = QLineEdit()
        self.cross_section_form_edit.setPlaceholderText("例如：梯形、矩形等")

        basic_layout.addRow(
            "渠道名称：",
            self.channel_name_edit,
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
            "渠段长度（m）：",
            self.section_length_edit,
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
            "纵比降：",
            self.longitudinal_slope_edit,
        )
        basic_layout.addRow(
            "设计流量（m³/s）：",
            self.design_flow_edit,
        )
        basic_layout.addRow(
            "渠道等级：",
            self.channel_grade_edit,
        )
        basic_layout.addRow(
            "渠道断面形式：",
            self.cross_section_form_edit,
        )

        form_layout.addWidget(basic_group)

        # =========================
        # 三、断面与渠体参数
        # =========================

        section_group = QGroupBox("三、断面与渠体参数")

        section_layout = QFormLayout(section_group)

        self._setup_form_layout(section_layout)

        self.embankment_top_width_edit = self._create_nonnegative_decimal_edit()

        self.inner_slope_edit = QLineEdit()
        self.inner_slope_edit.setPlaceholderText("内边坡，按原始资料填写")

        self.outer_slope_edit = QLineEdit()
        self.outer_slope_edit.setPlaceholderText("外边坡，按原始资料填写")

        self.increased_flow_edit = self._create_nonnegative_decimal_edit()

        self.bed_soil_edit = QLineEdit()

        self.lining_structure_edit = QLineEdit()

        self.freeboard_edit = self._create_nonnegative_decimal_edit()

        self.bottom_width_edit = self._create_nonnegative_decimal_edit()

        self.water_conveyance_loss_edit = self._create_nonnegative_decimal_edit()

        section_layout.addRow(
            "堤顶宽度（m）：",
            self.embankment_top_width_edit,
        )
        section_layout.addRow(
            "渠道边坡（内）：",
            self.inner_slope_edit,
        )
        section_layout.addRow(
            "渠道边坡（外）：",
            self.outer_slope_edit,
        )
        section_layout.addRow(
            "加大流量（m³/s）：",
            self.increased_flow_edit,
        )
        section_layout.addRow(
            "渠床土质：",
            self.bed_soil_edit,
        )
        section_layout.addRow(
            "防渗衬砌结构：",
            self.lining_structure_edit,
        )
        section_layout.addRow(
            "安全超高（m）：",
            self.freeboard_edit,
        )
        section_layout.addRow(
            "渠底宽度（m）：",
            self.bottom_width_edit,
        )
        section_layout.addRow(
            "输水损失（m³/km）：",
            self.water_conveyance_loss_edit,
        )

        form_layout.addWidget(section_group)

        # =========================
        # 四、衬砌及高程参数
        # =========================

        lining_group = QGroupBox("四、衬砌及高程参数")

        lining_layout = QFormLayout(lining_group)

        self._setup_form_layout(lining_layout)

        self.lining_material_edit = QLineEdit()

        self.lining_thickness_edit = self._create_nonnegative_decimal_edit()

        self.concrete_strength_edit = QLineEdit()
        self.concrete_strength_edit.setPlaceholderText("例如：C20、C25")

        self.channel_depth_edit = self._create_nonnegative_decimal_edit()

        self.channel_bottom_elevation_edit = self._create_signed_decimal_edit()

        lining_layout.addRow(
            "衬砌材料：",
            self.lining_material_edit,
        )
        lining_layout.addRow(
            "衬砌厚度（cm）：",
            self.lining_thickness_edit,
        )
        lining_layout.addRow(
            "混凝土强度：",
            self.concrete_strength_edit,
        )
        lining_layout.addRow(
            "渠深（m）：",
            self.channel_depth_edit,
        )
        lining_layout.addRow(
            "渠底高程（m）：",
            self.channel_bottom_elevation_edit,
        )

        form_layout.addWidget(lining_group)

        # =========================
        # 五、分项评价
        # =========================

        evaluation_group = self._create_evaluation_group()

        form_layout.addWidget(evaluation_group)

        # =========================
        # 六、调查结论
        # =========================

        conclusion_group = QGroupBox("六、调查结论")

        conclusion_layout = QFormLayout(conclusion_group)

        self._setup_form_layout(conclusion_layout)

        self.overall_grade_combo = QComboBox()

        self.overall_grade_combo.addItem(
            "未确定",
            None,
        )

        for grade in (
            "A",
            "B",
            "C",
            "D",
        ):
            self.overall_grade_combo.addItem(
                grade,
                grade,
            )

        self.survey_date_edit = self._create_date_edit()

        self.survey_date_edit.setPlaceholderText("例如：2026-09-13")

        self.survey_comment_edit = QPlainTextEdit()

        self.survey_comment_edit.setPlaceholderText("填写调查意见与建议")

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

        form_layout.addWidget(conclusion_group)

        form_layout.addStretch()

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
        back_button.clicked.connect(self.request_back)

        self.save_button = QPushButton("保存草稿")
        self.complete_button = QPushButton("完成调查")
        self.complete_button.setMinimumWidth(120)
        self.complete_button.clicked.connect(self.complete_survey)
        self.save_button.setMinimumWidth(120)
        self.save_button.clicked.connect(self.save_draft)

        button_layout.addWidget(back_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.complete_button)

        root_layout.addLayout(button_layout)

    # =========================================================
    # UI helpers
    # =========================================================
    def _create_evaluation_group(self):
        """
        创建附表2.1分项评价区域。

        实际控件生成、标准显示、
        回填和结果收集由公共组件负责。
        """

        self.evaluation_section = EvaluationSection(
            title="五、分项评价",
            evaluation_items=(LINED_CHANNEL_EVALUATION_ITEMS),
            description=("各项目选择 A、B、C、D 后，" "系统显示原调查表对应评价标准。"),
        )

        return self.evaluation_section

    def _clear_evaluation_controls(
        self,
    ):
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

    def _create_nonnegative_decimal_edit(
        self,
        placeholder="可留空",
    ):
        edit = QLineEdit()

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

    def _create_signed_decimal_edit(
        self,
        placeholder="可留空",
    ):
        edit = QLineEdit()

        edit.setPlaceholderText(placeholder)

        validator = QDoubleValidator(
            -999999999.0,
            999999999.0,
            6,
            edit,
        )

        validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        edit.setValidator(validator)

        return edit

    def _create_date_edit(self):
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
        text = edit.text().strip()

        if not text:
            return None

        expression = QRegularExpression(
            r"^\d{4}-(0[1-9]|1[0-2])-" r"(0[1-9]|[12]\d|3[01])$"
        )

        if not expression.match(text).hasMatch():
            raise ValueError(f"{field_name}格式应为 " "YYYY-MM-DD。")

        return text

    def _create_month_edit(self):
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
        text = edit.text().strip()

        if not text:
            return None

        return float(text)

    def _get_optional_text(
        self,
        edit,
    ):
        return edit.text().strip() or None

    def _get_optional_month(
        self,
        edit,
        field_name,
    ):
        text = edit.text().strip()

        if not text:
            return None

        expression = QRegularExpression(r"^\d{4}-(0[1-9]|1[0-2])$")

        if not expression.match(text).hasMatch():
            raise ValueError(f"{field_name}格式应为 YYYY-MM，" "例如：2008-06。")

        return text

    # =========================================================
    # 脏数据保护
    # =========================================================

    def _connect_dirty_tracking(self):
        line_edits = [
            self.channel_name_edit,
            self.start_stake_edit,
            self.end_stake_edit,
            self.section_length_edit,
            self.build_date_edit,
            self.renovation_date_edit,
            self.longitudinal_slope_edit,
            self.design_flow_edit,
            self.channel_grade_edit,
            self.cross_section_form_edit,
            self.embankment_top_width_edit,
            self.inner_slope_edit,
            self.outer_slope_edit,
            self.increased_flow_edit,
            self.bed_soil_edit,
            self.lining_structure_edit,
            self.freeboard_edit,
            self.bottom_width_edit,
            self.water_conveyance_loss_edit,
            self.lining_material_edit,
            self.lining_thickness_edit,
            self.concrete_strength_edit,
            self.channel_depth_edit,
            self.channel_bottom_elevation_edit,
            self.survey_date_edit,
        ]

        for edit in line_edits:
            edit.textEdited.connect(self._mark_dirty)

        for combo in self.evaluation_section.get_grade_combos().values():
            combo.activated.connect(self._mark_dirty)

        self.survey_comment_edit.textChanged.connect(self._mark_dirty)

    def _mark_dirty(
        self,
        *args,
    ):
        self.is_dirty = True

    def confirm_leave_changes(self):
        if not self.is_dirty:
            return True

        reply = QMessageBox.question(
            self,
            "存在未保存修改",
            (
                "当前调查表存在尚未保存的修改。\n\n"
                "选择“保存”将先保存当前内容再离开；\n"
                "选择“不保存”将放弃本次修改；\n"
                "选择“取消”将继续留在当前页面。"
            ),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
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
    # 组织机构 / 渠系 / 业务编号
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

            engineering_type_code = get_engineering_type_code("form_2_1")

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

    # =========================================================
    # 保存
    # =========================================================

    def _collect_record_data(self):
        asset_name = self.channel_name_edit.text().strip()

        if not asset_name:
            raise ValueError("渠道名称不能为空。")

        start_stake_text, start_stake_value = parse_stake(self.start_stake_edit.text())

        end_stake_text, end_stake_value = parse_stake(self.end_stake_edit.text())

        if (
            start_stake_value is not None
            and end_stake_value is not None
            and end_stake_value < start_stake_value
        ):
            raise ValueError("终止桩号不能小于起始桩号。")

        build_date = self._get_optional_month(
            self.build_date_edit,
            "建成年月",
        )

        renovation_date = self._get_optional_month(
            self.renovation_date_edit,
            "加固改造年月",
        )

        record_data = {
            "channel_name": asset_name,
            "start_stake": (start_stake_text),
            "start_stake_value": (start_stake_value),
            "end_stake": (end_stake_text),
            "end_stake_value": (end_stake_value),
            "section_length": (self._get_optional_float(self.section_length_edit)),
            "build_date": build_date,
            "renovation_date": (renovation_date),
            "longitudinal_slope": (
                self._get_optional_text(self.longitudinal_slope_edit)
            ),
            "design_flow": (self._get_optional_float(self.design_flow_edit)),
            "channel_grade": (self._get_optional_text(self.channel_grade_edit)),
            "cross_section_form": (
                self._get_optional_text(self.cross_section_form_edit)
            ),
            "embankment_top_width": (
                self._get_optional_float(self.embankment_top_width_edit)
            ),
            "inner_slope": (self._get_optional_text(self.inner_slope_edit)),
            "outer_slope": (self._get_optional_text(self.outer_slope_edit)),
            "increased_flow": (self._get_optional_float(self.increased_flow_edit)),
            "bed_soil": (self._get_optional_text(self.bed_soil_edit)),
            "lining_structure": (self._get_optional_text(self.lining_structure_edit)),
            "freeboard": (self._get_optional_float(self.freeboard_edit)),
            "bottom_width": (self._get_optional_float(self.bottom_width_edit)),
            "water_conveyance_loss": (
                self._get_optional_float(self.water_conveyance_loss_edit)
            ),
            "lining_material": (self._get_optional_text(self.lining_material_edit)),
            "lining_thickness": (self._get_optional_float(self.lining_thickness_edit)),
            "concrete_strength": (self._get_optional_text(self.concrete_strength_edit)),
            "channel_depth": (self._get_optional_float(self.channel_depth_edit)),
            "channel_bottom_elevation": (
                self._get_optional_float(self.channel_bottom_elevation_edit)
            ),
        }

        return (
            asset_name,
            start_stake_text,
            start_stake_value,
            end_stake_text,
            end_stake_value,
            record_data,
        )

    def _save_current_draft(
        self,
        show_message=True,
    ):
        try:
            self.current_context = get_current_context()

            self.form_version = get_current_form_version("form_2_1")

            if not self.current_context:
                raise ValueError("当前没有可用项目。")

            if self.current_context["batch_id"] is None:
                raise ValueError("当前没有启用的调查批次。")

            if self.form_version is None:
                raise ValueError("未找到附表2.1当前版本。")

            department_data = self.department_combo.currentData()

            office_data = self.office_combo.currentData()

            canal_data = self.canal_combo.currentData()

            if not department_data:
                raise ValueError("请选择基层处。")

            if not office_data:
                raise ValueError("请选择水管所。")

            if not canal_data:
                raise ValueError("请选择所属渠系。")

            business_code = self.business_code_edit.text().strip()

            if not business_code:
                raise ValueError("业务编号尚未生成。")

            (
                asset_name,
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                record_data,
            ) = self._collect_record_data()

            inspection_results = self._collect_evaluation_results()

            survey_date = self._get_optional_date(
                self.survey_date_edit,
                "调查时间",
            )

            overall_grade = self.overall_grade_combo.currentData()

            survey_comment = self.survey_comment_edit.toPlainText().strip() or None

            if self.editing_record_id is None:
                result = create_lined_channel_section_survey(
                    project_id=(self.current_context["project_id"]),
                    survey_batch_id=(self.current_context["batch_id"]),
                    form_version_id=(self.form_version["id"]),
                    asset_name=asset_name,
                    organization_unit_id=(office_data["id"]),
                    canal_unit_id=(canal_data["id"]),
                    business_code=(business_code),
                    record_data=(record_data),
                    start_stake_text=(start_stake_text),
                    start_stake_value=(start_stake_value),
                    end_stake_text=(end_stake_text),
                    end_stake_value=(end_stake_value),
                    inspection_results=(inspection_results),
                    survey_date=survey_date,
                    overall_grade=overall_grade,
                    survey_comment=survey_comment,
                )

                self.editing_record_id = result["survey_record_id"]

                self.editing_record_status = "draft"

                message = (
                    "渠道渠段调查草稿已保存。\n\n"
                    f"业务编号：{business_code}\n"
                    f"调查记录ID："
                    f"{self.editing_record_id}"
                )

            else:
                (
                    update_lined_channel_section_draft(
                        survey_record_id=(self.editing_record_id),
                        asset_name=asset_name,
                        organization_unit_id=(office_data["id"]),
                        canal_unit_id=(canal_data["id"]),
                        business_code=(business_code),
                        record_data=(record_data),
                        start_stake_text=(start_stake_text),
                        start_stake_value=(start_stake_value),
                        end_stake_text=(end_stake_text),
                        end_stake_value=(end_stake_value),
                        inspection_results=(inspection_results),
                        survey_date=survey_date,
                        overall_grade=overall_grade,
                        survey_comment=survey_comment,
                    )
                )

                message = "渠道渠段调查草稿已更新。\n\n" f"业务编号：{business_code}"

            # 工程建立以后，
            # 当前阶段不允许直接修改归属。
            self.department_combo.setEnabled(False)
            self.office_combo.setEnabled(False)
            self.canal_combo.setEnabled(False)

            if self.editing_record_status == "completed":
                self.title_label.setText(
                    "附表2.1 防渗衬砌渠道渠段" "工程状况调查 - 编辑已完成记录"
                )

                self.save_button.setText("保存修改")

                self.complete_button.setEnabled(False)

            else:
                self.title_label.setText(
                    "附表2.1 防渗衬砌渠道渠段" "工程状况调查 - 编辑草稿"
                )

                self.save_button.setText("保存草稿")

                self.complete_button.setEnabled(True)

            self.is_dirty = False

            self.survey_saved.emit()

            if show_message:
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
        self._save_current_draft(show_message=True)

    def _validate_completion_fields(self):
        missing_fields = []

        # 归属
        if not self.department_combo.currentData():
            missing_fields.append("所属基层处")

        if not self.office_combo.currentData():
            missing_fields.append("所属水管所")

        if not self.canal_combo.currentData():
            missing_fields.append("所属渠系")

        if not (self.business_code_edit.text().strip()):
            missing_fields.append("业务编号")

        # 基本信息
        required_edits = [
            (
                self.channel_name_edit,
                "渠道名称",
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
                self.section_length_edit,
                "渠段长度",
            ),
            (
                self.build_date_edit,
                "建成年月",
            ),
            (
                self.longitudinal_slope_edit,
                "纵比降",
            ),
            (
                self.design_flow_edit,
                "设计流量",
            ),
            (
                self.channel_grade_edit,
                "渠道等级",
            ),
            (
                self.cross_section_form_edit,
                "渠道断面形式",
            ),
            (
                self.embankment_top_width_edit,
                "堤顶宽度",
            ),
            (
                self.inner_slope_edit,
                "渠道边坡（内）",
            ),
            (
                self.outer_slope_edit,
                "渠道边坡（外）",
            ),
            (
                self.increased_flow_edit,
                "加大流量",
            ),
            (
                self.bed_soil_edit,
                "渠床土质",
            ),
            (
                self.lining_structure_edit,
                "防渗衬砌结构",
            ),
            (
                self.freeboard_edit,
                "安全超高",
            ),
            (
                self.bottom_width_edit,
                "渠底宽度",
            ),
            (
                self.water_conveyance_loss_edit,
                "输水损失",
            ),
            (
                self.lining_material_edit,
                "衬砌材料",
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
                self.channel_depth_edit,
                "渠深",
            ),
            (
                self.channel_bottom_elevation_edit,
                "渠底高程",
            ),
            (
                self.survey_date_edit,
                "调查时间",
            ),
        ]

        for edit, field_name in required_edits:
            if not edit.text().strip():
                missing_fields.append(field_name)

        if self.overall_grade_combo.currentData() not in ("A", "B", "C", "D"):
            missing_fields.append("工程状况类别")

        if not (self.survey_comment_edit.toPlainText().strip()):
            missing_fields.append("调查意见与建议")

        evaluation_results = self._collect_evaluation_results()

        if len(evaluation_results) != len(LINED_CHANNEL_EVALUATION_ITEMS):
            missing_count = len(LINED_CHANNEL_EVALUATION_ITEMS) - len(
                evaluation_results
            )

            missing_fields.append("分项评价" f"（还缺 {missing_count} 项）")

        if missing_fields:
            field_text = "\n".join(f"• {field_name}" for field_name in missing_fields)

            raise ValueError("完成调查前请补充以下必填内容：" f"\n\n{field_text}")

        # 桩号及顺序
        _, start_value = parse_stake(self.start_stake_edit.text())

        _, end_value = parse_stake(self.end_stake_edit.text())

        if start_value is None or end_value is None:
            raise ValueError("起始桩号和终止桩号不能为空。")

        if end_value < start_value:
            raise ValueError("终止桩号不能小于起始桩号。")

        # 年月
        try:
            datetime.strptime(
                self.build_date_edit.text().strip(),
                "%Y-%m",
            )
        except ValueError:
            raise ValueError("建成年月不是有效年月，" "应填写为 YYYY-MM。")

        renovation_date = self.renovation_date_edit.text().strip()

        if renovation_date:
            try:
                datetime.strptime(
                    renovation_date,
                    "%Y-%m",
                )
            except ValueError:
                raise ValueError("加固改造年月不是有效年月，" "应填写为 YYYY-MM。")

        try:
            datetime.strptime(
                self.survey_date_edit.text().strip(),
                "%Y-%m-%d",
            )
        except ValueError:
            raise ValueError("调查时间不是有效日期，" "应填写为 YYYY-MM-DD。")

    def complete_survey(self):
        try:
            self._validate_completion_fields()

            reply = QMessageBox.question(
                self,
                "确认完成调查",
                (
                    "系统将先保存当前页面全部内容，"
                    "然后把本次调查标记为“已完成”。\n\n"
                    "完成后仍可从列表打开并修改。\n\n"
                    "是否确认？"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            saved = self._save_current_draft(show_message=False)

            if not saved:
                raise ValueError("当前页面保存失败，" "没有执行完成调查。")

            result = complete_lined_channel_section_record(self.editing_record_id)

            self.editing_record_status = "completed"

            self.title_label.setText(
                "附表2.1 防渗衬砌渠道渠段" "工程状况调查 - 编辑已完成记录"
            )

            self.save_button.setText("保存修改")

            self.complete_button.setEnabled(False)

            self.is_dirty = False

            QMessageBox.information(
                self,
                "完成成功",
                (
                    "本次渠道渠段调查已完成。\n\n"
                    f"调查记录ID："
                    f"{result['survey_record_id']}\n"
                    f"分项评价："
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

    # =========================================================
    # 新增 / 加载
    # =========================================================

    def _all_data_edits(self):
        return [
            self.channel_name_edit,
            self.start_stake_edit,
            self.end_stake_edit,
            self.section_length_edit,
            self.build_date_edit,
            self.renovation_date_edit,
            self.longitudinal_slope_edit,
            self.design_flow_edit,
            self.channel_grade_edit,
            self.cross_section_form_edit,
            self.embankment_top_width_edit,
            self.inner_slope_edit,
            self.outer_slope_edit,
            self.increased_flow_edit,
            self.bed_soil_edit,
            self.lining_structure_edit,
            self.freeboard_edit,
            self.bottom_width_edit,
            self.water_conveyance_loss_edit,
            self.lining_material_edit,
            self.lining_thickness_edit,
            self.concrete_strength_edit,
            self.channel_depth_edit,
            self.channel_bottom_elevation_edit,
        ]

    def prepare_new(self):
        self.current_context = get_current_context()

        self.form_version = get_current_form_version("form_2_1")

        self.editing_record_id = None
        self.editing_record_status = None

        self.title_label.setText("附表2.1 防渗衬砌渠道渠段工程状况调查 - 新增")

        self.save_button.setText("保存草稿")

        self.department_combo.setEnabled(True)
        self.office_combo.setEnabled(True)
        self.canal_combo.setEnabled(True)

        for edit in self._all_data_edits():
            edit.clear()

        self.load_departments()
        self.update_business_code()

        self.is_dirty = False

        self._clear_evaluation_controls()

        self.overall_grade_combo.setCurrentIndex(0)

        self.survey_date_edit.clear()

        self.survey_comment_edit.clear()

        self.complete_button.setEnabled(True)

    def _set_combo_by_id(
        self,
        combo,
        target_id,
    ):
        for index in range(combo.count()):
            data = combo.itemData(index)

            if isinstance(data, dict) and data.get("id") == target_id:
                combo.setCurrentIndex(index)
                return True

        return False

    def _set_optional_value(
        self,
        edit,
        value,
    ):
        edit.setText("" if value is None else str(value))

    def load_record(
        self,
        survey_record_id,
    ):
        record = get_lined_channel_section_record(survey_record_id)

        if record["record_status"] not in (
            "draft",
            "completed",
        ):
            raise ValueError("当前记录状态暂不支持打开。")

        self.current_context = get_current_context()

        self.form_version = get_current_form_version("form_2_1")

        self.editing_record_id = survey_record_id

        self.editing_record_status = record["record_status"]

        self.title_label.setText("附表2.1 防渗衬砌渠道渠段工程状况调查 - 编辑草稿")

        # =========================
        # 恢复归属
        # =========================

        self.load_departments()

        self._set_combo_by_id(
            self.department_combo,
            record["department_id"],
        )

        self.department_changed()

        self._set_combo_by_id(
            self.office_combo,
            record["organization_unit_id"],
        )

        self.office_changed()

        self._set_combo_by_id(
            self.canal_combo,
            record["canal_unit_id"],
        )

        self.business_code_edit.setText(record["business_code"])

        self.department_combo.setEnabled(False)
        self.office_combo.setEnabled(False)
        self.canal_combo.setEnabled(False)

        # =========================
        # 回填基本信息
        # =========================

        data = record["record_data"] or {}

        self.channel_name_edit.setText(record["asset_name"])

        self.start_stake_edit.setText(record["start_stake_text"])

        self.end_stake_edit.setText(record["end_stake_text"])

        self._set_optional_value(
            self.section_length_edit,
            data.get("section_length"),
        )

        self.build_date_edit.setText(data.get("build_date") or "")

        self.renovation_date_edit.setText(data.get("renovation_date") or "")

        self.longitudinal_slope_edit.setText(data.get("longitudinal_slope") or "")

        self._set_optional_value(
            self.design_flow_edit,
            data.get("design_flow"),
        )

        self.channel_grade_edit.setText(data.get("channel_grade") or "")

        self.cross_section_form_edit.setText(data.get("cross_section_form") or "")

        self._set_optional_value(
            self.embankment_top_width_edit,
            data.get("embankment_top_width"),
        )

        self.inner_slope_edit.setText(data.get("inner_slope") or "")

        self.outer_slope_edit.setText(data.get("outer_slope") or "")

        self._set_optional_value(
            self.increased_flow_edit,
            data.get("increased_flow"),
        )

        self.bed_soil_edit.setText(data.get("bed_soil") or "")

        self.lining_structure_edit.setText(data.get("lining_structure") or "")

        self._set_optional_value(
            self.freeboard_edit,
            data.get("freeboard"),
        )

        self._set_optional_value(
            self.bottom_width_edit,
            data.get("bottom_width"),
        )

        self._set_optional_value(
            self.water_conveyance_loss_edit,
            data.get("water_conveyance_loss"),
        )

        self.lining_material_edit.setText(data.get("lining_material") or "")

        self._set_optional_value(
            self.lining_thickness_edit,
            data.get("lining_thickness"),
        )

        self.concrete_strength_edit.setText(data.get("concrete_strength") or "")

        self._set_optional_value(
            self.channel_depth_edit,
            data.get("channel_depth"),
        )

        self._set_optional_value(
            self.channel_bottom_elevation_edit,
            data.get("channel_bottom_elevation"),
        )

        # =========================
        # 分项评价
        # =========================

        inspection_results = get_inspection_results(survey_record_id)

        self._load_evaluation_results(inspection_results)

        # =========================
        # 调查结论
        # =========================

        grade = record["overall_grade"]

        grade_index = self.overall_grade_combo.findData(grade)

        if grade_index >= 0:
            self.overall_grade_combo.setCurrentIndex(grade_index)
        else:
            self.overall_grade_combo.setCurrentIndex(0)

        self.survey_date_edit.setText(record["survey_date"] or "")

        self.survey_comment_edit.setPlainText(record["survey_comment"] or "")

        # =========================
        # 状态
        # =========================

        if record["record_status"] == "completed":
            self.title_label.setText(
                "附表2.1 防渗衬砌渠道渠段" "工程状况调查 - 编辑已完成记录"
            )

            self.save_button.setText("保存修改")

            self.complete_button.setEnabled(False)

        else:
            self.title_label.setText(
                "附表2.1 防渗衬砌渠道渠段" "工程状况调查 - 编辑草稿"
            )

            self.save_button.setText("保存草稿")

            self.complete_button.setEnabled(True)

        self.is_dirty = False
