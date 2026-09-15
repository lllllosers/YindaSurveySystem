from datetime import date
from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from forms.engineering.models import (
    EngineeringFormDefinition,
    FieldRowDefinition,
)

from pages.components.engineering_field_runtime import (
    EngineeringFieldRuntime,
    create_engineering_field_runtime,
)

from pages.components.evaluation_section import (
    EvaluationSection,
)

from pages.components.survey_input_fields import (
    create_date_edit,
    get_optional_date,
)


class GenericEngineeringSurveyPage(QWidget):
    """
    附表2工程调查通用录入页面。

    R1-5阶段仅负责根据
    EngineeringFormDefinition
    生成页面结构。

    当前明确不负责：
    - 数据库读取；
    - 草稿保存；
    - completed流程；
    - 业务编号生成；
    - dirty tracking；
    - 连续录入；
    - 返回拦截；
    - Excel导出。

    后续阶段在当前结构上逐步接入，
    不另起第二套通用页面。
    """

    survey_saved = Signal()
    back_requested = Signal()

    def __init__(
        self,
        definition: EngineeringFormDefinition,
        parent=None,
    ):
        super().__init__(parent)

        self.definition = definition

        # key -> EngineeringFieldRuntime
        self.field_runtimes: dict[
            str,
            EngineeringFieldRuntime,
        ] = {}

        # 用于测试和后续布局控制。
        self.section_groups: list[QGroupBox] = []

        self.overall_grade_group: QButtonGroup

        self.overall_grade_buttons: dict[
            str,
            QRadioButton,
        ] = {}

        self.evaluation_section: EvaluationSection

        self._init_ui()

        self.prepare_new()

    # =========================================================
    # 主界面
    # =========================================================

    def _init_ui(
        self,
    ):
        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.setSpacing(18)

        # =====================================================
        # 标题
        # =====================================================

        self.title_label = QLabel(self.definition.display_name)

        self.title_label.setStyleSheet("font-size: 20px; " "font-weight: bold;")

        root_layout.addWidget(self.title_label)

        self.description_label = QLabel(
            (
                f"填写附表"
                f"{self.definition.form_number}"
                "基本信息、分项评价及调查结论。"
                "草稿允许暂时不完整；"
                "完成调查前系统将检查"
                "全部必填内容。"
            )
        )

        self.description_label.setWordWrap(True)

        self.description_label.setStyleSheet("color: #607080; " "font-size: 15px;")

        root_layout.addWidget(self.description_label)

        # =====================================================
        # 滚动区域
        # =====================================================

        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(True)

        self.form_container = QWidget()

        self.form_layout = QVBoxLayout(self.form_container)

        self.form_layout.setContentsMargins(
            4,
            4,
            12,
            4,
        )

        self.form_layout.setSpacing(16)

        # =====================================================
        # 一、归属与编号
        # =====================================================

        self._build_ownership_section()

        # =====================================================
        # 配置驱动基本信息
        # =====================================================

        self._build_definition_sections()

        # =====================================================
        # 分项评价
        # =====================================================

        self._build_evaluation_section()

        # =====================================================
        # 调查结论
        # =====================================================

        self._build_conclusion_section()

        self.form_layout.addStretch()

        self.scroll_area.setWidget(self.form_container)

        root_layout.addWidget(
            self.scroll_area,
            1,
        )

        # =====================================================
        # R1-5底部仅做预览状态
        # =====================================================

        self._build_preview_footer(root_layout)

    # =========================================================
    # 公共布局
    # =========================================================

    @staticmethod
    def _setup_form_layout(
        layout: QFormLayout,
    ):
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        layout.setHorizontalSpacing(20)

        layout.setVerticalSpacing(12)

    # =========================================================
    # 一、归属与编号
    # =========================================================

    def _build_ownership_section(
        self,
    ):
        group = QGroupBox("一、归属与编号")

        layout = QFormLayout(group)

        self._setup_form_layout(layout)

        self.department_combo = QComboBox()

        self.office_combo = QComboBox()

        self.canal_combo = QComboBox()

        self.business_code_edit = QLineEdit()

        self.business_code_edit.setReadOnly(True)

        self.business_code_edit.setPlaceholderText(
            ("选择基层处、水管所和渠系后" "自动生成")
        )

        layout.addRow(
            "所属基层处：",
            self.department_combo,
        )

        layout.addRow(
            "所属水管所：",
            self.office_combo,
        )

        layout.addRow(
            "所属渠系：",
            self.canal_combo,
        )

        layout.addRow(
            "业务编号：",
            self.business_code_edit,
        )

        self.form_layout.addWidget(group)

        self.ownership_group = group

    # =========================================================
    # Definition sections
    # =========================================================

    def _build_definition_sections(
        self,
    ):
        # 先为全部字段建立 runtime。
        for field in self.definition.fields:
            runtime = create_engineering_field_runtime(field)

            self.field_runtimes[field.key] = runtime

        # 再根据 section / row 定义布局。
        for section in self.definition.sections:
            group = QGroupBox(section.title)

            layout = QFormLayout(group)

            self._setup_form_layout(layout)

            for row in section.rows:
                self._add_definition_row(
                    layout,
                    row,
                )

            self.form_layout.addWidget(group)

            self.section_groups.append(group)

    def _add_definition_row(
        self,
        layout: QFormLayout,
        row: FieldRowDefinition,
    ):
        """
        单字段：
            名称：[________]

        多字段：
            断面尺寸：[宽] × [高]
        """

        if len(row.field_keys) == 1:
            field_key = row.field_keys[0]

            runtime = self.field_runtimes[field_key]

            definition = runtime.definition

            label_text = row.label or definition.display_label

            layout.addRow(
                f"{label_text}：",
                runtime.widget,
            )

            return

        # =====================================================
        # 组合字段行
        # =====================================================

        row_widget = QWidget()

        row_layout = QHBoxLayout(row_widget)

        row_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        row_layout.setSpacing(8)

        separator = row.separator if row.separator is not None else ""

        for index, field_key in enumerate(row.field_keys):
            if index > 0 and separator:
                row_layout.addWidget(QLabel(separator))

            runtime = self.field_runtimes[field_key]

            row_layout.addWidget(runtime.widget)

        label_text = row.label or " / ".join(
            self.field_runtimes[field_key].definition.label
            for field_key in row.field_keys
        )

        layout.addRow(
            f"{label_text}：",
            row_widget,
        )

    # =========================================================
    # 分项评价
    # =========================================================

    def _build_evaluation_section(
        self,
    ):
        self.evaluation_section = EvaluationSection(
            title=(self.definition.evaluation_title),
            evaluation_items=(self.definition.evaluation_items),
            grade_options=(self.definition.grade_options),
        )

        self.form_layout.addWidget(self.evaluation_section)

    # =========================================================
    # 调查结论
    # =========================================================

    def _build_conclusion_section(
        self,
    ):
        group = QGroupBox(self.definition.conclusion_title)

        layout = QFormLayout(group)

        self._setup_form_layout(layout)

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

        for grade in self.definition.grade_options:
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
        # 调查意见
        # -------------------------

        self.survey_comment_edit = QPlainTextEdit()

        self.survey_comment_edit.setPlaceholderText("填写调查意见与建议")

        self.survey_comment_edit.setMinimumHeight(100)

        self.survey_comment_edit.setTabChangesFocus(True)

        layout.addRow(
            "工程状况类别：",
            self.overall_grade_widget,
        )

        layout.addRow(
            "调查时间：",
            self.survey_date_edit,
        )

        layout.addRow(
            "调查意见与建议：",
            self.survey_comment_edit,
        )

        self.form_layout.addWidget(group)

        self.conclusion_group = group

    # =========================================================
    # R1-5预览底部
    # =========================================================

    def _build_preview_footer(
        self,
        root_layout,
    ):
        footer_layout = QHBoxLayout()

        self.preview_status_label = QLabel(
            ("当前为通用表单框架结构预览，" "尚未接入保存与完成调查流程。")
        )

        self.preview_status_label.setStyleSheet("color: #607080;")

        self.back_button = QPushButton("关闭预览")

        self.back_button.clicked.connect(self.back_requested.emit)

        footer_layout.addWidget(self.back_button)

        footer_layout.addStretch()

        footer_layout.addWidget(self.preview_status_label)

        root_layout.addLayout(footer_layout)

    # =========================================================
    # 提供给后续Runtime使用的基础接口
    # =========================================================

    def get_field_runtime(
        self,
        field_key: str,
    ) -> EngineeringFieldRuntime:
        try:
            return self.field_runtimes[field_key]
        except KeyError as error:
            raise KeyError("当前表单不存在字段：" f"{field_key}") from error

    def get_field_widget(
        self,
        field_key: str,
    ):
        return self.get_field_runtime(field_key).widget

    # =========================================================
    # 动态字段：收集
    # =========================================================

    def collect_record_data(
        self,
    ) -> dict:
        """
        收集 definition 中的全部正式字段。

        stake 字段除了标准化文本，
        还会根据 PositionDefinition
        写入对应的桩号数值字段。

        例如附表2.6：

        {
            "stake": "CH12+350",
            "stake_value": 12350.0,
            ...
        }
        """

        record_data = {}

        for field in self.definition.fields:
            runtime = self.field_runtimes[field.key]

            record_data[field.key] = runtime.get_value()

        position = self.definition.position

        # =====================================================
        # point
        # =====================================================

        if position.kind == "point":
            stake_field = position.single_stake_field

            value_key = position.single_stake_value_key

            runtime = self.field_runtimes[stake_field]

            (
                stake_text,
                stake_value,
            ) = runtime.get_stake_parts()

            # 确保用户输入的兼容格式
            # 最终统一写回正式CH格式。
            record_data[stake_field] = stake_text

            record_data[value_key] = stake_value

        # =====================================================
        # range
        # =====================================================

        elif position.kind == "range":
            start_field = position.start_stake_field

            end_field = position.end_stake_field

            start_value_key = position.start_stake_value_key

            end_value_key = position.end_stake_value_key

            (
                start_text,
                start_value,
            ) = self.field_runtimes[start_field].get_stake_parts()

            (
                end_text,
                end_value,
            ) = self.field_runtimes[end_field].get_stake_parts()

            record_data[start_field] = start_text

            record_data[start_value_key] = start_value

            record_data[end_field] = end_text

            record_data[end_value_key] = end_value

        else:
            raise ValueError("暂不支持的工程位置类型：" f"{position.kind}")

        return record_data

    # =========================================================
    # 工程位置
    # =========================================================

    def collect_position_data(
        self,
    ) -> dict:
        """
        返回 EngineeringAsset 层需要的
        标准化位置数据。

        该接口不关心具体附表，
        只关心 point / range。
        """

        position = self.definition.position

        if position.kind == "point":
            runtime = self.field_runtimes[position.single_stake_field]

            (
                stake_text,
                stake_value,
            ) = runtime.get_stake_parts()

            return {
                "kind": "point",
                "single_stake_text": (stake_text),
                "single_stake_value": (stake_value),
            }

        if position.kind == "range":
            start_runtime = self.field_runtimes[position.start_stake_field]

            end_runtime = self.field_runtimes[position.end_stake_field]

            (
                start_text,
                start_value,
            ) = start_runtime.get_stake_parts()

            (
                end_text,
                end_value,
            ) = end_runtime.get_stake_parts()

            return {
                "kind": "range",
                "start_stake_text": (start_text),
                "start_stake_value": (start_value),
                "end_stake_text": (end_text),
                "end_stake_value": (end_value),
            }

        raise ValueError("暂不支持的工程位置类型：" f"{position.kind}")

    # =========================================================
    # 动态字段：回填
    # =========================================================

    def load_record_data(
        self,
        record_data,
    ):
        """
        将 record_data 回填到
        definition 定义的字段。

        数据库中额外存在的旧字段
        或派生字段自动忽略。

        例如：
        stake_value
        start_stake_value
        end_stake_value
        不对应可编辑控件，
        因此不会直接回填。
        """

        record_data = record_data or {}

        for field in self.definition.fields:
            runtime = self.field_runtimes[field.key]

            runtime.set_value(record_data.get(field.key))

    # =========================================================
    # 工程状况类别
    # =========================================================

    def get_overall_grade(
        self,
    ):
        for grade, button in self.overall_grade_buttons.items():
            if button.isChecked():
                return grade

        return None

    def clear_overall_grade(
        self,
    ):
        self.overall_grade_group.setExclusive(False)

        for button in self.overall_grade_buttons.values():
            button.setChecked(False)

        self.overall_grade_group.setExclusive(True)

    def set_overall_grade(
        self,
        grade,
    ):
        self.clear_overall_grade()

        if grade is None:
            return

        button = self.overall_grade_buttons.get(grade)

        if button is not None:
            button.setChecked(True)

    # =========================================================
    # 调查结论
    # =========================================================

    def collect_conclusion_data(
        self,
    ) -> dict:

        return {
            "survey_date": (
                get_optional_date(
                    self.survey_date_edit,
                    "调查时间",
                )
            ),
            "overall_grade": (self.get_overall_grade()),
            "survey_comment": (self.survey_comment_edit.toPlainText().strip() or None),
        }

    def load_conclusion_data(
        self,
        *,
        survey_date=None,
        overall_grade=None,
        survey_comment=None,
    ):
        self.survey_date_edit.setText(survey_date or "")

        self.set_overall_grade(overall_grade)

        self.survey_comment_edit.setPlainText(survey_comment or "")

    # =========================================================
    # 分项评价
    # =========================================================

    def collect_evaluation_results(
        self,
    ):
        return (
            self.evaluation_section
            .collect_results()
        )

    def load_evaluation_results(
        self,
        results,
    ):
        self.evaluation_section.load_results(
            results or []
        )

    # =========================================================
    # 完整页面数据
    # =========================================================

    def collect_form_data(
        self,
    ) -> dict:
        """
        收集当前页面中与业务记录有关的全部数据。

        暂不包含：
        - 基层处
        - 水管所
        - 渠系
        - 业务编号

        这些属于公共工程归属上下文，
        后续持久化阶段统一接入。
        """

        record_data = (
            self.collect_record_data()
        )

        conclusion = (
            self.collect_conclusion_data()
        )

        asset_name = (
            record_data.get(
                self.definition
                .asset_name_field
            )
        )

        return {
            "asset_name": asset_name,
            "record_data": record_data,
            "position": (
                self.collect_position_data()
            ),
            "inspection_results": (
                self.collect_evaluation_results()
            ),
            **conclusion,
        }

    # =========================================================
    # 新建 / 清空
    # =========================================================

    def clear_form_data(
        self,
    ):
        """
        清空当前调查内容。

        不清空：
        - 基层处
        - 水管所
        - 渠系

        这样后续连续录入时
        可以保留当前工程归属。
        """

        for runtime in (
            self.field_runtimes
            .values()
        ):
            runtime.clear()

        self.evaluation_section.clear()

        self.clear_overall_grade()

        self.survey_date_edit.clear()

        self.survey_comment_edit.clear()

        self.business_code_edit.clear()

    def prepare_new(
        self,
        *,
        survey_date=None,
    ):
        """
        准备录入一条新的工程调查。

        默认调查日期为系统当天。

        连续录入时也可以显式传入
        上一条记录的调查日期。
        """

        self.clear_form_data()

        if survey_date is None:
            survey_date = (
                date.today()
                .isoformat()
            )

        self.survey_date_edit.setText(
            survey_date
        )

    # =========================================================
    # 完整记录回填
    # =========================================================

    def load_form_data(
        self,
        *,
        record_data,
        inspection_results=None,
        survey_date=None,
        overall_grade=None,
        survey_comment=None,
    ):
        self.load_record_data(
            record_data
        )

        self.load_evaluation_results(
            inspection_results
        )

        self.load_conclusion_data(
            survey_date=survey_date,
            overall_grade=overall_grade,
            survey_comment=survey_comment,
        )