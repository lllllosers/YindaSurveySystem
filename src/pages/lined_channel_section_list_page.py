from forms.engineering.form_2_1 import (
    FORM_2_1,
)

from pages.components.generic_engineering_list_page import (
    GenericEngineeringListPage,
)

from services.lined_channel_export import (
    export_lined_channel_original_form,
)


class LinedChannelSectionListPage(
    GenericEngineeringListPage,
):
    """附表2.1防渗衬砌渠道渠段当前批次调查列表。"""

    DEFINITION = FORM_2_1

    ORIGINAL_EXPORTER = staticmethod(
        export_lined_channel_original_form
    )

    EXPORT_FILENAME_PREFIX = (
        "附表2.1_防渗衬砌渠道渠段工程状况调查表"
    )

    EXPORT_FALLBACK_ASSET_NAME = "渠道渠段"
