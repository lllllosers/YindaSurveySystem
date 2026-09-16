from forms.engineering.form_2_2 import (
    FORM_2_2,
)

from services.engineering_original_form_export import (
    export_engineering_original_form,
)
from services.engineering_summary_export import (
    export_engineering_summary,
)


def export_sluice_gate_summary(
    records,
    file_path,
):
    """附表2.2详细汇总兼容入口。"""

    return export_engineering_summary(
        FORM_2_2,
        records=records,
        file_path=file_path,
    )


def export_sluice_gate_original_form(
    survey_record_id,
    file_path,
):
    """附表2.2正式原表兼容入口。"""

    return export_engineering_original_form(
        FORM_2_2,
        survey_record_id=survey_record_id,
        file_path=file_path,
    )
