from forms.engineering.form_2_5 import (
    FORM_2_5,
)

from pages.components.generic_engineering_list_page import (
    GenericEngineeringListPage,
)

from services.tunnel_export import (
    export_tunnel_original_form,
)


class TunnelListPage(
    GenericEngineeringListPage,
):
    """附表2.5隧洞当前批次调查列表。"""

    DEFINITION = FORM_2_5

    ORIGINAL_EXPORTER = staticmethod(
        export_tunnel_original_form
    )

    EXPORT_FILENAME_PREFIX = (
        "附表2.5_隧洞工程状况调查表"
    )

    EXPORT_FALLBACK_ASSET_NAME = "隧洞"
