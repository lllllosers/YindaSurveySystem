from forms.engineering.models import (
    EngineeringFormDefinition,
    FieldDefinition,
    FieldRowDefinition,
    FormSectionDefinition,
    PositionDefinition,
)

from forms.engineering.list_definitions import (
    build_standard_engineering_list_definition,
)

from services.lined_channel_evaluation import (
    LINED_CHANNEL_EVALUATION_ITEMS,
)

FORM_2_1 = EngineeringFormDefinition(
    # =========================================================
    # 表单身份
    # =========================================================
    form_code="form_2_1",
    form_number="2.1",
    form_name=("防渗衬砌渠道渠段" "工程状况调查表"),
    asset_type=("lined_channel_section"),
    business_type_code="01",
    asset_name_field=("channel_name"),
    # =========================================================
    # 工程位置
    # =========================================================
    position=PositionDefinition.range(
        start_stake_field=("start_stake"),
        start_stake_value_key=("start_stake_value"),
        end_stake_field=("end_stake"),
        end_stake_value_key=("end_stake_value"),
    ),
    # =========================================================
    # 字段
    # =========================================================
    fields=(
        # -----------------------------------------------------
        # 二、渠段基本信息
        # -----------------------------------------------------
        FieldDefinition(
            key="channel_name",
            label="渠道名称",
            input_type="text",
            required=True,
            placeholder="填写渠道名称",
        ),
        FieldDefinition(
            key="start_stake",
            label="起始桩号",
            input_type="stake",
            required=True,
            placeholder="例如：CH12+000",
        ),
        FieldDefinition(
            key="end_stake",
            label="终止桩号",
            input_type="stake",
            required=True,
            placeholder="例如：CH13+250",
        ),
        FieldDefinition(
            key="section_length",
            label="渠段长度",
            input_type="decimal",
            required=True,
            unit="m",
            placeholder="例如：1250",
        ),
        FieldDefinition(
            key="build_date",
            label="建成年月",
            input_type="month",
            required=True,
            placeholder=("直接输入6位数字，" "例如：200806"),
        ),
        FieldDefinition(
            key="renovation_date",
            label="加固改造年月",
            input_type="month",
            required=False,
            placeholder=("直接输入6位数字，" "例如：202109，可留空"),
        ),
        FieldDefinition(
            key="longitudinal_slope",
            label="纵比降",
            input_type="text",
            required=True,
            placeholder=("按原始资料填写，" "例如 1/2000"),
        ),
        FieldDefinition(
            key="design_flow",
            label="设计流量",
            input_type="decimal",
            required=True,
            unit="m³/s",
        ),
        FieldDefinition(
            key="channel_grade",
            label="渠道等级",
            input_type="text",
            required=True,
            placeholder="按原始资料填写",
        ),
        FieldDefinition(
            key="cross_section_form",
            label="渠道断面形式",
            input_type="text",
            required=True,
            placeholder=("例如：梯形、矩形等"),
        ),
        # -----------------------------------------------------
        # 三、断面与渠体参数
        # -----------------------------------------------------
        FieldDefinition(
            key="embankment_top_width",
            label="堤顶宽度",
            input_type="decimal",
            required=True,
            unit="m",
        ),
        FieldDefinition(
            key="inner_slope",
            label="渠道边坡（内）",
            input_type="text",
            required=True,
            placeholder=("内边坡，按原始资料填写"),
        ),
        FieldDefinition(
            key="outer_slope",
            label="渠道边坡（外）",
            input_type="text",
            required=True,
            placeholder=("外边坡，按原始资料填写"),
        ),
        FieldDefinition(
            key="increased_flow",
            label="加大流量",
            input_type="decimal",
            required=True,
            unit="m³/s",
        ),
        FieldDefinition(
            key="bed_soil",
            label="渠床土质",
            input_type="text",
            required=True,
        ),
        FieldDefinition(
            key="lining_structure",
            label="防渗衬砌结构",
            input_type="text",
            required=True,
        ),
        FieldDefinition(
            key="freeboard",
            label="安全超高",
            input_type="decimal",
            required=True,
            unit="m",
        ),
        FieldDefinition(
            key="bottom_width",
            label="渠底宽度",
            input_type="decimal",
            required=True,
            unit="m",
        ),
        FieldDefinition(
            key="water_conveyance_loss",
            label="输水损失",
            input_type="decimal",
            required=True,
            unit="m³/km",
        ),
        # -----------------------------------------------------
        # 四、衬砌及高程参数
        # -----------------------------------------------------
        FieldDefinition(
            key="lining_material",
            label="衬砌材料",
            input_type="text",
            required=True,
        ),
        FieldDefinition(
            key="lining_thickness",
            label="衬砌厚度",
            input_type="decimal",
            required=True,
            unit="cm",
        ),
        FieldDefinition(
            key="concrete_strength",
            label="混凝土强度",
            input_type="text",
            required=True,
            placeholder="例如：C20、C25",
        ),
        FieldDefinition(
            key="channel_depth",
            label="渠深",
            input_type="decimal",
            required=True,
            unit="m",
        ),
        FieldDefinition(
            key="channel_bottom_elevation",
            label="渠底高程",
            input_type="signed_decimal",
            required=True,
            unit="m",
        ),
    ),
    # =========================================================
    # 页面布局
    # =========================================================
    sections=(
        FormSectionDefinition(
            title="二、渠段基本信息",
            rows=(
                FieldRowDefinition(("channel_name",)),
                FieldRowDefinition(("start_stake",)),
                FieldRowDefinition(("end_stake",)),
                FieldRowDefinition(("section_length",)),
                FieldRowDefinition(("build_date",)),
                FieldRowDefinition(("renovation_date",)),
                FieldRowDefinition(("longitudinal_slope",)),
                FieldRowDefinition(("design_flow",)),
                FieldRowDefinition(("channel_grade",)),
                FieldRowDefinition(("cross_section_form",)),
            ),
        ),
        FormSectionDefinition(
            title=("三、断面与渠体参数"),
            rows=(
                FieldRowDefinition(("embankment_top_width",)),
                FieldRowDefinition(("inner_slope",)),
                FieldRowDefinition(("outer_slope",)),
                FieldRowDefinition(("increased_flow",)),
                FieldRowDefinition(("bed_soil",)),
                FieldRowDefinition(("lining_structure",)),
                FieldRowDefinition(("freeboard",)),
                FieldRowDefinition(("bottom_width",)),
                FieldRowDefinition(("water_conveyance_loss",)),
            ),
        ),
        FormSectionDefinition(
            title=("四、衬砌及高程参数"),
            rows=(
                FieldRowDefinition(("lining_material",)),
                FieldRowDefinition(("lining_thickness",)),
                FieldRowDefinition(("concrete_strength",)),
                FieldRowDefinition(("channel_depth",)),
                FieldRowDefinition(("channel_bottom_elevation",)),
            ),
        ),
    ),
    # =========================================================
    # 当前批次列表
    # =========================================================
    list_definition=(
        build_standard_engineering_list_definition(
            new_button_text='新增渠道渠段调查',
        )
    ),
    evaluation_items=tuple(LINED_CHANNEL_EVALUATION_ITEMS),
    grade_options=(
        "A",
        "B",
        "C",
        "D",
    ),
    evaluation_title=("五、分项评价"),
    conclusion_title=("六、调查结论"),
)
