from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database import (
    create_engineering_survey,
    get_canal_units_for_organization,
    get_current_context,
    get_current_form_version,
    get_departments,
    get_engineering_business_codes,
    get_water_offices,
)

from services.business_code import (
    build_business_code,
    get_engineering_type_code,
    suggest_next_sequence,
)

from services.stake import parse_stake


class SluiceGatePage(QWidget):
    survey_saved = Signal()
    back_requested = Signal()

    def __init__(self):
        super().__init__()

        self.current_context = get_current_context()
        self.form_version = get_current_form_version("form_2_2")

        self.init_ui()
        self.load_departments()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(18)

        title = QLabel("附表2.2 水闸工程状况调查")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        root_layout.addWidget(title)

        description = QLabel(
            "当前为V0.1最小录入版本。"
            "先验证工程对象、调查记录和业务编号完整保存流程。"
        )
        description.setStyleSheet("color: #607080; font-size: 14px;")

        root_layout.addWidget(description)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(14)

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

        # 工程名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：测试节制闸")

        # 桩号
        self.stake_edit = QLineEdit()
        self.stake_edit.setPlaceholderText("例如：K12+350")

        # 设计流量
        self.design_flow_edit = QLineEdit()
        self.design_flow_edit.setPlaceholderText("例如：4.5，可留空")

        validator = QDoubleValidator(
            0.0,
            999999999.0,
            6,
            self,
        )
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.design_flow_edit.setValidator(validator)

        form_layout.addRow(
            "所属基层处：",
            self.department_combo,
        )

        form_layout.addRow(
            "所属水管所：",
            self.office_combo,
        )

        form_layout.addRow(
            "所属渠系：",
            self.canal_combo,
        )

        form_layout.addRow(
            "业务编号：",
            self.business_code_edit,
        )

        form_layout.addRow(
            "工程名称：",
            self.name_edit,
        )

        form_layout.addRow(
            "桩号：",
            self.stake_edit,
        )

        form_layout.addRow(
            "设计流量（m³/s）：",
            self.design_flow_edit,
        )

        root_layout.addLayout(form_layout)

        button_layout = QHBoxLayout()

        back_button = QPushButton("返回列表")
        back_button.clicked.connect(
            self.back_requested.emit
        )

        button_layout.addWidget(
            back_button
        )

        button_layout.addStretch()

        save_button = QPushButton("保存草稿")
        save_button.setMinimumWidth(120)
        save_button.clicked.connect(self.save_draft)

        button_layout.addWidget(save_button)

        root_layout.addLayout(button_layout)

        root_layout.addStretch()

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

            design_flow_text = self.design_flow_edit.text().strip()

            design_flow = None

            if design_flow_text:
                design_flow = float(design_flow_text)

            record_data = {
                "asset_name": asset_name,
                "stake": stake_text,
                "stake_value": stake_value,
                "design_flow": design_flow,
            }

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
            )

            QMessageBox.information(
                self,
                "保存成功",
                (
                    "水闸调查草稿已保存。\n\n"
                    f"业务编号："
                    f"{result['business_code']}\n"
                    f"工程对象ID："
                    f"{result['engineering_asset_id']}\n"
                    f"调查记录ID："
                    f"{result['survey_record_id']}"
                ),
            )

            self.clear_form()
            self.survey_saved.emit()

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )

    def clear_form(self):
        self.name_edit.clear()
        self.stake_edit.clear()
        self.design_flow_edit.clear()

        # 保存完成后重新计算编号，
        # 下一条记录会自动建议新的顺序号。
        self.update_business_code()
