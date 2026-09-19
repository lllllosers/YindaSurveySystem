from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
)

from forms.engineering.models import (
    FieldDefinition,
)
from forms.engineering.value_normalizers import (
    normalize_concrete_strength,
    normalize_structure_grade,
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

from services.stake import (
    parse_stake,
)


@dataclass
class EngineeringFieldRuntime:
    """
    一个 FieldDefinition 在 Qt 页面中的
    运行时对象。

    definition:
        描述字段是什么。

    widget:
        实际输入控件。

    本类负责：
    - 读取；
    - 回填；
    - 清空；
    - 空值判断；
    - dirty tracking 接线。

    不负责：
    - 页面布局；
    - 必填业务规则；
    - SurveyRecord 保存；
    - point / range 工程身份处理。
    """

    definition: FieldDefinition
    widget: QLineEdit | QComboBox

    # =========================================================
    # 读取
    # =========================================================

    def get_value(self):
        """
        获取适合写入 record_data 的字段值。

        stake 类型只返回标准化桩号文本；
        桩号对应米数由 get_stake_parts()
        单独提供给工程位置逻辑。
        """

        input_type = self.definition.input_type

        if input_type == "text":
            return get_optional_text(self.widget)

        if input_type == "structure_grade":
            return normalize_structure_grade(
                self.widget.text(),
                self.definition.label,
            )

        if input_type == "concrete_strength":
            return normalize_concrete_strength(
                self.widget.text(),
                self.definition.label,
            )

        if input_type in (
            "decimal",
            "signed_decimal",
        ):
            return get_optional_float(self.widget)

        if input_type == "integer":
            return get_optional_int(self.widget)

        if input_type == "month":
            return get_optional_month(
                self.widget,
                self.definition.label,
            )

        if input_type == "stake":
            stake_text, _ = parse_stake(self.widget.text())

            return stake_text

        if input_type == "choice":
            return self.widget.currentData()

        raise ValueError("暂不支持的工程调查字段类型：" f"{input_type}")

    def get_stake_parts(
        self,
    ) -> tuple[
        str | None,
        float | None,
    ]:
        """
        获取桩号的标准文本和米数。

        仅 stake 字段允许调用。
        """

        if self.definition.input_type != "stake":
            raise ValueError("只有 stake 类型字段" "可以获取桩号解析结果。")

        return parse_stake(self.widget.text())

    # =========================================================
    # 回填
    # =========================================================

    def set_value(
        self,
        value,
    ):
        """
        数据库值回填到控件。

        setText() 不会触发 textEdited，
        因此不会被 dirty tracking
        错误判断为用户修改。
        """

        if self.definition.input_type == "structure_grade":
            normalized = normalize_structure_grade(
                value,
                self.definition.label,
            )

            self.widget.setText(normalized or "")
            return

        if self.definition.input_type == "concrete_strength":
            normalized = normalize_concrete_strength(
                value,
                self.definition.label,
            )

            self.widget.setText(normalized or "")
            return

        if self.definition.input_type == "choice":
            if value is None:
                self.widget.setCurrentIndex(0)
                return

            index = self.widget.findData(
                str(value)
            )

            if index < 0:
                raise ValueError(
                    f"{self.definition.label}"
                    "存在未定义的选项值："
                    f"{value}"
                )

            self.widget.setCurrentIndex(
                index
            )
            return

        if value is None:
            self.widget.clear()
            return

        self.widget.setText(str(value))

    # =========================================================
    # 清空
    # =========================================================

    def clear(self):
        if self.definition.input_type == "choice":
            self.widget.setCurrentIndex(0)
            return

        self.widget.clear()

    # =========================================================
    # 状态
    # =========================================================

    def is_blank(self) -> bool:
        if self.definition.input_type == "choice":
            return self.widget.currentData() is None

        return not (self.widget.text().strip())

    # =========================================================
    # dirty tracking
    # =========================================================

    def connect_dirty(
        self,
        callback: Callable,
    ):
        """
        只监听用户实际编辑。

        使用 textEdited 而不是 textChanged，
        避免程序回填数据时误标 dirty。
        """

        if self.definition.input_type == "choice":
            # activated 只由用户选择触发，
            # 程序 setCurrentIndex() 不会误标 dirty。
            self.widget.activated.connect(callback)
            return

        self.widget.textEdited.connect(callback)


def _normalize_domain_edit(
    widget,
    normalizer,
    field_name,
):
    try:
        normalized = normalizer(
            widget.text(),
            field_name,
        )
    except ValueError:
        return

    widget.setText(
        normalized or ""
    )


def _placeholder(
    definition: FieldDefinition,
    default: str | None,
):
    """
    definition.placeholder 为 None：
        使用该字段类型默认提示。

    definition.placeholder 为 "":
        明确不显示 placeholder。
    """

    if definition.placeholder is not None:
        return definition.placeholder

    return default


def create_engineering_field_runtime(
    definition: FieldDefinition,
) -> EngineeringFieldRuntime:
    """
    根据 FieldDefinition 创建
    对应 Qt 输入控件及运行时包装。

    根据 FieldDefinition 创建已支持的
    工程调查输入控件。新增字段类型时，
    模型合同、运行时和测试必须同步扩展。
    """

    input_type = definition.input_type

    if input_type == "text":
        widget = QLineEdit()

        placeholder = _placeholder(
            definition,
            None,
        )

        if placeholder:
            widget.setPlaceholderText(placeholder)

    elif input_type == "structure_grade":
        widget = QLineEdit()

        placeholder = _placeholder(
            definition,
            "只需输入数字，例如：3；离开输入框后自动显示为3级",
        )

        if placeholder:
            widget.setPlaceholderText(placeholder)

        widget.editingFinished.connect(
            lambda target=widget,
            field_name=definition.label:
            _normalize_domain_edit(
                target,
                normalize_structure_grade,
                field_name,
            )
        )

    elif input_type == "concrete_strength":
        widget = QLineEdit()

        placeholder = _placeholder(
            definition,
            "输入30、c30或C30均可；自动统一为C30",
        )

        if placeholder:
            widget.setPlaceholderText(placeholder)

        widget.editingFinished.connect(
            lambda target=widget,
            field_name=definition.label:
            _normalize_domain_edit(
                target,
                normalize_concrete_strength,
                field_name,
            )
        )

    elif input_type == "stake":
        widget = QLineEdit()

        placeholder = _placeholder(
            definition,
            "例如：CH12+350",
        )

        if placeholder:
            widget.setPlaceholderText(placeholder)

    elif input_type == "decimal":
        widget = create_nonnegative_decimal_edit(
            _placeholder(
                definition,
                "可留空",
            )
        )

    elif input_type == "signed_decimal":
        widget = create_signed_decimal_edit(
            _placeholder(
                definition,
                "可留空",
            )
        )

    elif input_type == "integer":
        maximum = definition.maximum if definition.maximum is not None else 999999999

        widget = create_nonnegative_integer_edit(
            placeholder=_placeholder(
                definition,
                "可留空",
            ),
            maximum=maximum,
        )

    elif input_type == "month":
        widget = create_month_edit(
            _placeholder(
                definition,
                ("直接输入6位数字，" "例如：201006"),
            )
        )

    elif input_type == "choice":
        widget = QComboBox()

        blank_text = _placeholder(
            definition,
            "请选择",
        )

        widget.addItem(
            blank_text or "",
            None,
        )

        for choice in (
            definition.choices
            or ()
        ):
            widget.addItem(
                choice,
                choice,
            )

    else:
        raise ValueError("暂不支持的工程调查字段类型：" f"{input_type}")

    widget.setProperty("uiWidthRole", "form")

    return EngineeringFieldRuntime(
        definition=definition,
        widget=widget,
    )
