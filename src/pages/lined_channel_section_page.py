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
)

from services.business_code import (
    build_business_code,
    get_engineering_type_code,
    suggest_next_sequence,
)

from services.stake import parse_stake


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
            "当前阶段填写附表2.1全部基本信息。"
            "可保存草稿并重新打开继续修改；"
            "A/B/C/D分项评价将在下一阶段接入。"
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
        self.save_button.setMinimumWidth(120)
        self.save_button.clicked.connect(self.save_draft)

        button_layout.addWidget(back_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)

        root_layout.addLayout(button_layout)

    # =========================================================
    # UI helpers
    # =========================================================

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
        ]

        for edit in line_edits:
            edit.textEdited.connect(self._mark_dirty)

        for combo in (
            self.department_combo,
            self.office_combo,
            self.canal_combo,
        ):
            combo.activated.connect(self._mark_dirty)

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
                    )
                )

                message = "渠道渠段调查草稿已更新。\n\n" f"业务编号：{business_code}"

            # 工程建立以后，
            # 当前阶段不允许直接修改归属。
            self.department_combo.setEnabled(False)
            self.office_combo.setEnabled(False)
            self.canal_combo.setEnabled(False)

            self.title_label.setText("附表2.1 防渗衬砌渠道渠段工程状况调查 - 编辑草稿")

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

        if record["record_status"] != "draft":
            raise ValueError("当前阶段仅支持打开草稿记录。")

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

        self.is_dirty = False
