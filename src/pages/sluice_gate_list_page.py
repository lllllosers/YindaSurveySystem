from forms.engineering.form_2_2 import (
    FORM_2_2,
)

from pages.components.generic_engineering_list_page import (
    GenericEngineeringListPage,
)

from services.sluice_gate_export import (
    export_sluice_gate_original_form,
)


class SluiceGateListPage(
    GenericEngineeringListPage,
):
    """附表2.2水闸当前批次调查列表。"""

    DEFINITION = FORM_2_2

    ORIGINAL_EXPORTER = staticmethod(
        export_sluice_gate_original_form
    )

    EXPORT_FILENAME_PREFIX = (
        "附表2.2_水闸工程状况调查表"
    )

    EXPORT_FALLBACK_ASSET_NAME = "水闸"
