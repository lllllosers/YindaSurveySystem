from dataclasses import dataclass
from typing import (
    Any,
    Literal,
    Mapping,
)


from forms.engineering.extension_models import (
    ListDefinition,
    OriginalFormExportDefinition,
    SummaryExportDefinition,
)


FieldType = Literal[
    "text",
    "decimal",
    "signed_decimal",
    "integer",
    "month",
    "stake",
    "choice",
]

PositionType = Literal[
    "point",
    "range",
]


@dataclass(frozen=True)
class FieldDefinition:
    """
    一项工程调查输入字段。

    本对象只描述“字段是什么”，
    不负责创建 Qt 控件。
    """

    key: str
    label: str
    input_type: FieldType = "text"

    required: bool = True

    unit: str | None = None
    placeholder: str | None = None

    # 当前主要服务 integer 类型。
    maximum: int | None = None

    # choice 类型的固定候选项。
    # 仅在 input_type="choice" 时允许配置。
    choices: tuple[str, ...] | None = None

    def __post_init__(self):
        if self.input_type == "choice":
            if not self.choices:
                raise ValueError(
                    "choice 字段必须配置至少一个候选项。"
                )

            normalized = tuple(
                str(choice).strip()
                for choice in self.choices
            )

            if any(
                not choice
                for choice in normalized
            ):
                raise ValueError(
                    "choice 字段候选项不能为空。"
                )

            if (
                len(normalized)
                != len(set(normalized))
            ):
                raise ValueError(
                    "choice 字段候选项不能重复。"
                )

            object.__setattr__(
                self,
                "choices",
                normalized,
            )

        elif self.choices is not None:
            raise ValueError(
                "只有 choice 字段可以配置 choices。"
            )

    @property
    def display_label(self) -> str:
        """
        生成页面使用的标签文字。

        正式原表没有单位时，
        unit 应保持 None，
        不自行补充。
        """

        if self.unit:
            return (
                f"{self.label}"
                f"（{self.unit}）"
            )

        return self.label


@dataclass(frozen=True)
class FieldRowDefinition:
    """
    表单中的一行。

    普通情况：
        一个字段一行。

    组合情况：
        同一行放多个字段，
        例如：
        断面尺寸（宽×高）。
    """

    field_keys: tuple[str, ...]

    # None 时：
    # 单字段行使用该字段自己的 label。
    label: str | None = None

    # 多字段时可使用：
    # ×、～ 等分隔符。
    separator: str | None = None

    def __post_init__(self):
        if not self.field_keys:
            raise ValueError(
                "FieldRowDefinition "
                "至少必须包含一个字段。"
            )

        if (
            len(set(self.field_keys))
            != len(self.field_keys)
        ):
            raise ValueError(
                "同一表单行不能重复引用字段。"
            )


@dataclass(frozen=True)
class FormSectionDefinition:
    """
    一组工程基本信息。

    例如：
    二、工程基本信息
    三、结构参数
    """

    title: str
    rows: tuple[
        FieldRowDefinition,
        ...,
    ]

    def __post_init__(self):
        if not self.title.strip():
            raise ValueError(
                "表单分区标题不能为空。"
            )

        if not self.rows:
            raise ValueError(
                f"{self.title} "
                "至少需要一行字段。"
            )


@dataclass(frozen=True)
class PositionDefinition:
    """
    EngineeringAsset 的工程位置定义。

    point:
        一个桩号。

    range:
        起始桩号 + 终止桩号。
    """

    kind: PositionType

    single_stake_field: (
        str | None
    ) = None

    single_stake_value_key: (
        str | None
    ) = None

    start_stake_field: (
        str | None
    ) = None

    start_stake_value_key: (
        str | None
    ) = None

    end_stake_field: (
        str | None
    ) = None

    end_stake_value_key: (
        str | None
    ) = None

    @classmethod
    def point(
        cls,
        *,
        stake_field: str,
        stake_value_key: str,
    ):
        return cls(
            kind="point",
            single_stake_field=(
                stake_field
            ),
            single_stake_value_key=(
                stake_value_key
            ),
        )

    @classmethod
    def range(
        cls,
        *,
        start_stake_field: str,
        start_stake_value_key: str,
        end_stake_field: str,
        end_stake_value_key: str,
    ):
        return cls(
            kind="range",
            start_stake_field=(
                start_stake_field
            ),
            start_stake_value_key=(
                start_stake_value_key
            ),
            end_stake_field=(
                end_stake_field
            ),
            end_stake_value_key=(
                end_stake_value_key
            ),
        )


@dataclass(frozen=True)
class EngineeringFormDefinition:
    """
    一张附表2工程调查表的
    声明式定义。

    这里只描述：
    - 表单身份；
    - 工程身份；
    - 字段；
    - 页面布局；
    - 工程位置；
    - 评价配置。

    保存、加载、Qt界面和Excel导出
    不放在这里。
    """

    form_code: str
    form_number: str
    form_name: str

    asset_type: str
    business_type_code: str

    # 哪一个字段代表
    # EngineeringAsset.asset_name。
    asset_name_field: str

    position: PositionDefinition

    fields: tuple[
        FieldDefinition,
        ...,
    ]

    sections: tuple[
        FormSectionDefinition,
        ...,
    ]

    evaluation_items: tuple[
        Mapping[str, Any],
        ...,
    ]

    grade_options: tuple[
        str,
        ...,
    ] = (
        "A",
        "B",
        "C",
        "D",
    )

    evaluation_title: str = (
        "分项评价"
    )

    # 正式调查表在分项评价区域之后
    # 可能存在补充说明。
    #
    # 例如：
    # 渡槽其它部位的定义。
    evaluation_note: (
        str | None
    ) = None

    conclusion_title: str = (
        "调查结论"
    )

    # =====================================================
    # 列表 / 汇总 / 正式原表扩展定义
    # =====================================================
    #
    # 三者仅描述表级差异；
    # Qt / openpyxl / 数据库执行逻辑不放入 Definition。
    # 当前2.1～2.6尚未迁移时保持 None，
    # 后续 R1-13B/C/D 分阶段接入。
    list_definition: (
        ListDefinition | None
    ) = None

    summary_export_definition: (
        SummaryExportDefinition | None
    ) = None

    original_form_export_definition: (
        OriginalFormExportDefinition | None
    ) = None

    @property
    def field_map(
        self,
    ) -> dict[
        str,
        FieldDefinition,
    ]:
        return {
            field.key: field
            for field in self.fields
        }

    @property
    def display_name(self) -> str:
        return (
            f"附表{self.form_number} "
            f"{self.form_name}"
        )

    def __post_init__(self):
        # =====================================================
        # 1. 表单身份
        # =====================================================

        if not self.form_code.startswith(
            "form_2_"
        ):
            raise ValueError(
                "工程调查表 form_code "
                "必须使用 form_2_x 格式。"
            )

        if (
            len(
                self.business_type_code
            )
            != 2
            or not (
                self.business_type_code
                .isdigit()
            )
        ):
            raise ValueError(
                "工程类型代码必须为"
                "2位数字字符串。"
            )

        if not self.asset_type.strip():
            raise ValueError(
                "asset_type 不能为空。"
            )

        # =====================================================
        # 2. 字段唯一性
        # =====================================================

        field_keys = [
            field.key
            for field in self.fields
        ]

        if (
            len(field_keys)
            != len(set(field_keys))
        ):
            raise ValueError(
                "同一调查表中存在"
                "重复字段 key。"
            )

        field_key_set = set(
            field_keys
        )

        if (
            self.asset_name_field
            not in field_key_set
        ):
            raise ValueError(
                "asset_name_field "
                "必须引用已定义字段。"
            )

        # =====================================================
        # 3. 页面布局引用
        # =====================================================

        row_field_keys = []

        for section in self.sections:
            for row in section.rows:
                for (
                    field_key
                ) in row.field_keys:
                    if (
                        field_key
                        not in field_key_set
                    ):
                        raise ValueError(
                            "页面布局引用了"
                            "不存在的字段："
                            f"{field_key}"
                        )

                    row_field_keys.append(
                        field_key
                    )

        if (
            len(row_field_keys)
            != len(
                set(row_field_keys)
            )
        ):
            raise ValueError(
                "同一个字段不能在"
                "多个页面位置重复出现。"
            )

        if (
            set(row_field_keys)
            != field_key_set
        ):
            missing = (
                field_key_set
                - set(row_field_keys)
            )

            raise ValueError(
                "存在未加入页面布局的字段："
                + "、".join(
                    sorted(missing)
                )
            )

        # =====================================================
        # 4. 工程位置
        # =====================================================

        if (
            self.position.kind
            == "point"
        ):
            stake_field = (
                self.position
                .single_stake_field
            )

            if (
                not stake_field
                or stake_field
                not in field_key_set
            ):
                raise ValueError(
                    "点工程必须配置"
                    "有效的桩号字段。"
                )

            if (
                self.field_map[
                    stake_field
                ].input_type
                != "stake"
            ):
                raise ValueError(
                    "点工程位置字段"
                    "必须为 stake 类型。"
                )

            if not (
                self.position
                .single_stake_value_key
            ):
                raise ValueError(
                    "点工程必须配置"
                    "桩号数值存储 key。"
                )

        elif (
            self.position.kind
            == "range"
        ):
            start_field = (
                self.position
                .start_stake_field
            )

            end_field = (
                self.position
                .end_stake_field
            )

            for field_key in (
                start_field,
                end_field,
            ):
                if (
                    not field_key
                    or field_key
                    not in field_key_set
                ):
                    raise ValueError(
                        "区间工程必须配置"
                        "有效的起止桩号字段。"
                    )

                if (
                    self.field_map[
                        field_key
                    ].input_type
                    != "stake"
                ):
                    raise ValueError(
                        "区间工程起止位置"
                        "必须为 stake 类型。"
                    )

            if not (
                self.position
                .start_stake_value_key
            ):
                raise ValueError(
                    "区间工程必须配置"
                    "起始桩号数值存储 key。"
                )

            if not (
                self.position
                .end_stake_value_key
            ):
                raise ValueError(
                    "区间工程必须配置"
                    "终止桩号数值存储 key。"
                )

        else:
            raise ValueError(
                "暂不支持的工程位置类型："
                f"{self.position.kind}"
            )

        # =====================================================
        # 5. 评价等级
        # =====================================================

        if not self.grade_options:
            raise ValueError(
                "至少需要配置一个评价等级。"
            )

        if (
            len(
                self.grade_options
            )
            != len(
                set(
                    self.grade_options
                )
            )
        ):
            raise ValueError(
                "评价等级不能重复。"
            )

        database_grades = {
            "A",
            "B",
            "C",
            "D",
        }

        if not set(
            self.grade_options
        ).issubset(
            database_grades
        ):
            raise ValueError(
                "当前数据库仅支持"
                "A/B/C/D评价等级。"
            )

        if (
            self.evaluation_note
            is not None
            and not (
                self.evaluation_note
                .strip()
            )
        ):
            raise ValueError(
                "evaluation_note "
                "不能是空字符串。"
            )

        # =====================================================
        # 6. 评价项目合同
        # =====================================================

        item_codes = []

        for item in (
            self.evaluation_items
        ):
            for required_key in (
                "item_code",
                "category",
                "item_name",
                "standards",
            ):
                if (
                    required_key
                    not in item
                ):
                    raise ValueError(
                        "评价项目缺少字段："
                        f"{required_key}"
                    )

            item_code = str(
                item["item_code"]
            )

            item_codes.append(
                item_code
            )

            standards = item[
                "standards"
            ]

            for grade in (
                self.grade_options
            ):
                if (
                    grade
                    not in standards
                ):
                    raise ValueError(
                        f"评价项目 "
                        f"{item_code} "
                        f"缺少 {grade} "
                        "级标准。"
                    )

        if (
            len(item_codes)
            != len(
                set(item_codes)
            )
        ):
            raise ValueError(
                "评价项目 item_code "
                "不能重复。"
            )

        # =====================================================
        # 7. List / Summary / Original Form 扩展合同
        # =====================================================
        #
        # extension_models 负责各自内部结构校验；
        # EngineeringFormDefinition 只负责需要结合
        # 本表正式字段 / evaluation_items 才能完成的
        # 跨定义引用校验。
        # =====================================================

        extension_bindings = []

        if self.list_definition is not None:
            extension_bindings.extend(
                column.binding
                for column
                in self.list_definition.columns
            )
            extension_bindings.extend(
                self.list_definition
                .keyword_bindings
            )

        if (
            self.summary_export_definition
            is not None
        ):
            extension_bindings.extend(
                column.binding
                for column
                in self.summary_export_definition
                .columns
            )

        if (
            self.original_form_export_definition
            is not None
        ):
            extension_bindings.extend(
                cell_binding.binding
                for cell_binding
                in self.original_form_export_definition
                .field_bindings
            )

        for binding in extension_bindings:
            if binding.source != "record_data":
                continue

            for key in binding.keys:
                if key not in field_key_set:
                    raise ValueError(
                        "扩展定义引用了不存在的 "
                        "record_data 字段："
                        f"{key}"
                    )

        # 正式原表的评价区域需要结合本表
        # evaluation_items 数量后才能确定完整写入范围。
        original_definition = (
            self.original_form_export_definition
        )

        if original_definition is not None:
            evaluation_binding = (
                original_definition
                .evaluation_binding
            )

            evaluation_cells = {
                (
                    f"{evaluation_binding.column}"
                    f"{evaluation_binding.start_row + index}"
                )
                for index in range(
                    len(self.evaluation_items)
                )
            }

            occupied_cells = {
                cell_binding.cell
                for cell_binding
                in original_definition
                .field_bindings
            }

            occupied_cells.update(
                {
                    original_definition
                    .conclusion_binding
                    .survey_comment_cell,
                    original_definition
                    .conclusion_binding
                    .overall_grade_cell,
                    original_definition
                    .conclusion_binding
                    .survey_date_cell,
                }
            )

            overlap = (
                evaluation_cells
                & occupied_cells
            )

            if overlap:
                raise ValueError(
                    "分项评价写入区域与其他正式原表"
                    "绑定冲突："
                    + "、".join(
                        sorted(overlap)
                    )
                )
