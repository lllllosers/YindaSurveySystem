from forms.engineering.models import (
    EngineeringFormDefinition,
    FieldDefinition,
    FieldRowDefinition,
    FormSectionDefinition,
    PositionDefinition,
)

from services.culvert_evaluation import (
    CULVERT_EVALUATION_ITEMS,
)

FORM_2_6 = EngineeringFormDefinition(
    # =========================================================
    # 表单身份
    # =========================================================
    form_code="form_2_6",
    form_number="2.6",
    form_name=("涵洞（暗涵）工程状况调查表"),
    asset_type="culvert",
    business_type_code="06",
    asset_name_field="asset_name",
    # =========================================================
    # 工程位置
    # =========================================================
    position=PositionDefinition.point(
        stake_field="stake",
        stake_value_key="stake_value",
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
            placeholder=("填写涵洞（暗涵）名称"),
        ),
        FieldDefinition(
            key="stake",
            label="桩号",
            input_type="stake",
            required=True,
            placeholder=("例如：CH12+350"),
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
            placeholder=("按原始资料填写"),
        ),
        FieldDefinition(
            key="build_date",
            label="建成年月",
            input_type="month",
            required=True,
        ),
        FieldDefinition(
            key="renovation_date",
            label="加固改造年月",
            input_type="month",
            required=False,
            placeholder=("例如：202109，可留空"),
        ),
        # 正式原表未明确标注单位。
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
            key="structure_form",
            label="结构形式",
            input_type="text",
            required=True,
            placeholder=("按原始资料填写"),
        ),
        FieldDefinition(
            key="main_structure_material",
            label="主构建筑材料",
            input_type="text",
            required=True,
            placeholder=("按原始资料填写"),
        ),
        FieldDefinition(
            key="concrete_strength",
            label="混凝土强度",
            input_type="text",
            required=True,
            placeholder=("例如：C30"),
        ),
        # 正式原表未明确标注单位。
        FieldDefinition(
            key="cover_thickness",
            label="钢筋保护层厚度",
            input_type="decimal",
            required=True,
        ),
        FieldDefinition(
            key="soil_cover_thickness",
            label="覆土厚度",
            input_type="decimal",
            required=True,
            unit="m",
        ),
        FieldDefinition(
            key="channel_width",
            label="渠宽",
            input_type="decimal",
            required=True,
            unit="m",
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
            title="二、工程基本信息",
            rows=(
                FieldRowDefinition(("asset_name",)),
                FieldRowDefinition(("stake",)),
                FieldRowDefinition(("design_flow",)),
                FieldRowDefinition(("structure_grade",)),
                FieldRowDefinition(("build_date",)),
                FieldRowDefinition(("renovation_date",)),
                FieldRowDefinition(("length",)),
                FieldRowDefinition(("increased_flow",)),
            ),
        ),
        FormSectionDefinition(
            title=("三、结构与断面参数"),
            rows=(
                FieldRowDefinition(("structure_form",)),
                FieldRowDefinition(("main_structure_material",)),
                FieldRowDefinition(("concrete_strength",)),
                FieldRowDefinition(("cover_thickness",)),
                FieldRowDefinition(("soil_cover_thickness",)),
                FieldRowDefinition(("channel_width",)),
                FieldRowDefinition(("channel_depth",)),
                FieldRowDefinition(("channel_bottom_elevation",)),
            ),
        ),
    ),
    # =========================================================
    # 分项评价
    # =========================================================
    evaluation_items=tuple(CULVERT_EVALUATION_ITEMS),
    grade_options=(
        "A",
        "B",
        "C",
        "D",
    ),
    evaluation_title="四、分项评价",
    conclusion_title="五、调查结论",
)
