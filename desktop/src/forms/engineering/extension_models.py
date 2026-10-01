from dataclasses import (
    dataclass,
    field,
)
import re
from typing import (
    Any,
    Callable,
    Literal,
)


ValueSource = Literal[
    "query_record",
    "record",
    "record_data",
]

ColumnAlignment = Literal[
    "left",
    "center",
    "right",
]

PageOrientation = Literal[
    "landscape",
    "portrait",
]

ValueFormatter = Callable[..., Any]


_CELL_REFERENCE_PATTERN = re.compile(
    r"^[A-Z]{1,3}[1-9]\d*$"
)

_CELL_RANGE_PATTERN = re.compile(
    r"^[A-Z]{1,3}[1-9]\d*:[A-Z]{1,3}[1-9]\d*$"
)

_COLUMN_REFERENCE_PATTERN = re.compile(
    r"^[A-Z]{1,3}$"
)


def _validate_cell_reference(
    value: str,
    *,
    field_name: str,
) -> None:
    if not _CELL_REFERENCE_PATTERN.fullmatch(
        value
    ):
        raise ValueError(
            f"{field_name} 必须是有效的 Excel 单元格坐标。"
        )


def _validate_alignment(
    value: str,
) -> None:
    if value not in (
        "left",
        "center",
        "right",
    ):
        raise ValueError(
            "列对齐方式仅支持 "
            "left/center/right。"
        )


@dataclass(frozen=True)
class ValueBindingDefinition:
    """
    一个只读展示值的数据绑定。

    source 决定从哪一层数据读取：
    - query_record：统一查询结果；
    - record：generic persistence 返回的正式调查记录；
    - record_data：record/query_record 中的 record_data。

    keys 支持一个或多个字段。
    多字段绑定必须提供 formatter，
    例如：宽×高、孔数/宽×高、起止桩号。
    """

    source: ValueSource
    keys: tuple[str, ...]
    formatter: ValueFormatter | None = None

    def __post_init__(self):
        if self.source not in (
            "query_record",
            "record",
            "record_data",
        ):
            raise ValueError(
                "不支持的数据绑定 source："
                f"{self.source}"
            )

        if not self.keys:
            raise ValueError(
                "ValueBindingDefinition "
                "至少必须包含一个 key。"
            )

        clean_keys = []

        for key in self.keys:
            if not key or not key.strip():
                raise ValueError(
                    "数据绑定 key 不能为空。"
                )

            clean_keys.append(
                key.strip()
            )

        if len(clean_keys) != len(
            set(clean_keys)
        ):
            raise ValueError(
                "同一个数据绑定中不能重复引用 key。"
            )

        if (
            len(self.keys) > 1
            and self.formatter is None
        ):
            raise ValueError(
                "多字段数据绑定必须配置 formatter。"
            )

    @classmethod
    def single(
        cls,
        *,
        source: ValueSource,
        key: str,
        formatter: ValueFormatter | None = None,
    ):
        return cls(
            source=source,
            keys=(key,),
            formatter=formatter,
        )

    @classmethod
    def composite(
        cls,
        *,
        source: ValueSource,
        keys: tuple[str, ...],
        formatter: ValueFormatter,
    ):
        return cls(
            source=source,
            keys=keys,
            formatter=formatter,
        )


@dataclass(frozen=True)
class ListColumnDefinition:
    """
    工程调查当前批次列表中的一列。
    """

    header: str
    width: int
    binding: ValueBindingDefinition
    alignment: ColumnAlignment = "left"

    def __post_init__(self):
        if not self.header.strip():
            raise ValueError(
                "ListColumnDefinition.header "
                "不能为空。"
            )

        if self.width <= 0:
            raise ValueError(
                "列表列宽必须大于 0。"
            )

        _validate_alignment(
            self.alignment
        )


@dataclass(frozen=True)
class ListDefinition:
    """
    一张附表2的当前批次列表展示定义。

    本对象只描述列表差异，
    不负责 Qt 控件、查询、删除或导出执行。
    """

    new_button_text: str
    keyword_placeholder: str
    position_label: str
    columns: tuple[
        ListColumnDefinition,
        ...,
    ]

    keyword_bindings: tuple[
        ValueBindingDefinition,
        ...,
    ] = field(
        default_factory=lambda: (
            ValueBindingDefinition.single(
                source="query_record",
                key="business_code",
            ),
            ValueBindingDefinition.single(
                source="query_record",
                key="asset_name",
            ),
            ValueBindingDefinition.single(
                source="query_record",
                key="engineering_position",
            ),
        )
    )

    show_grade_statistics: bool = True

    def __post_init__(self):
        if not self.new_button_text.strip():
            raise ValueError(
                "列表新增按钮文字不能为空。"
            )

        if not self.keyword_placeholder.strip():
            raise ValueError(
                "列表关键词提示文字不能为空。"
            )

        if not self.position_label.strip():
            raise ValueError(
                "列表工程位置标签不能为空。"
            )

        if not self.columns:
            raise ValueError(
                "ListDefinition 至少需要一列。"
            )

        headers = [
            column.header
            for column in self.columns
        ]

        if len(headers) != len(set(headers)):
            raise ValueError(
                "列表列标题不能重复。"
            )

        if not self.keyword_bindings:
            raise ValueError(
                "列表至少需要一个关键词来源。"
            )

        for binding in (
            tuple(
                column.binding
                for column
                in self.columns
            )
            + self.keyword_bindings
        ):
            if binding.source not in (
                "query_record",
                "record_data",
            ):
                raise ValueError(
                    "ListDefinition 只允许使用 "
                    "query_record/record_data 数据源。"
                )


@dataclass(frozen=True)
class SummaryColumnDefinition:
    """
    单表详细汇总 Excel 的一个基础信息列。

    “序号”、评价列和调查结论列
    由 Generic Summary Exporter 统一生成，
    因此这里仅定义各表自己的基础列。
    """

    header: str
    width: int
    binding: ValueBindingDefinition
    alignment: ColumnAlignment = "left"

    def __post_init__(self):
        if not self.header.strip():
            raise ValueError(
                "SummaryColumnDefinition.header "
                "不能为空。"
            )

        if self.width <= 0:
            raise ValueError(
                "汇总列宽必须大于 0。"
            )

        _validate_alignment(
            self.alignment
        )


@dataclass(frozen=True)
class SummaryExportDefinition:
    """
    一张附表2的详细汇总 Excel 定义。

    公共样式、评价列、结论列、冻结窗格、
    自动筛选和页面设置由通用导出器负责。
    """

    sheet_name: str
    columns: tuple[
        SummaryColumnDefinition,
        ...,
    ]

    header_height: int = 36
    evaluation_column_width: int = 20

    def __post_init__(self):
        if not self.sheet_name.strip():
            raise ValueError(
                "详细汇总工作表名称不能为空。"
            )

        if not self.columns:
            raise ValueError(
                "SummaryExportDefinition "
                "至少需要一个基础列。"
            )

        headers = [
            column.header
            for column in self.columns
        ]

        if len(headers) != len(set(headers)):
            raise ValueError(
                "详细汇总列标题不能重复。"
            )

        if self.header_height <= 0:
            raise ValueError(
                "详细汇总表头高度必须大于 0。"
            )

        if self.evaluation_column_width <= 0:
            raise ValueError(
                "评价列宽必须大于 0。"
            )











from shared.forms.engineering.extension_models import (
    OriginalFormCellBinding,
    OriginalFormEvaluationBinding,
    OriginalFormConclusionBinding,
    OriginalFormPrintSettings,
    OriginalFormExportDefinition,
)
