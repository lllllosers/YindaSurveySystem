from forms.engineering.extension_models import (
    ListColumnDefinition,
    ListDefinition,
    ValueBindingDefinition,
)

from forms.engineering.formatters import (
    format_record_status,
)


STANDARD_ENGINEERING_LIST_HEADERS = (
    "业务编号",
    "工程名称",
    "基层处",
    "水管所",
    "渠系",
    "工程位置",
    "工程状况类别",
    "调查时间",
    "状态",
    "修改时间",
)

STANDARD_ENGINEERING_LIST_WIDTHS = (
    155,
    180,
    130,
    130,
    150,
    180,
    105,
    110,
    90,
    160,
)


def _query_column(
    *,
    header,
    width,
    key,
    formatter=None,
):
    return ListColumnDefinition(
        header=header,
        width=width,
        binding=(
            ValueBindingDefinition.single(
                source="query_record",
                key=key,
                formatter=formatter,
            )
        ),
    )


def build_standard_engineering_list_definition(
    *,
    new_button_text,
):
    """
    构造附表2工程调查统一当前批次列表。

    2.1～2.6统一使用：
    业务编号、工程名称、组织机构、渠系、工程位置、
    工程状况类别、调查时间、状态、修改时间。

    点工程与区间工程的差异已经由统一查询层收敛为
    engineering_position，列表层不再感知 point/range。
    """

    columns = (
        _query_column(
            header="业务编号",
            width=155,
            key="business_code",
        ),
        _query_column(
            header="工程名称",
            width=180,
            key="asset_name",
        ),
        _query_column(
            header="基层处",
            width=130,
            key="department_name",
        ),
        _query_column(
            header="水管所",
            width=130,
            key="office_name",
        ),
        _query_column(
            header="渠系",
            width=150,
            key="canal_name",
        ),
        _query_column(
            header="工程位置",
            width=180,
            key="engineering_position",
        ),
        _query_column(
            header="工程状况类别",
            width=105,
            key="overall_grade",
        ),
        _query_column(
            header="调查时间",
            width=110,
            key="survey_date",
        ),
        _query_column(
            header="状态",
            width=90,
            key="record_status",
            formatter=format_record_status,
        ),
        _query_column(
            header="修改时间",
            width=160,
            key="updated_at",
        ),
    )

    return ListDefinition(
        new_button_text=new_button_text,
        keyword_placeholder=(
            "业务编号 / 工程名称 / 工程位置"
        ),
        position_label="工程位置",
        columns=columns,
        show_grade_statistics=True,
    )
