from dataclasses import fields

from forms.engineering.models import EngineeringFormDefinition

from shared.forms.engineering.form_2_12 import FORM_2_12 as CORE_DEFINITION

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

FORM_2_12 = EngineeringFormDefinition(
    **{field.name: getattr(CORE_DEFINITION, field.name) for field in fields(CORE_DEFINITION)},
    list_definition=build_standard_engineering_list_definition(
            new_button_text="新增桥梁调查",
        ),
    summary_export_definition=SummaryExportDefinition(
        sheet_name='桥梁调查汇总',
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
                header='设计流量',
                width=16,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='design_flow',
                ),
            ),
            SummaryColumnDefinition(
                header='建筑物等级',
                width=14,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='structure_grade',
                ),
            ),
            SummaryColumnDefinition(
                header='建成年月',
                width=14,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='build_date',
                ),
            ),
            SummaryColumnDefinition(
                header='加固改造年月',
                width=16,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='renovation_date',
                ),
            ),
            SummaryColumnDefinition(
                header='宽*跨',
                width=14,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='width_span',
                ),
            ),
            SummaryColumnDefinition(
                header='承载重量（吨）',
                width=16,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='load_capacity',
                ),
            ),
            SummaryColumnDefinition(
                header='结构形式',
                width=16,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='structure_form',
                ),
            ),
            SummaryColumnDefinition(
                header='钢筋混凝土强度',
                width=18,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='reinforced_concrete_strength',
                ),
            ),
            SummaryColumnDefinition(
                header='钢筋保护层厚度',
                width=16,
                binding=ValueBindingDefinition.single(
                    source='record_data',
                    key='cover_thickness',
                ),
            ),
        ),
    ),
)
