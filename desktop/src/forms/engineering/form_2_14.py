from dataclasses import fields

from forms.engineering.models import EngineeringFormDefinition

from shared.forms.engineering.form_2_14 import FORM_2_14 as CORE_DEFINITION

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

FORM_2_14 = EngineeringFormDefinition(
    **{field.name: getattr(CORE_DEFINITION, field.name) for field in fields(CORE_DEFINITION)},
    list_definition=build_standard_engineering_list_definition(
            new_button_text='新增沟段调查',
        ),
    summary_export_definition=SummaryExportDefinition(
        sheet_name='沟段调查汇总',
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
                header='沟道宽度',
                width=14,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='ditch_width',
                ),
            ),
            SummaryColumnDefinition(
                header='有无防洪设施',
                width=14,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='has_flood_control_facility',
                ),
            ),
            SummaryColumnDefinition(
                header='防洪设施类型',
                width=18,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='flood_control_facility_type',
                ),
            ),
            SummaryColumnDefinition(
                header='防洪设施建成时间',
                width=18,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='flood_control_build_time',
                ),
            ),
            SummaryColumnDefinition(
                header='防洪设施改造时间',
                width=18,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='flood_control_renovation_time',
                ),
            ),
            SummaryColumnDefinition(
                header='防洪能力',
                width=18,
                binding=ValueBindingDefinition.single(
                    source="record_data",
                    key='flood_control_capacity',
                ),
            ),
        ),
    ),
)
