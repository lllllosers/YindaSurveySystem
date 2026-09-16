from datetime import date
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
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from database import (
    get_canal_units_for_organization,
    get_current_context,
    get_current_form_version,
    get_departments,
    get_engineering_business_codes,
    get_water_offices,
)

from services.business_code import (
    build_business_code,
    suggest_next_sequence,
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

from forms.engineering.validation import (
    validate_completion,
)

from forms.engineering.persistence import (
    complete_engineering_record,
    create_engineering_record,
    load_engineering_record_bundle,
    update_engineering_record,
)


class GenericEngineeringSurveyPage(QWidget):
    """
    附表2工程调查通用录入页面。

    页面根据 EngineeringFormDefinition
    生成字段、位置、评价和调查结论，
    并统一负责工程调查的页面生命周期：

    - 新增记录；
    - 草稿保存和继续编辑；
    - 完成调查；
    - 已完成记录修改；
    - 业务编号生成；
    - dirty tracking；
    - 连续录入；
    - 返回拦截；
    - 快捷键操作。

    数据持久化和完成事务由
    forms.engineering.persistence
    及 database 公共接口负责。

    正式原表和汇总 Excel 导出
    由各表对应的 exporter 负责。
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

        # =====================================================
        # 调查生命周期状态
        # =====================================================

        self.current_context = None
        self.form_version = None

        self.editing_record_id = None
        self.editing_record_status = None

        self.is_dirty = False

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

        self._connect_ownership_signals()
        self._connect_dirty_tracking()
        self._setup_keyboard_shortcuts()

        # 构造页面本身不主动读取数据库。
        # 正式进入新增调查时，
        # 由 initialize_new_record()
        # 显式加载当前业务上下文。
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
        # 页面操作区
        # =====================================================

        self._build_runtime_footer(root_layout)

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
    # 归属与编号运行时
    # =========================================================

    def _connect_ownership_signals(
        self,
    ):
        self.department_combo.currentIndexChanged.connect(self.department_changed)

        self.office_combo.currentIndexChanged.connect(self.office_changed)

        self.canal_combo.currentIndexChanged.connect(self.update_business_code)

    def load_departments(
        self,
    ):
        """
        加载启用基层处，
        并级联刷新水管所、渠系和业务编号。
        """

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

    def department_changed(
        self,
    ):
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

    def office_changed(
        self,
    ):
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

    def update_business_code(
        self,
    ):
        """
        根据当前归属和表单定义
        自动生成业务编号。

        工程类型代码来自
        definition.business_type_code。
        """

        # 已经建立的 EngineeringAsset
        # 不重新生成身份编号。
        if self.editing_record_id is not None:
            return

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

        try:
            department_code = department_data["business_code"]

            office_code = office_data["business_code"]

            canal_level_code = canal_data["canal_level"]

            engineering_type_code = self.definition.business_type_code

            if not department_code:
                raise ValueError("当前基层处没有业务代码。")

            if not office_code:
                raise ValueError("当前水管所没有业务代码。")

            existing_codes = get_engineering_business_codes(
                self.current_context["project_id"]
            )

            sequence = suggest_next_sequence(
                existing_codes=(existing_codes),
                department_code=(str(department_code)),
                water_office_code=(str(office_code)),
                canal_level_code=(str(canal_level_code)),
                engineering_type_code=(engineering_type_code),
            )

            business_code = build_business_code(
                department_code=(str(department_code)),
                water_office_code=(str(office_code)),
                canal_level_code=(str(canal_level_code)),
                engineering_type_code=(engineering_type_code),
                sequence=sequence,
            )

            self.business_code_edit.setText(business_code)

            self.business_code_edit.setToolTip("")

            return business_code

        except Exception as error:
            self.business_code_edit.clear()

            # 自动级联过程中不弹出 QMessageBox，
            # 防止切换下拉框时连续弹窗。
            # 正式保存时仍会执行完整校验。
            self.business_code_edit.setToolTip(str(error))

            return None

    # =========================================================
    # 当前业务上下文
    # =========================================================

    def _refresh_runtime_context(
        self,
    ):
        self.current_context = get_current_context()

        if not self.current_context:
            raise ValueError("当前没有可用项目。")

        if self.current_context["batch_id"] is None:
            raise ValueError("当前没有启用的调查批次。")

        self.form_version = get_current_form_version(self.definition.form_code)

        if self.form_version is None:
            raise ValueError(
                f"未找到附表" f"{self.definition.form_number}" "当前版本。"
            )

    def collect_ownership_data(
        self,
    ) -> dict:
        """
        收集 EngineeringAsset / SurveyRecord
        所需的公共归属信息。
        """

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

        return {
            "department_id": department_data["id"],
            "office_id": office_data["id"],
            "canal_id": canal_data["id"],
            "business_code": business_code,
        }

    # =========================================================
    # 页面模式
    # =========================================================

    def _apply_record_mode(
        self,
    ):
        """
        根据当前记录生命周期，
        统一控制标题、按钮和状态提示。
        """

        base_title = self.definition.display_name

        # =====================================================
        # 新增
        # =====================================================

        if self.editing_record_id is None:
            self.title_label.setText(f"{base_title} - 新增")

            self.save_button.setText("保存草稿")

            self.save_button.setEnabled(True)

            self.complete_button.setEnabled(True)

            self.runtime_status_label.setText("正在新增工程调查。")

            return

        # =====================================================
        # 草稿
        # =====================================================

        if self.editing_record_status == "draft":
            self.title_label.setText(f"{base_title} - 编辑草稿")

            self.save_button.setText("保存草稿")

            self.save_button.setEnabled(True)

            self.complete_button.setEnabled(True)

            self.runtime_status_label.setText("正在编辑已保存草稿。")

            return

        # =====================================================
        # 已完成记录
        # =====================================================

        if self.editing_record_status == "completed":
            self.title_label.setText(f"{base_title} - 编辑已完成记录")

            self.save_button.setText("保存修改")

            self.save_button.setEnabled(True)

            # completed 不允许再次执行
            # draft -> completed。
            self.complete_button.setEnabled(False)

            self.runtime_status_label.setText("正在编辑已完成调查记录。")

            return

        raise ValueError("不支持的调查记录状态：" f"{self.editing_record_status}")

    # =========================================================
    # 保存草稿
    # =========================================================

    def _save_current_record(
        self,
        *,
        show_message=True,
    ):
        """
        保存当前工程调查。

        新记录：
            创建 EngineeringAsset
            和 SurveyRecord。

        已有记录：
            更新原调查记录。

        已完成记录保存修改前，
        必须继续满足完整的完成条件。
        """

        try:
            self._refresh_runtime_context()

            ownership = self.collect_ownership_data()

            payload = self.collect_form_data()

            # =================================================
            # completed记录必须始终保持完整
            # =================================================

            if self.editing_record_status == "completed":
                errors = validate_completion(
                    self.definition,
                    payload,
                )

                if errors:
                    error_text = "\n".join(f"• {error}" for error in errors)

                    raise ValueError(
                        "已完成调查的修改"
                        "必须继续满足全部"
                        "完成条件：\n\n"
                        f"{error_text}"
                    )

            asset_name = str(payload.get("asset_name") or "").strip()

            asset_name_definition = self.definition.field_map[
                self.definition.asset_name_field
            ]

            if not asset_name:
                raise ValueError(f"{asset_name_definition.label}" "不能为空。")

            # =================================================
            # 第一次保存
            # =================================================

            if self.editing_record_id is None:
                result = create_engineering_record(
                    self.definition,
                    project_id=(self.current_context["project_id"]),
                    survey_batch_id=(self.current_context["batch_id"]),
                    form_version_id=(self.form_version["id"]),
                    organization_unit_id=(ownership["office_id"]),
                    canal_unit_id=(ownership["canal_id"]),
                    business_code=(ownership["business_code"]),
                    payload=payload,
                )

                self.editing_record_id = int(result["survey_record_id"])

                self.editing_record_status = "draft"

            # =================================================
            # 已有草稿修改
            # =================================================

            else:
                update_engineering_record(
                    self.definition,
                    survey_record_id=(self.editing_record_id),
                    payload=payload,
                )

                result = {
                    "survey_record_id": self.editing_record_id,
                    "record_status": self.editing_record_status,
                }

            # =================================================
            # 工程身份建立后锁定归属
            # =================================================

            self.department_combo.setEnabled(False)

            self.office_combo.setEnabled(False)

            self.canal_combo.setEnabled(False)

            self._apply_record_mode()

            self.is_dirty = False

            self.survey_saved.emit()

            if show_message:
                if self.editing_record_status == "completed":
                    message = (
                        "当前已完成调查的修改"
                        "已保存。\n\n"
                        f"业务编号："
                        f"{ownership['business_code']}"
                    )

                else:
                    message = (
                        "当前调查草稿已保存。\n\n"
                        f"业务编号："
                        f"{ownership['business_code']}"
                    )

                QMessageBox.information(
                    self,
                    "保存成功",
                    message,
                )

            return result

        except Exception as error:
            if show_message:
                QMessageBox.warning(
                    self,
                    "保存失败",
                    str(error),
                )

                return None

            raise

    def save_draft(
        self,
    ):
        self._save_current_record(show_message=True)

    # =========================================================
    # 完成调查
    # =========================================================

    def complete_survey(
        self,
    ):
        """
        将当前工程调查正式推进为 completed。

        页面层负责：
        1. 收集最新页面数据；
        2. 完整性校验；
        3. 用户确认；
        4. 必要时先创建草稿；
        5. 调用通用完成事务；
        6. 更新页面生命周期状态。

        数据库 completed 转换仍由
        persistence/database 层负责。
        """

        try:
            if self.editing_record_status == "completed":
                raise ValueError("当前调查已经完成，" "无需再次执行完成调查。")

            # =================================================
            # 1. 收集并校验最新页面
            # =================================================

            payload = self.collect_form_data()

            errors = validate_completion(
                self.definition,
                payload,
            )

            if errors:
                error_text = "\n".join(f"• {error}" for error in errors)

                raise ValueError("完成调查前请修正" "以下内容：\n\n" f"{error_text}")

            # 归属也属于完成调查前
            # 必须存在的业务上下文。
            self._refresh_runtime_context()

            self.collect_ownership_data()

            # =================================================
            # 2. 用户确认
            # =================================================

            reply = QMessageBox.question(
                self,
                "确认完成调查",
                (
                    "系统将保存当前页面的"
                    "全部修改，随后把本次"
                    "调查标记为“已完成”。\n\n"
                    "是否确认完成本次调查？"
                ),
                (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return None

            # =================================================
            # 3. 新记录先建立草稿身份
            # =================================================

            if self.editing_record_id is None:
                saved = self._save_current_record(show_message=False)

                if saved is None:
                    raise ValueError("当前页面保存失败，" "因此没有执行完成调查。")

            if self.editing_record_id is None:
                raise ValueError("没有有效的调查记录ID。")

            # _save_current_record() 对新记录
            # 建立draft后，页面内容没有变化；
            # 重新收集可以确保使用规范化后的
            # 当前页面状态。
            payload = self.collect_form_data()

            # =================================================
            # 4. 通用完成事务
            # =================================================

            result = complete_engineering_record(
                self.definition,
                survey_record_id=(self.editing_record_id),
                payload=payload,
            )

            previous_survey_date = self.survey_date_edit.text().strip()

            self.editing_record_status = "completed"

            self.is_dirty = False

            self._apply_record_mode()

            self.survey_saved.emit()

            self._handle_completion_success(
                result,
                previous_survey_date=(previous_survey_date),
            )

            return result

        except Exception as error:
            QMessageBox.warning(
                self,
                "完成失败",
                str(error),
            )

            return None

    # =========================================================
    # 数据库记录 -> 表单数据
    # =========================================================

    def _build_loaded_record_data(
        self,
        record,
    ) -> dict:
        """
        将数据库记录转换成
        GenericEngineeringSurveyPage
        可以直接回填的 record_data。

        EngineeringAsset 中的：
        - asset_name
        - point/range 桩号

        优先级高于 JSON 中可能存在的旧副本。
        """

        data = dict(record.get("record_data") or {})

        data[self.definition.asset_name_field] = record.get("asset_name")

        position = self.definition.position

        if position.kind == "point":
            data[position.single_stake_field] = record.get("single_stake_text")

            data[position.single_stake_value_key] = record.get("single_stake_value")

        elif position.kind == "range":
            data[position.start_stake_field] = record.get("start_stake_text")

            data[position.start_stake_value_key] = record.get("start_stake_value")

            data[position.end_stake_field] = record.get("end_stake_text")

            data[position.end_stake_value_key] = record.get("end_stake_value")

        else:
            raise ValueError("暂不支持的工程位置类型：" f"{position.kind}")

        return data

    # =========================================================
    # 打开已有记录
    # =========================================================

    def load_record(
        self,
        survey_record_id,
    ):
        """
        打开已有工程调查。

        支持：
        - draft 继续编辑；
        - completed 读取并保存修改。

        已建立 EngineeringAsset 的
        归属和业务编号保持锁定。
        """

        bundle = load_engineering_record_bundle(
            self.definition,
            survey_record_id=(survey_record_id),
        )

        if bundle is None:
            raise ValueError(
                f"没有找到该附表" f"{self.definition.form_number}" "调查记录。"
            )

        record = bundle["record"]

        record_status = record["record_status"]

        if record_status not in (
            "draft",
            "completed",
        ):
            raise ValueError("当前记录状态暂不支持打开。")

        self._refresh_runtime_context()

        # 先设置记录ID。
        # 这样加载机构过程中不会重新生成
        # 新业务编号。
        self.editing_record_id = int(record["survey_record_id"])

        self.editing_record_status = record_status

        # =====================================================
        # 1. 回填工程归属
        # =====================================================

        self.load_departments()

        if not self._set_combo_by_id(
            self.department_combo,
            record.get("department_id"),
        ):
            raise ValueError("该调查记录所属基层处" "已不存在或不可用。")

        self.department_changed()

        if not self._set_combo_by_id(
            self.office_combo,
            record.get("office_id"),
        ):
            raise ValueError("该调查记录所属水管所" "已不存在或不可用。")

        self.office_changed()

        if not self._set_combo_by_id(
            self.canal_combo,
            record.get("canal_id"),
        ):
            raise ValueError("该调查记录所属渠系" "已不存在或不可用。")

        # 加载机构时可能清空了编号，
        # 最终恢复数据库原编号。
        self.business_code_edit.setText(record.get("business_code") or "")

        # =====================================================
        # 2. 回填表单数据
        # =====================================================

        self.load_form_data(
            record_data=(self._build_loaded_record_data(record)),
            inspection_results=(bundle["inspection_results"]),
            survey_date=(record.get("survey_date")),
            overall_grade=(record.get("overall_grade")),
            survey_comment=(record.get("survey_comment")),
        )

        # =====================================================
        # 3. 已建立工程锁定归属
        # =====================================================

        self.department_combo.setEnabled(False)

        self.office_combo.setEnabled(False)

        self.canal_combo.setEnabled(False)

        self._apply_record_mode()

        # 数据库回填不属于用户修改。
        self.is_dirty = False

        return record

    # =========================================================
    # Combo辅助
    # =========================================================

    @staticmethod
    def _set_combo_by_id(
        combo,
        target_id,
    ) -> bool:
        if target_id is None:
            return False

        for index in range(combo.count()):
            data = combo.itemData(index)

            if isinstance(data, dict) and data.get("id") == target_id:
                combo.setCurrentIndex(index)

                return True

        return False

    # =========================================================
    # 快捷键
    # =========================================================

    def _setup_keyboard_shortcuts(
        self,
    ):
        """
        工程调查高频录入快捷键。

        Ctrl+S：
            保存当前记录。

        Ctrl+Enter / Ctrl+Return：
            完成调查。
        """

        self.save_shortcut = QShortcut(
            QKeySequence("Ctrl+S"),
            self,
        )

        self.save_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self.save_shortcut.activated.connect(self.save_draft)

        self.complete_shortcut = QShortcut(
            QKeySequence("Ctrl+Return"),
            self,
        )

        self.complete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self.complete_shortcut.activated.connect(self._complete_from_shortcut)

        self.complete_enter_shortcut = QShortcut(
            QKeySequence("Ctrl+Enter"),
            self,
        )

        self.complete_enter_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )

        self.complete_enter_shortcut.activated.connect(self._complete_from_shortcut)

    def _complete_from_shortcut(
        self,
    ):
        if not self.complete_button.isEnabled():
            return

        self.complete_survey()

    # =========================================================
    # Dirty tracking
    # =========================================================

    def _connect_dirty_tracking(
        self,
    ):
        """
        只把用户实际编辑标记为 dirty。

        程序执行 setText() / 回填时，
        不应自动变成未保存状态。
        """

        for runtime in self.field_runtimes.values():
            runtime.connect_dirty(self._mark_dirty)

        self.survey_date_edit.textEdited.connect(self._mark_dirty)

        self.survey_comment_edit.textChanged.connect(self._mark_dirty)

        for button in self.overall_grade_buttons.values():
            button.clicked.connect(self._mark_dirty)

        self.evaluation_section.grade_changed.connect(self._mark_dirty)

        self.department_combo.activated.connect(self._mark_dirty)

        self.office_combo.activated.connect(self._mark_dirty)

        self.canal_combo.activated.connect(self._mark_dirty)

    def _mark_dirty(
        self,
        *args,
    ):
        self.is_dirty = True

    # =========================================================
    # 返回拦截
    # =========================================================

    def confirm_leave_changes(
        self,
    ) -> bool:
        """
        存在未保存修改时，
        询问用户如何处理。

        True：
            可以离开页面。

        False：
            留在当前页面。
        """

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
            (
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            ),
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Save:
            result = self._save_current_record(show_message=True)

            return result is not None

        if reply == QMessageBox.StandardButton.Discard:
            self.is_dirty = False
            return True

        return False

    def request_back(
        self,
    ):
        if not self.confirm_leave_changes():
            return

        self.back_requested.emit()

    # =========================================================
    # 连续录入
    # =========================================================

    def _focus_new_entry_start(
        self,
    ):
        """
        连续录入下一条时：
        - 回到表单顶部；
        - 聚焦工程名称字段。
        """

        vertical_bar = self.scroll_area.verticalScrollBar()

        vertical_bar.setValue(vertical_bar.minimum())

        self.get_field_widget(self.definition.asset_name_field).setFocus()

    def _ask_after_completion(
        self,
        result,
    ) -> str:
        """
        完成调查后询问下一步。

        返回：
            "continue"
            "back"
        """

        success_box = QMessageBox(self)

        success_box.setIcon(QMessageBox.Icon.Information)

        success_box.setWindowTitle("完成成功")

        success_box.setText(
            (
                "当前工程调查已标记为已完成。\n\n"
                f"调查记录ID："
                f"{result['survey_record_id']}\n"
                f"已填写分项评价："
                f"{result['inspection_count']} 项\n\n"
                "请选择下一步操作。"
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

        if success_box.clickedButton() is continue_button:
            return "continue"

        return "back"

    def _handle_completion_success(
        self,
        result,
        *,
        previous_survey_date=None,
    ):
        action = self._ask_after_completion(result)

        if action == "continue":
            self.prepare_new(survey_date=(previous_survey_date or None))

            self.is_dirty = False

            QTimer.singleShot(
                0,
                self._focus_new_entry_start,
            )

            return "continue"

        self.back_requested.emit()

        return "back"

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
            title=(
                self.definition.evaluation_title
            ),
            evaluation_items=(
                self.definition.evaluation_items
            ),
            grade_options=(
                self.definition.grade_options
            ),
        )

        self.form_layout.addWidget(
            self.evaluation_section
        )

        # 正式调查表如果在评价区后存在
        # 补充说明，由 definition 统一声明。
        #
        # 没有注释的表单不创建额外控件。
        self.evaluation_note_label = None

        if self.definition.evaluation_note:
            note_label = QLabel(
                self.definition.evaluation_note
            )

            note_label.setWordWrap(True)

            note_label.setStyleSheet(
                "color: #607080;"
            )

            self.form_layout.addWidget(
                note_label
            )

            self.evaluation_note_label = (
                note_label
            )

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
    # 底部操作区
    # =========================================================

    def _build_runtime_footer(
        self,
        root_layout,
    ):
        footer_layout = QHBoxLayout()

        self.back_button = QPushButton("返回")

        self.back_button.clicked.connect(self.request_back)

        self.runtime_status_label = QLabel(
            "当前已接入草稿保存与重新打开；" "完成调查将在下一阶段接入。"
        )

        self.runtime_status_label.setStyleSheet("color: #607080;")

        self.shortcut_hint_label = QLabel(
            "快捷键：Ctrl+S 保存　|　" "Ctrl+Enter 完成调查"
        )

        self.shortcut_hint_label.setStyleSheet("color: #607080;")

        # 暂时保留旧属性名，
        # 避免已有测试或开发代码突然失效。
        self.preview_status_label = self.runtime_status_label

        self.save_button = QPushButton("保存草稿")

        self.save_button.setMinimumWidth(120)

        self.complete_button = QPushButton("完成调查")

        self.complete_button.setMinimumWidth(120)

        self.complete_button.clicked.connect(self.complete_survey)

        self.save_button.clicked.connect(self.save_draft)

        footer_layout.addWidget(self.back_button)

        footer_layout.addStretch()

        footer_layout.addWidget(self.runtime_status_label)

        footer_layout.addSpacing(12)

        footer_layout.addWidget(self.shortcut_hint_label)

        footer_layout.addSpacing(12)

        footer_layout.addWidget(self.save_button)

        footer_layout.addWidget(self.complete_button)

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
        return self.evaluation_section.collect_results()

    def load_evaluation_results(
        self,
        results,
    ):
        self.evaluation_section.load_results(results or [])

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

        record_data = self.collect_record_data()

        conclusion = self.collect_conclusion_data()

        asset_name = record_data.get(self.definition.asset_name_field)

        return {
            "asset_name": asset_name,
            "record_data": record_data,
            "position": (self.collect_position_data()),
            "inspection_results": (self.collect_evaluation_results()),
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

        for runtime in self.field_runtimes.values():
            runtime.clear()

        self.evaluation_section.clear()

        self.clear_overall_grade()

        self.survey_date_edit.clear()

        self.survey_comment_edit.clear()

        self.business_code_edit.clear()

    def initialize_new_record(
        self,
        *,
        survey_date=None,
    ):
        """
        正式进入一条新的调查记录。

        与单纯构造 QWidget 不同，
        本方法开始读取实际业务上下文。
        """

        self.current_context = get_current_context()

        if not self.current_context:
            raise ValueError("当前没有可用项目。")

        if self.current_context["batch_id"] is None:
            raise ValueError("当前没有启用的调查批次。")

        self.form_version = get_current_form_version(self.definition.form_code)

        if self.form_version is None:
            raise ValueError(
                f"未找到附表" f"{self.definition.form_number}" "当前版本。"
            )

        # 先加载归属，
        # 再进入新增状态。
        self.load_departments()

        self.prepare_new(survey_date=survey_date)

    def prepare_new(
        self,
        *,
        survey_date=None,
    ):
        """
        切换到新增调查状态。

        保留当前基层处、水管所、渠系，
        清空具体工程内容，
        并重新生成下一业务编号。
        """

        self.editing_record_id = None
        self.editing_record_status = None

        self.department_combo.setEnabled(True)

        self.office_combo.setEnabled(True)

        self.canal_combo.setEnabled(True)

        self.clear_form_data()

        if survey_date is None:
            survey_date = date.today().isoformat()

        self.survey_date_edit.setText(survey_date)

        self.update_business_code()

        self._apply_record_mode()

        self.is_dirty = False

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
        self.load_record_data(record_data)

        self.load_evaluation_results(inspection_results)

        self.load_conclusion_data(
            survey_date=survey_date,
            overall_grade=overall_grade,
            survey_comment=survey_comment,
        )

    # =========================================================
    # 完成调查校验
    # =========================================================

    def validate_for_completion(
        self,
    ) -> list[str]:
        """
        校验当前页面是否满足完成调查条件。

        字段格式错误由 Runtime / 输入辅助函数
        抛出 ValueError；
        本方法将其转换为统一错误列表。
        """

        try:
            payload = self.collect_form_data()

        except ValueError as error:
            return [str(error)]

        return validate_completion(
            self.definition,
            payload,
        )
