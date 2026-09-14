from PySide6.QtCore import (
    QRegularExpression,
)
from PySide6.QtGui import (
    QDoubleValidator,
    QIntValidator,
)
from PySide6.QtWidgets import QLineEdit


def create_nonnegative_decimal_edit(
    placeholder="可留空",
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


def create_signed_decimal_edit(
    placeholder="可留空",
):
    """
    创建允许为空的有符号小数输入框。

    适用于高程等允许出现负值的字段。
    """

    edit = QLineEdit()

    if placeholder:
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


def create_nonnegative_integer_edit(
    placeholder="可留空",
):
    """
    创建允许为空的非负整数输入框。
    """

    edit = QLineEdit()

    if placeholder:
        edit.setPlaceholderText(placeholder)

    edit.setValidator(
        QIntValidator(
            0,
            999999999,
            edit,
        )
    )

    return edit


def _format_month_input(
    edit,
    text,
):
    """
    年月高速录入。

    例如：
    201006 -> 2010-06
    """

    digits = "".join(char for char in text if char.isdigit())[:6]

    if len(digits) <= 4:
        formatted = digits
    else:
        formatted = f"{digits[:4]}-" f"{digits[4:6]}"

    if formatted != text:
        edit.setText(formatted)
        edit.setCursorPosition(len(formatted))


def create_month_edit(
    placeholder="直接输入6位数字，例如：201006",
):
    """
    创建 YYYY-MM 年月输入框。
    """

    edit = QLineEdit()

    edit.setMaxLength(7)

    if placeholder:
        edit.setPlaceholderText(placeholder)

    edit.textEdited.connect(
        lambda text, target=edit: _format_month_input(
            target,
            text,
        )
    )

    return edit


def get_optional_float(
    edit,
):
    text = edit.text().strip()

    if not text:
        return None

    return float(text)


def get_optional_int(
    edit,
):
    text = edit.text().strip()

    if not text:
        return None

    return int(text)


def get_optional_text(
    edit,
):
    return edit.text().strip() or None


def get_optional_month(
    edit,
    field_name,
):
    """
    草稿保存阶段只检查 YYYY-MM 语法。

    是否为真实日历年月，
    在完成调查阶段继续严格校验。
    """

    text = edit.text().strip()

    if not text:
        return None

    expression = QRegularExpression(r"^\d{4}-(0[1-9]|1[0-2])$")

    if not expression.match(text).hasMatch():
        raise ValueError(f"{field_name}格式应为 " "YYYY-MM，例如：2010-06。")

    return text
