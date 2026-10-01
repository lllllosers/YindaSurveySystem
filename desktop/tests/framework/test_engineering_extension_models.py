import sys
import unittest
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from forms.engineering.extension_models import (
    ListColumnDefinition,
    ListDefinition,
    OriginalFormCellBinding,
    OriginalFormConclusionBinding,
    OriginalFormEvaluationBinding,
    OriginalFormExportDefinition,
    OriginalFormPrintSettings,
    SummaryColumnDefinition,
    SummaryExportDefinition,
    ValueBindingDefinition,
)

from forms.engineering.models import (
    EngineeringFormDefinition,
    FieldDefinition,
    FieldRowDefinition,
    FormSectionDefinition,
    PositionDefinition,
)


TEST_EVALUATION_ITEMS = (
    {
        "item_code": "test_item",
        "category": "测试类别",
        "item_name": "测试项目",
        "standards": {
            "A": "A级",
            "B": "B级",
            "C": "C级",
            "D": "D级",
        },
    },
)


def _format_pair(
    first,
    second,
):
    return f"{first}×{second}"


def _build_definition(
    *,
    list_definition=None,
    summary_export_definition=None,
    original_form_export_definition=None,
):
    return EngineeringFormDefinition(
        form_code="form_2_99",
        form_number="2.99",
        form_name="扩展定义测试表",
        asset_type="extension_test",
        business_type_code="99",
        asset_name_field="asset_name",
        position=(
            PositionDefinition.point(
                stake_field="stake",
                stake_value_key="stake_value",
            )
        ),
        fields=(
            FieldDefinition(
                key="asset_name",
                label="名称",
            ),
            FieldDefinition(
                key="stake",
                label="桩号",
                input_type="stake",
            ),
            FieldDefinition(
                key="design_flow",
                label="设计流量",
                input_type="decimal",
            ),
            FieldDefinition(
                key="width",
                label="宽",
                input_type="decimal",
            ),
            FieldDefinition(
                key="height",
                label="高",
                input_type="decimal",
            ),
        ),
        sections=(
            FormSectionDefinition(
                title="二、工程基本信息",
                rows=(
                    FieldRowDefinition(("asset_name",)),
                    FieldRowDefinition(("stake",)),
                    FieldRowDefinition(("design_flow",)),
                    FieldRowDefinition(("width",)),
                    FieldRowDefinition(("height",)),
                ),
            ),
        ),
        evaluation_items=TEST_EVALUATION_ITEMS,
        list_definition=list_definition,
        summary_export_definition=(
            summary_export_definition
        ),
        original_form_export_definition=(
            original_form_export_definition
        ),
    )


def _valid_list_definition():
    return ListDefinition(
        new_button_text="新增测试调查",
        keyword_placeholder=(
            "业务编号 / 工程名称 / 桩号"
        ),
        position_label="桩号",
        columns=(
            ListColumnDefinition(
                header="业务编号",
                width=150,
                binding=(
                    ValueBindingDefinition.single(
                        source="query_record",
                        key="business_code",
                    )
                ),
            ),
            ListColumnDefinition(
                header="设计流量",
                width=100,
                binding=(
                    ValueBindingDefinition.single(
                        source="record_data",
                        key="design_flow",
                    )
                ),
                alignment="center",
            ),
        ),
    )


def _valid_summary_definition():
    return SummaryExportDefinition(
        sheet_name="测试调查汇总",
        columns=(
            SummaryColumnDefinition(
                header="业务编号",
                width=22,
                binding=(
                    ValueBindingDefinition.single(
                        source="record",
                        key="business_code",
                    )
                ),
            ),
            SummaryColumnDefinition(
                header="设计流量",
                width=16,
                binding=(
                    ValueBindingDefinition.single(
                        source="record_data",
                        key="design_flow",
                    )
                ),
                alignment="center",
            ),
            SummaryColumnDefinition(
                header="断面尺寸",
                width=18,
                binding=(
                    ValueBindingDefinition.composite(
                        source="record_data",
                        keys=(
                            "width",
                            "height",
                        ),
                        formatter=_format_pair,
                    )
                ),
                alignment="center",
            ),
        ),
    )


def _valid_original_definition(
    *,
    extra_field_bindings=(),
):
    return OriginalFormExportDefinition(
        template_filename=(
            "form_2_99_V1.xlsx"
        ),
        sheet_name="附表2.99",
        field_bindings=(
            OriginalFormCellBinding(
                cell="B5",
                binding=(
                    ValueBindingDefinition.single(
                        source="record",
                        key="asset_name",
                    )
                ),
            ),
            OriginalFormCellBinding(
                cell="J5",
                binding=(
                    ValueBindingDefinition.single(
                        source="record_data",
                        key="design_flow",
                    )
                ),
            ),
            *extra_field_bindings,
        ),
        evaluation_binding=(
            OriginalFormEvaluationBinding(
                column="E",
                start_row=10,
            )
        ),
        conclusion_binding=(
            OriginalFormConclusionBinding(
                survey_comment_cell="C20",
                overall_grade_cell="J20",
                surveyor_signatures_cell="B21",
                water_office_manager_signature_cell="D21",
                engineering_section_chief_signature_cell="F21",
                department_head_signature_cell="H21",
                survey_date_cell="J21",
            )
        ),
        print_settings=(
            OriginalFormPrintSettings(
                print_area="A1:J21",
            )
        ),
        output_filename_prefix=(
            "附表2.99_扩展定义测试表"
        ),
        fallback_asset_name="测试工程",
    )


class EngineeringExtensionModelsTestCase(
    unittest.TestCase,
):
    def test_default_list_keyword_sources_are_common_fields(
        self,
    ):
        definition = _valid_list_definition()

        self.assertEqual(
            tuple(
                binding.keys[0]
                for binding
                in definition.keyword_bindings
            ),
            (
                "business_code",
                "asset_name",
                "engineering_position",
            ),
        )

    def test_composite_binding_requires_formatter(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "多字段数据绑定必须配置 formatter",
        ):
            ValueBindingDefinition(
                source="record_data",
                keys=(
                    "width",
                    "height",
                ),
            )

    def test_list_definition_rejects_full_record_source(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "ListDefinition 只允许使用",
        ):
            ListDefinition(
                new_button_text="新增",
                keyword_placeholder="关键词",
                position_label="桩号",
                columns=(
                    ListColumnDefinition(
                        header="名称",
                        width=100,
                        binding=(
                            ValueBindingDefinition.single(
                                source="record",
                                key="asset_name",
                            )
                        ),
                    ),
                ),
            )

    def test_original_definition_rejects_query_record_source(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "正式原表字段绑定只允许使用",
        ):
            OriginalFormCellBinding(
                cell="B5",
                binding=(
                    ValueBindingDefinition.single(
                        source="query_record",
                        key="asset_name",
                    )
                ),
            )

    def test_engineering_form_can_compose_three_extension_definitions(
        self,
    ):
        list_definition = (
            _valid_list_definition()
        )
        summary_definition = (
            _valid_summary_definition()
        )
        original_definition = (
            _valid_original_definition()
        )

        definition = _build_definition(
            list_definition=list_definition,
            summary_export_definition=(
                summary_definition
            ),
            original_form_export_definition=(
                original_definition
            ),
        )

        self.assertIs(
            definition.list_definition,
            list_definition,
        )
        self.assertIs(
            definition.summary_export_definition,
            summary_definition,
        )
        self.assertIs(
            definition.original_form_export_definition,
            original_definition,
        )

    def test_record_data_binding_must_reference_defined_form_field(
        self,
    ):
        invalid_summary = SummaryExportDefinition(
            sheet_name="测试",
            columns=(
                SummaryColumnDefinition(
                    header="不存在字段",
                    width=16,
                    binding=(
                        ValueBindingDefinition.single(
                            source="record_data",
                            key="missing_field",
                        )
                    ),
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "扩展定义引用了不存在的 record_data 字段",
        ):
            _build_definition(
                summary_export_definition=(
                    invalid_summary
                )
            )

    def test_original_evaluation_cells_cannot_overlap_other_bindings(
        self,
    ):
        conflicting_binding = (
            OriginalFormCellBinding(
                cell="E10",
                binding=(
                    ValueBindingDefinition.single(
                        source="record_data",
                        key="width",
                    )
                ),
            )
        )

        original_definition = (
            _valid_original_definition(
                extra_field_bindings=(
                    conflicting_binding,
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "分项评价写入区域与其他正式原表绑定冲突",
        ):
            _build_definition(
                original_form_export_definition=(
                    original_definition
                )
            )


if __name__ == "__main__":
    unittest.main()
