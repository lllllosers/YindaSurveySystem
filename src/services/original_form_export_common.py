"""SQLite ownership adapter; shared rendering never queries a database."""
from shared.export.original_form_export_common import (
    display_value, strip_trailing_suffix,
    fill_original_form_ownership_header as _fill_header,
)


def fill_original_form_ownership_header(
    worksheet, *, asset, canal_id, business_code, canal_lineage=None,
):
    if canal_lineage is None:
        from database import get_canal_lineage
        canal_lineage = get_canal_lineage(canal_id)
    return _fill_header(
        worksheet, asset=asset, business_code=business_code,
        canal_lineage=canal_lineage,
    )
