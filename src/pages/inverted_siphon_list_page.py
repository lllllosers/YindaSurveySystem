from forms.engineering.form_2_4 import (
    FORM_2_4,
)

from pages.components.generic_engineering_list_page import (
    GenericEngineeringListPage,
)

from services.inverted_siphon_export import (
    export_inverted_siphon_original_form,
)


class InvertedSiphonListPage(
    GenericEngineeringListPage,
):
    """附表2.4倒虹吸当前批次调查列表。"""

    DEFINITION = FORM_2_4

    ORIGINAL_EXPORTER = staticmethod(
        export_inverted_siphon_original_form
    )

    EXPORT_FILENAME_PREFIX = (
        "附表2.4_倒虹吸工程状况调查表"
    )

    EXPORT_FALLBACK_ASSET_NAME = "倒虹吸"
