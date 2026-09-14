from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

from database import (
    create_engineering_survey,
    get_canal_units_for_organization,
    get_current_context,
    get_current_form_version,
    get_departments,
    get_engineering_business_codes,
    get_point_engineering_record,
    get_water_offices,
    update_point_engineering_survey,
)

from pages.components.survey_input_fields import (
    create_month_edit,
    create_nonnegative_decimal_edit,
    create_nonnegative_integer_edit,
    create_signed_decimal_edit,
    get_optional_float,
    get_optional_int,
    get_optional_month,
    get_optional_text,
)

from services.business_code import (
    build_business_code,
    get_engineering_type_code,
    suggest_next_sequence,
)

from services.stake import parse_stake


class AqueductPage(QWidget):
    """
    附表2.3 渡槽（座槽）工程状况调查页面。

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

        self.form_version = get_current_form_version("form_2_3")

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

        self.title_label = QLabel("附表2.3 渡槽（座槽）工程状况调查")

        self.title_label.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        root_layout.addWidget(self.title_label)

        description = QLabel(
            "当前阶段录入附表2.3正式基本信息。"
            "草稿允许基本信息暂时不完整；"
            "分项评价和调查结论将在后续阶段接入。"
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

        self.name_edit.setPlaceholderText("填写渡槽（座槽）名称")

        self.stake_edit = QLineEdit()

        self.stake_edit.setPlaceholderText("例如：CH12+350")

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

        structure_group = QGroupBox("三、结构参数")

        structure_layout = QFormLayout(structure_group)

        self._setup_form_layout(structure_layout)

        self.structure_form_edit = QLineEdit()

        self.section_width_edit = create_nonnegative_decimal_edit()

        self.section_height_edit = create_nonnegative_decimal_edit()

        self.trough_body_structure_edit = QLineEdit()

        self.trough_wall_thickness_edit = create_nonnegative_decimal_edit()

        self.waterstop_form_edit = QLineEdit()

        # 高程允许负值。
        self.trough_bottom_elevation_edit = create_signed_decimal_edit()

        self.span_count_edit = create_nonnegative_integer_edit()

        self.lower_support_structure_form_edit = QLineEdit()

        self.structure_form_edit.setPlaceholderText("按原始资料填写")

        self.section_width_edit.setPlaceholderText("断面宽")

        self.section_height_edit.setPlaceholderText("断面高")

        self.trough_body_structure_edit.setPlaceholderText("按原始资料填写")

        self.waterstop_form_edit.setPlaceholderText("按原始资料填写")

        self.lower_support_structure_form_edit.setPlaceholderText("按原始资料填写")

        structure_layout.addRow(
            "结构形式：",
            self.structure_form_edit,
        )

        # 正式表为一个“宽*高”字段，
        # 程序内部拆成两个数值字段。
        section_size_widget = QWidget()

        section_size_layout = QHBoxLayout(section_size_widget)

        section_size_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        section_size_layout.setSpacing(8)

        section_size_layout.addWidget(self.section_width_edit)

        section_separator = QLabel("×")

        section_size_layout.addWidget(section_separator)

        section_size_layout.addWidget(self.section_height_edit)

        structure_layout.addRow(
            "断面尺寸（宽×高）：",
            section_size_widget,
        )

        structure_layout.addRow(
            "槽身结构：",
            self.trough_body_structure_edit,
        )

        structure_layout.addRow(
            "槽壁厚度：",
            self.trough_wall_thickness_edit,
        )

        structure_layout.addRow(
            "止水形式：",
            self.waterstop_form_edit,
        )

        structure_layout.addRow(
            "槽底高程：",
            self.trough_bottom_elevation_edit,
        )

        structure_layout.addRow(
            "跨数：",
            self.span_count_edit,
        )

        structure_layout.addRow(
            "下部支撑结构型式：",
            self.lower_support_structure_form_edit,
        )

        form_layout.addWidget(structure_group)

        form_layout.addStretch()

        self.scroll_area.setWidget(form_container)

        root_layout.addWidget(
            self.scroll_area,
            1,
        )

        # =====================================================
        # 底部
        # =====================================================

        self.back_button = QPushButton("返回")

        self.back_button.clicked.connect(self.request_back)

        shortcut_hint = QLabel("快捷键：Ctrl+S 保存草稿")

        shortcut_hint.setStyleSheet("color: #607080;")

        self.save_button = QPushButton("保存草稿")

        self.save_button.setMinimumWidth(120)

        self.save_button.setToolTip("保存当前草稿（Ctrl+S）")

        self.save_button.clicked.connect(self.save_draft)

        button_layout = QHBoxLayout()

        button_layout.addWidget(self.back_button)

        button_layout.addStretch()

        button_layout.addWidget(shortcut_hint)

        button_layout.addSpacing(12)

        button_layout.addWidget(self.save_button)

        root_layout.addLayout(button_layout)

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
            self.stake_edit,
            self.design_flow_edit,
            self.structure_grade_edit,
            self.build_date_edit,
            self.renovation_date_edit,
            self.length_edit,
            self.increased_flow_edit,
            self.structure_form_edit,
            self.section_width_edit,
            self.section_height_edit,
            self.trough_body_structure_edit,
            self.trough_wall_thickness_edit,
            self.waterstop_form_edit,
            self.trough_bottom_elevation_edit,
            self.span_count_edit,
            self.lower_support_structure_form_edit,
            self.save_button,
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
        设置附表2.3草稿保存快捷键。
        """

        self.save_shortcut = QShortcut(
            QKeySequence("Ctrl+S"),
            self,
        )

        self.save_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self.save_shortcut.activated.connect(self.save_draft)

    def _connect_dirty_tracking(self):
        """
        监听用户实际修改。

        程序进行 setText() 回填时，
        不应错误标记为用户修改。
        """

        line_edits = [
            self.name_edit,
            self.stake_edit,
            self.design_flow_edit,
            self.structure_grade_edit,
            self.build_date_edit,
            self.renovation_date_edit,
            self.length_edit,
            self.increased_flow_edit,
            self.structure_form_edit,
            self.section_width_edit,
            self.section_height_edit,
            self.trough_body_structure_edit,
            self.trough_wall_thickness_edit,
            self.waterstop_form_edit,
            self.trough_bottom_elevation_edit,
            self.span_count_edit,
            self.lower_support_structure_form_edit,
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

            engineering_type_code = get_engineering_type_code("form_2_3")

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
        收集附表2.3正式基本信息。
        """

        asset_name = self.name_edit.text().strip()

        stake_text, stake_value = parse_stake(self.stake_edit.text())

        record_data = {
            "asset_name": (asset_name or None),
            "stake": stake_text,
            "stake_value": stake_value,
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
            "structure_form": (get_optional_text(self.structure_form_edit)),
            "section_width": (get_optional_float(self.section_width_edit)),
            "section_height": (get_optional_float(self.section_height_edit)),
            "trough_body_structure": (
                get_optional_text(self.trough_body_structure_edit)
            ),
            "trough_wall_thickness": (
                get_optional_float(self.trough_wall_thickness_edit)
            ),
            "waterstop_form": (get_optional_text(self.waterstop_form_edit)),
            "trough_bottom_elevation": (
                get_optional_float(self.trough_bottom_elevation_edit)
            ),
            "span_count": (get_optional_int(self.span_count_edit)),
            "lower_support_structure_form": (
                get_optional_text(self.lower_support_structure_form_edit)
            ),
        }

        return {
            "asset_name": asset_name,
            "stake_text": stake_text,
            "stake_value": stake_value,
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
            self.current_context = get_current_context()

            if not self.current_context:
                raise ValueError("当前没有可用项目。")

            if self.current_context["batch_id"] is None:
                raise ValueError("当前没有启用的调查批次。")

            self.form_version = get_current_form_version("form_2_3")

            if self.form_version is None:
                raise ValueError("未找到附表2.3当前版本。")

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

            stake_text = basic_data["stake_text"]

            stake_value = basic_data["stake_value"]

            record_data = basic_data["record_data"]

            # =============================================
            # 第一次保存：创建
            # =============================================

            if self.editing_record_id is None:
                result = create_engineering_survey(
                    project_id=(self.current_context["project_id"]),
                    survey_batch_id=(self.current_context["batch_id"]),
                    form_version_id=(self.form_version["id"]),
                    asset_name=(asset_name),
                    asset_type=(self.form_version["asset_type"]),
                    organization_unit_id=(office_data["id"]),
                    canal_unit_id=(canal_data["id"]),
                    business_code=(business_code),
                    record_data=(record_data),
                    single_stake_text=(stake_text),
                    single_stake_value=(stake_value),
                )

                self.editing_record_id = int(result["survey_record_id"])

                self.editing_record_status = "draft"

            # =============================================
            # 后续保存：修改原记录
            # =============================================

            else:
                update_point_engineering_survey(
                    survey_record_id=(self.editing_record_id),
                    form_code="form_2_3",
                    asset_name=(asset_name),
                    record_data=(record_data),
                    single_stake_text=(stake_text),
                    single_stake_value=(stake_value),
                )

            # =============================================
            # 工程建立后锁定归属
            # =============================================

            self.department_combo.setEnabled(False)

            self.office_combo.setEnabled(False)

            self.canal_combo.setEnabled(False)

            self.title_label.setText("附表2.3 渡槽（座槽）" "工程状况调查 - 编辑草稿")

            self.save_button.setEnabled(True)

            self.save_button.setText("保存草稿")

            self.is_dirty = False

            self.survey_saved.emit()

            if show_message:
                QMessageBox.information(
                    self,
                    "保存成功",
                    ("当前调查草稿已保存。\n\n" f"业务编号：" f"{business_code}"),
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
        保存当前附表2.3草稿。
        """

        self._save_current_draft(show_message=True)

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
        打开已有附表2.3草稿。

        B1阶段暂时只开放 draft。
        completed 将在后续完整接入
        评价和调查结论后再开放编辑。
        """

        record = get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        if record is None:
            raise ValueError("没有找到该附表2.3调查记录。")

        if record["record_status"] != "draft":
            raise ValueError("当前阶段仅支持打开" "附表2.3草稿记录。")

        self.current_context = get_current_context()

        self.form_version = get_current_form_version("form_2_3")

        self.editing_record_id = int(record["survey_record_id"])

        self.editing_record_status = record["record_status"]

        self.title_label.setText("附表2.3 渡槽（座槽）" "工程状况调查 - 编辑草稿")

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

        # 根据基层处重新加载水管所。
        self.department_changed()

        office_found = self._set_combo_by_id(
            self.office_combo,
            record["office_id"],
        )

        if not office_found:
            raise ValueError("该调查记录所属水管所" "已不存在或不可用。")

        # 根据水管所重新加载渠系。
        self.office_changed()

        canal_found = self._set_combo_by_id(
            self.canal_combo,
            record["canal_id"],
        )

        if not canal_found:
            raise ValueError("该调查记录所属渠系" "已不存在或不可用。")

        # 重新加载过程中会自动计算一个
        # “下一业务编号”，这里必须用
        # 数据库中原记录自己的业务编号覆盖回来。
        self.business_code_edit.setText(record["business_code"] or "")

        # EngineeringAsset 建立后，
        # 工程归属属于工程身份的一部分，
        # 调查页面不允许直接修改。
        self.department_combo.setEnabled(False)

        self.office_combo.setEnabled(False)

        self.canal_combo.setEnabled(False)

        # =====================================================
        # 2. 回填正式基本信息
        # =====================================================

        data = record["record_data"] or {}

        self.name_edit.setText(record["asset_name"] or "")

        # 点状工程的位置身份以
        # EngineeringAsset.single_stake_text
        # 为准。
        self.stake_edit.setText(record["single_stake_text"] or "")

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

        self.structure_form_edit.setText(data.get("structure_form") or "")

        set_optional(
            self.section_width_edit,
            data.get("section_width"),
        )

        set_optional(
            self.section_height_edit,
            data.get("section_height"),
        )

        self.trough_body_structure_edit.setText(data.get("trough_body_structure") or "")

        set_optional(
            self.trough_wall_thickness_edit,
            data.get("trough_wall_thickness"),
        )

        self.waterstop_form_edit.setText(data.get("waterstop_form") or "")

        set_optional(
            self.trough_bottom_elevation_edit,
            data.get("trough_bottom_elevation"),
        )

        set_optional(
            self.span_count_edit,
            data.get("span_count"),
        )

        (
            self.lower_support_structure_form_edit.setText(
                data.get("lower_support_structure_form") or ""
            )
        )

        self.save_button.setEnabled(True)

        self.save_button.setText("保存草稿")

        # 数据库回填属于程序行为，
        # 不属于用户未保存修改。
        self.is_dirty = False

    # =========================================================
    # 新增状态
    # =========================================================

    def prepare_new(self):
        """
        初始化一条新的附表2.3调查。

        B1阶段暂不做“连续录入保留归属”。
        该行为统一留到 B3 接入。
        """

        self.current_context = get_current_context()

        self.form_version = get_current_form_version("form_2_3")

        self.editing_record_id = None
        self.editing_record_status = None

        self.title_label.setText("附表2.3 渡槽（座槽）" "工程状况调查 - 新增")

        # =====================================================
        # 1. 恢复新增模式
        # =====================================================

        self.department_combo.setEnabled(True)

        self.office_combo.setEnabled(True)

        self.canal_combo.setEnabled(True)

        self.save_button.setEnabled(True)

        self.save_button.setText("保存草稿")

        # =====================================================
        # 2. 清空工程基本信息
        # =====================================================

        self.name_edit.clear()
        self.stake_edit.clear()
        self.design_flow_edit.clear()
        self.structure_grade_edit.clear()

        self.build_date_edit.clear()
        self.renovation_date_edit.clear()

        self.length_edit.clear()
        self.increased_flow_edit.clear()

        self.structure_form_edit.clear()

        self.section_width_edit.clear()
        self.section_height_edit.clear()

        self.trough_body_structure_edit.clear()

        self.trough_wall_thickness_edit.clear()

        self.waterstop_form_edit.clear()

        self.trough_bottom_elevation_edit.clear()

        self.span_count_edit.clear()

        (self.lower_support_structure_form_edit.clear())

        # =====================================================
        # 3. 重新加载当前有效归属
        # =====================================================

        self.load_departments()

        # load_departments -> department_changed
        # -> office_changed 已经会自动触发
        # 业务编号生成。
        #
        # 这里再执行一次没有副作用，
        # 同时保证初始化结束后编号与当前选择一致。
        self.update_business_code()

        # =====================================================
        # 4. 初始化不属于用户修改
        # =====================================================

        self.is_dirty = False
