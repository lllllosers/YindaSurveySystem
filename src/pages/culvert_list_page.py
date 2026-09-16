from forms.engineering.form_2_6 import (
    FORM_2_6,
)

from pages.components.generic_engineering_list_page import (
    GenericEngineeringListPage,
)

from services.culvert_export import (
    export_culvert_original_form,
)


class CulvertListPage(
    GenericEngineeringListPage,
):
    """附表2.6涵洞（暗涵）当前批次调查列表。"""

    DEFINITION = FORM_2_6

    ORIGINAL_EXPORTER = staticmethod(
        export_culvert_original_form
    )

    EXPORT_FILENAME_PREFIX = (
        "附表2.6_涵洞（暗涵）工程状况调查表"
    )

    EXPORT_FALLBACK_ASSET_NAME = "涵洞（暗涵）"
