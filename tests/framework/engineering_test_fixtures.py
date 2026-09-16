from forms.engineering.models import (
    EngineeringFormDefinition,
    FieldDefinition,
    FieldRowDefinition,
    FormSectionDefinition,
    PositionDefinition,
)

TEST_EVALUATION_ITEMS = (
    {
        "item_code": "test_item_1",
        "category": "测试类别",
        "item_name": "测试项目一",
        "standards": {
            "A": "A级",
            "B": "B级",
            "C": "C级",
            "D": "D级",
        },
    },
    {
        "item_code": "test_item_2",
        "category": "测试类别",
        "item_name": "测试项目二",
        "standards": {
            "A": "A级",
            "B": "B级",
            "C": "C级",
            "D": "D级",
        },
    },
)


TEST_POINT_DEFINITION = EngineeringFormDefinition(
    form_code="form_2_90",
    form_number="2.90",
    form_name="测试点工程调查表",
    asset_type="test_point",
    business_type_code="90",
    asset_name_field="asset_name",
    position=PositionDefinition.point(
        stake_field="stake",
        stake_value_key="stake_value",
    ),
    fields=(
        FieldDefinition(
            key="asset_name",
            label="工程名称",
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
            unit="m³/s",
        ),
        FieldDefinition(
            key="build_date",
            label="建成年月",
            input_type="month",
        ),
        FieldDefinition(
            key="renovation_date",
            label="加固改造年月",
            input_type="month",
            required=False,
        ),
    ),
    sections=(
        FormSectionDefinition(
            title="二、工程基本信息",
            rows=(
                FieldRowDefinition(("asset_name",)),
                FieldRowDefinition(("stake",)),
                FieldRowDefinition(("design_flow",)),
                FieldRowDefinition(("build_date",)),
                FieldRowDefinition(("renovation_date",)),
            ),
        ),
    ),
    evaluation_items=TEST_EVALUATION_ITEMS,
    evaluation_title="三、分项评价",
    conclusion_title="四、调查结论",
)


TEST_RANGE_DEFINITION = EngineeringFormDefinition(
    form_code="form_2_91",
    form_number="2.91",
    form_name="测试区间工程调查表",
    asset_type="test_range",
    business_type_code="91",
    asset_name_field="asset_name",
    position=PositionDefinition.range(
        start_stake_field="start_stake",
        start_stake_value_key=("start_stake_value"),
        end_stake_field="end_stake",
        end_stake_value_key=("end_stake_value"),
    ),
    fields=(
        FieldDefinition(
            key="asset_name",
            label="工程名称",
        ),
        FieldDefinition(
            key="start_stake",
            label="起始桩号",
            input_type="stake",
        ),
        FieldDefinition(
            key="end_stake",
            label="终止桩号",
            input_type="stake",
        ),
    ),
    sections=(
        FormSectionDefinition(
            title="二、工程基本信息",
            rows=(
                FieldRowDefinition(("asset_name",)),
                FieldRowDefinition(("start_stake",)),
                FieldRowDefinition(("end_stake",)),
            ),
        ),
    ),
    evaluation_items=TEST_EVALUATION_ITEMS,
)


def build_valid_point_payload():
    return {
        "asset_name": "测试点工程",
        "record_data": {
            "asset_name": "测试点工程",
            "stake": "CH1+000",
            "stake_value": 1000.0,
            "design_flow": 5.0,
            "build_date": "2026-01",
            "renovation_date": None,
        },
        "position": {
            "kind": "point",
            "single_stake_text": "CH1+000",
            "single_stake_value": 1000.0,
        },
        "inspection_results": [
            {
                "item_code": item["item_code"],
                "grade": "A",
            }
            for item in TEST_POINT_DEFINITION.evaluation_items
        ],
        "survey_date": "2026-09-15",
        "overall_grade": "A",
        "survey_comment": "测试调查意见",
    }


def build_valid_range_payload():
    return {
        "asset_name": "测试区间工程",
        "record_data": {
            "asset_name": "测试区间工程",
            "start_stake": "CH1+000",
            "start_stake_value": 1000.0,
            "end_stake": "CH2+000",
            "end_stake_value": 2000.0,
        },
        "position": {
            "kind": "range",
            "start_stake_text": "CH1+000",
            "start_stake_value": 1000.0,
            "end_stake_text": "CH2+000",
            "end_stake_value": 2000.0,
        },
        "inspection_results": [
            {
                "item_code": item["item_code"],
                "grade": "A",
            }
            for item in TEST_RANGE_DEFINITION.evaluation_items
        ],
        "survey_date": "2026-09-15",
        "overall_grade": "A",
        "survey_comment": "测试调查意见",
    }
