from forms.engineering.form_2_3 import (
    FORM_2_3,
)

from services.engineering_original_form_export import (
    export_engineering_original_form,
)
from services.engineering_summary_export import (
    export_engineering_summary,
)


def export_aqueduct_summary(
    records,
    file_path,
):
    """
    附表2.3详细汇总导出的兼容入口。
    """

    return export_engineering_summary(
        FORM_2_3,
        records=records,
        file_path=file_path,
    )


def export_aqueduct_original_form(
    survey_record_id,
    file_path,
):
    """
    附表2.3正式原表导出的兼容入口。
    """

    return export_engineering_original_form(
        FORM_2_3,
        survey_record_id=survey_record_id,
        file_path=file_path,
    )
