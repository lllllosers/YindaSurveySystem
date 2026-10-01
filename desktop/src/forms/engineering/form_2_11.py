from dataclasses import fields

from forms.engineering.models import EngineeringFormDefinition

from shared.forms.engineering.form_2_11 import FORM_2_11 as CORE_DEFINITION

from forms.engineering.extension_models import (
    SummaryColumnDefinition,
    SummaryExportDefinition,
    ValueBindingDefinition,
)

from forms.engineering.formatters import (
    format_stake_range_compact,
)

from forms.engineering.list_definitions import (
    build_standard_engineering_list_definition,
)

FORM_2_11 = EngineeringFormDefinition(
    **{field.name: getattr(CORE_DEFINITION, field.name) for field in fields(CORE_DEFINITION)},
    list_definition=build_standard_engineering_list_definition(
            new_button_text='新增堰槽量水设施调查',
        ),
    summary_export_definition=SummaryExportDefinition(
        sheet_name='堰槽量水设施调查汇总',
        columns=(
            SummaryColumnDefinition(
                header='业务编号',
                width=22,
                binding=ValueBindingDefinition.single(
                    source='record',
                    key='business_code',
                ),
            ),
            SummaryColumnDefinition(
                header='名称',
                width=20,
                binding=ValueBindingDefinition.single(
                    source='record',
                    key='asset_name',
                ),
            ),
            SummaryColumnDefinition(
                header='基层处',
                width=16,
                binding=ValueBindingDefinition.single(
                    source='query_record',
                    key='department_name',
                ),
            ),
            SummaryColumnDefinition(
                header='水管所',
                width=16,
                binding=ValueBindingDefinition.single(
                    source='query_record',
                    key='office_name',
                ),
            ),
            SummaryColumnDefinition(
                header='渠系',
                width=18,
                binding=ValueBindingDefinition.single(
                    source='query_record',
                    key='canal_name',
                ),
            ),
            SummaryColumnDefinition(
                header='桩号',
                width=14,
                binding=ValueBindingDefinition.composite(
                            source="record_data",
                            keys=("start_stake", "end_stake"),
                            formatter=format_stake_range_compact,
                        ),
            ),
            SummaryColumnDefinition(
                header='设计流量（m³/s）',
                width=16,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='design_flow',
                ),
            ),
            SummaryColumnDefinition(
                header='建筑物等级',
                width=14,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='structure_grade',
                ),
            ),
            SummaryColumnDefinition(
                header='建成年月',
                width=14,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='build_date',
                ),
            ),
            SummaryColumnDefinition(
                header='加固改造年月',
                width=16,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='renovation_date',
                ),
            ),
            SummaryColumnDefinition(
                header='长度（m）',
                width=12,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='length',
                ),
            ),
            SummaryColumnDefinition(
                header='加大流量（m³/s）',
                width=16,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='increased_flow',
                ),
            ),
            SummaryColumnDefinition(
                header='量水堰类型',
                width=18,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='measurement_weir_type',
                ),
            ),
            SummaryColumnDefinition(
                header='主构建筑材料',
                width=18,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='main_structure_material',
                ),
            ),
            SummaryColumnDefinition(
                header='槽型（W×L）',
                width=16,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='flume_type',
                ),
            ),
        ),
    ),
)
