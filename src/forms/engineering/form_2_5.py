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

from services.tunnel_evaluation import (
    TUNNEL_EVALUATION_ITEMS,
)


FORM_2_5 = EngineeringFormDefinition(
    # =========================================================
    # 表单身份
    # =========================================================
    form_code="form_2_5",
    form_number="2.5",
    form_name="隧洞工程状况调查表",
    asset_type="tunnel",
    business_type_code="05",
    asset_name_field="asset_name",

    # =========================================================
    # 工程位置
    # =========================================================
    position=PositionDefinition.range(
        start_stake_field="start_stake",
        start_stake_value_key="start_stake_value",
        end_stake_field="end_stake",
        end_stake_value_key="end_stake_value",
    ),

    # =========================================================
    # 字段
    # =========================================================
    fields=(
        # -----------------------------------------------------
        # 二、工程基本信息
        # -----------------------------------------------------
        FieldDefinition(
            key="asset_name",
            label="名称",
            input_type="text",
            required=True,
            placeholder="填写隧洞名称",
        ),
        FieldDefinition(
            key="start_stake",
            label="起始桩号",
            input_type="stake",
            required=True,
            placeholder="例如：CH20+000",
        ),
        FieldDefinition(
            key="end_stake",
            label="终止桩号",
            input_type="stake",
            required=True,
            placeholder="例如：CH21+200",
        ),
        FieldDefinition(
            key="design_flow",
            label="设计流量",
            input_type="decimal",
            required=True,
            unit="m³/s",
        ),
        FieldDefinition(
            key="structure_grade",
            label="建筑物等级",
            input_type="text",
            required=True,
            placeholder="按原始资料填写",
        ),
        FieldDefinition(
            key="build_date",
            label="建成年月",
            input_type="month",
            required=True,
            placeholder="直接输入6位数字，例如：201006",
        ),
        FieldDefinition(
            key="renovation_date",
            label="加固改造年月",
            input_type="month",
            required=False,
            placeholder="例如：202109，可留空",
        ),
        # 正式原表没有给长度标注单位。
        FieldDefinition(
            key="length",
            label="长度",
            input_type="decimal",
            required=True,
        ),
        FieldDefinition(
            key="increased_flow",
            label="加大流量",
            input_type="decimal",
            required=True,
            unit="m³/s",
        ),

        # -----------------------------------------------------
        # 三、结构与断面参数
        # -----------------------------------------------------
        FieldDefinition(
            key="lining_form",
            label="衬砌形式",
            input_type="text",
            required=True,
            placeholder="按原始资料填写",
        ),
        FieldDefinition(
            key="lining_thickness",
            label="衬砌厚度",
            input_type="decimal",
            required=True,
        ),
        FieldDefinition(
            key="concrete_strength",
            label="混凝土强度",
            input_type="text",
            required=True,
            placeholder="例如：C30",
        ),
        # 旧正式实现将该字段作为自由文本处理，
        # 本次迁移保持数据兼容，不擅自改为数值字段。
        FieldDefinition(
            key="inlet_outlet_bottom_elevation",
            label="进出口底部高程",
            input_type="text",
            required=True,
            placeholder="按原始资料填写",
        ),
        FieldDefinition(
            key="longitudinal_slope",
            label="纵坡",
            input_type="decimal",
            required=True,
            unit="n/1000",
        ),
        FieldDefinition(
            key="section_form",
            label="断面型式",
            input_type="text",
            required=True,
            placeholder="按原始资料填写",
        ),
        FieldDefinition(
            key="section_width",
            label="尺寸（宽）",
            input_type="decimal",
            required=True,
        ),
        FieldDefinition(
            key="section_height",
            label="尺寸（高）",
            input_type="decimal",
            required=True,
        ),
        FieldDefinition(
            key="cover_thickness",
            label="钢筋保护层厚度",
            input_type="decimal",
            required=True,
        ),
    ),

    # =========================================================
    # 页面布局
    # =========================================================
    sections=(
        FormSectionDefinition(
            title="二、工程基本信息",
            rows=(
                FieldRowDefinition(("asset_name",)),
                FieldRowDefinition(("start_stake",)),
                FieldRowDefinition(("end_stake",)),
                FieldRowDefinition(("design_flow",)),
                FieldRowDefinition(("structure_grade",)),
                FieldRowDefinition(("build_date",)),
                FieldRowDefinition(("renovation_date",)),
                FieldRowDefinition(("length",)),
                FieldRowDefinition(("increased_flow",)),
            ),
        ),
        FormSectionDefinition(
            title="三、结构与断面参数",
            rows=(
                FieldRowDefinition(("lining_form",)),
                FieldRowDefinition(("lining_thickness",)),
                FieldRowDefinition(("concrete_strength",)),
                FieldRowDefinition(
                    ("inlet_outlet_bottom_elevation",)
                ),
                FieldRowDefinition(("longitudinal_slope",)),
                FieldRowDefinition(("section_form",)),
                FieldRowDefinition(("section_width",)),
                FieldRowDefinition(("section_height",)),
                FieldRowDefinition(("cover_thickness",)),
            ),
        ),
    ),

    # =========================================================
    # 当前批次列表
    # =========================================================
    list_definition=(
        build_standard_engineering_list_definition(
            new_button_text='新增隧洞调查',
        )
    ),

    # =========================================================
    # 分项评价
    # =========================================================
    evaluation_items=tuple(
        TUNNEL_EVALUATION_ITEMS
    ),
    grade_options=(
        "A",
        "B",
        "C",
        "D",
    ),
    evaluation_title="四、分项评价",
    conclusion_title="五、调查结论",
)
