import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from forms.engineering.form_2_1 import (
    FORM_2_1,
)

from forms.engineering.form_2_2 import (
    FORM_2_2,
)

from forms.engineering.form_2_3 import (
    FORM_2_3,
)

from forms.engineering.form_2_4 import (
    FORM_2_4,
)

from services.aqueduct_evaluation import (
    AQUEDUCT_EVALUATION_ITEMS,
)

from services.inverted_siphon_evaluation import (
    INVERTED_SIPHON_EVALUATION_ITEMS,
)

from services.lined_channel_evaluation import (
    LINED_CHANNEL_EVALUATION_ITEMS,
)

from services.sluice_gate_evaluation import (
    SLUICE_GATE_EVALUATION_ITEMS,
)


class Forms21To24DefinitionTestCase(
    unittest.TestCase,
):

    def test_identity_contracts(
        self,
    ):
        expected = (
            (
                FORM_2_1,
                "form_2_1",
                "2.1",
                ("防渗衬砌渠道渠段" "工程状况调查表"),
                "lined_channel_section",
                "01",
            ),
            (
                FORM_2_2,
                "form_2_2",
                "2.2",
                "水闸工程状况调查表",
                "sluice_gate",
                "02",
            ),
            (
                FORM_2_3,
                "form_2_3",
                "2.3",
                ("渡槽（座槽）" "工程状况调查表"),
                "aqueduct",
                "03",
            ),
            (
                FORM_2_4,
                "form_2_4",
                "2.4",
                "倒虹吸工程状况调查表",
                "inverted_siphon",
                "04",
            ),
        )

        for (
            definition,
            form_code,
            form_number,
            form_name,
            asset_type,
            business_type_code,
        ) in expected:
            with self.subTest(form_code=form_code):
                self.assertEqual(
                    definition.form_code,
                    form_code,
                )

                self.assertEqual(
                    definition.form_number,
                    form_number,
                )

                self.assertEqual(
                    definition.form_name,
                    form_name,
                )

                self.assertEqual(
                    definition.asset_type,
                    asset_type,
                )

                self.assertEqual(
                    definition.business_type_code,
                    business_type_code,
                )

    def test_position_contracts(
        self,
    ):
        self.assertEqual(
            FORM_2_1.position.kind,
            "range",
        )

        self.assertEqual(
            FORM_2_1.position.start_stake_field,
            "start_stake",
        )

        self.assertEqual(
            FORM_2_1.position.end_stake_field,
            "end_stake",
        )

        for definition in (
            FORM_2_2,
            FORM_2_3,
            FORM_2_4,
        ):
            with self.subTest(form_code=definition.form_code):
                self.assertEqual(
                    definition.position.kind,
                    "range",
                )

                self.assertEqual(
                    definition.position.start_stake_field,
                    "start_stake",
                )

                self.assertEqual(
                    definition.position.end_stake_field,
                    "end_stake",
                )

    def test_asset_name_contracts(
        self,
    ):
        self.assertEqual(
            FORM_2_1.asset_name_field,
            "channel_name",
        )

        for definition in (
            FORM_2_2,
            FORM_2_3,
            FORM_2_4,
        ):
            self.assertEqual(
                definition.asset_name_field,
                "asset_name",
            )

    def test_only_renovation_date_is_optional(
        self,
    ):
        for definition in (
            FORM_2_1,
            FORM_2_2,
            FORM_2_3,
            FORM_2_4,
        ):
            with self.subTest(form_code=definition.form_code):
                optional_fields = {
                    field.key for field in definition.fields if not field.required
                }

                self.assertEqual(
                    optional_fields,
                    {
                        "renovation_date",
                    },
                )

    def test_form_2_1_fields(
        self,
    ):
        expected_keys = (
            "channel_name",
            "start_stake",
            "end_stake",
            "section_length",
            "build_date",
            "renovation_date",
            "longitudinal_slope",
            "design_flow",
            "channel_grade",
            "cross_section_form",
            "embankment_top_width",
            "inner_slope",
            "outer_slope",
            "increased_flow",
            "bed_soil",
            "lining_structure",
            "freeboard",
            "bottom_width",
            "water_conveyance_loss",
            "lining_material",
            "lining_thickness",
            "concrete_strength",
            "channel_depth",
            "channel_bottom_elevation",
        )

        self.assertEqual(
            tuple(field.key for field in FORM_2_1.fields),
            expected_keys,
        )

        self.assertEqual(
            FORM_2_1.field_map["longitudinal_slope"].input_type,
            "text",
        )

        self.assertEqual(
            FORM_2_1.field_map["channel_bottom_elevation"].input_type,
            "signed_decimal",
        )

    def test_form_2_2_fields(
        self,
    ):
        expected_keys = (
            "asset_name",
            "start_stake",
            "end_stake",
            "design_flow",
            "structure_grade",
            "build_date",
            "renovation_date",
            "increased_flow",
            "opening_count",
            "opening_width",
            "opening_height",
            "main_component_material",
            "concrete_strength",
            "reinforced_concrete_strength",
            "cover_thickness",
            "crack_width_limit",
        )

        self.assertEqual(
            tuple(field.key for field in FORM_2_2.fields),
            expected_keys,
        )

        self.assertEqual(
            FORM_2_2.field_map["opening_count"].input_type,
            "integer",
        )

        self.assertEqual(
            FORM_2_2.field_map["opening_count"].maximum,
            999999,
        )

    def test_form_2_3_fields_and_composite_row(
        self,
    ):
        expected_keys = (
            "asset_name",
            "start_stake",
            "end_stake",
            "design_flow",
            "structure_grade",
            "build_date",
            "renovation_date",
            "length",
            "increased_flow",
            "structure_form",
            "section_width",
            "section_height",
            "trough_body_structure",
            "trough_wall_thickness",
            "waterstop_form",
            "trough_bottom_elevation",
            "span_count",
            "lower_support_structure_form",
        )

        self.assertEqual(
            tuple(field.key for field in FORM_2_3.fields),
            expected_keys,
        )

        rows = FORM_2_3.sections[1].rows

        size_row = next(
            row
            for row in rows
            if row.field_keys
            == (
                "section_width",
                "section_height",
            )
        )

        self.assertEqual(
            size_row.label,
            "断面尺寸（宽×高）",
        )

        self.assertEqual(
            size_row.separator,
            "×",
        )

        self.assertEqual(
            FORM_2_3.evaluation_note,
            ("注：渡槽其它部位指进、出口" "渐变段、护栏等。"),
        )

    def test_form_2_4_fields(
        self,
    ):
        expected_keys = (
            "asset_name",
            "start_stake",
            "end_stake",
            "design_flow",
            "structure_grade",
            "build_date",
            "renovation_date",
            "length",
            "increased_flow",
            "structure_form",
            "section_size",
            "pipe_body_structure",
            "wall_thickness",
            "waterstop_form",
            "channel_bottom_elevation",
        )

        self.assertEqual(
            tuple(field.key for field in FORM_2_4.fields),
            expected_keys,
        )

        self.assertEqual(
            FORM_2_4.field_map["section_size"].input_type,
            "text",
        )

        self.assertEqual(
            FORM_2_4.field_map["channel_bottom_elevation"].input_type,
            "signed_decimal",
        )

    def test_evaluation_contracts(
        self,
    ):
        cases = (
            (
                FORM_2_1,
                LINED_CHANNEL_EVALUATION_ITEMS,
                12,
            ),
            (
                FORM_2_2,
                SLUICE_GATE_EVALUATION_ITEMS,
                14,
            ),
            (
                FORM_2_3,
                AQUEDUCT_EVALUATION_ITEMS,
                12,
            ),
            (
                FORM_2_4,
                INVERTED_SIPHON_EVALUATION_ITEMS,
                12,
            ),
        )

        for (
            definition,
            source_items,
            expected_count,
        ) in cases:
            with self.subTest(form_code=definition.form_code):
                self.assertEqual(
                    definition.evaluation_items,
                    tuple(source_items),
                )

                self.assertEqual(
                    len(definition.evaluation_items),
                    expected_count,
                )

                for item in definition.evaluation_items:
                    self.assertEqual(
                        set(item["standards"].keys()),
                        {
                            "A",
                            "B",
                            "C",
                            "D",
                        },
                    )

    def test_section_titles(
        self,
    ):
        self.assertEqual(
            tuple(section.title for section in FORM_2_1.sections),
            (
                "二、渠段基本信息",
                "三、断面与渠体参数",
                "四、衬砌及高程参数",
            ),
        )

        for definition in (
            FORM_2_2,
            FORM_2_3,
            FORM_2_4,
        ):
            self.assertEqual(
                definition.sections[0].title,
                "二、工程基本信息",
            )

        self.assertEqual(
            FORM_2_2.sections[1].title,
            "三、结构与材料参数",
        )

        self.assertEqual(
            FORM_2_3.sections[1].title,
            "三、结构参数",
        )

        self.assertEqual(
            FORM_2_4.sections[1].title,
            "三、结构参数",
        )


if __name__ == "__main__":
    unittest.main()
