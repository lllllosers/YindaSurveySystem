from forms.engineering.form_2_3 import (
    FORM_2_3,
)

from pages.components.generic_engineering_list_page import (
    GenericEngineeringListPage,
)

from services.aqueduct_export import (
    export_aqueduct_original_form,
)


class AqueductListPage(
    GenericEngineeringListPage,
):
    """附表2.3渡槽（座槽）当前批次调查列表。"""

    DEFINITION = FORM_2_3

    ORIGINAL_EXPORTER = staticmethod(
        export_aqueduct_original_form
    )

    EXPORT_FILENAME_PREFIX = (
        "附表2.3_渡槽（座槽）工程状况调查表"
    )

    EXPORT_FALLBACK_ASSET_NAME = "渡槽"
