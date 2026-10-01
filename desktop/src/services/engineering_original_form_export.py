"""SQLite adapter for the shared formal Excel renderer."""

from database import get_app_root, get_engineering_asset_detail, get_inspection_results
from forms.engineering.persistence import get_engineering_record
from services.original_form_export_common import fill_original_form_ownership_header
from services.original_form_renderer import render_original_form


def _resolve_ownership_canal_id(record):
    for key in ("canal_id", "canal_unit_id"):
        try:
            value = record[key]
        except (KeyError, IndexError, TypeError):
            continue
        if value is not None:
            return value
    raise ValueError("调查记录缺少渠系归属信息。")


def export_engineering_original_form(definition, *, survey_record_id, file_path):
    if definition.original_form_export_definition is None:
        raise ValueError(f"{definition.form_code} 尚未配置 OriginalFormExportDefinition。")
    record = get_engineering_record(definition, survey_record_id=survey_record_id)
    if record is None:
        raise ValueError("没有找到需要导出的工程调查记录。")
    asset = get_engineering_asset_detail(record["engineering_asset_id"])
    if asset is None:
        raise ValueError("没有找到该调查记录对应的工程对象。")
    evaluations = {
        item["item_code"]: item["grade"]
        for item in get_inspection_results(survey_record_id)
    }
    render_original_form(
        definition,
        template_root=get_app_root() / "templates" / "excel",
        output=file_path,
        record=record,
        record_data=record["record_data"] or {},
        evaluation_map=evaluations,
        fill_header=lambda worksheet: fill_original_form_ownership_header(
            worksheet,
            asset=asset,
            canal_id=_resolve_ownership_canal_id(record),
            business_code=record["business_code"],
        ),
    )
    return {
        "file_path": file_path,
        "survey_record_id": survey_record_id,
        "business_code": record["business_code"],
        "asset_name": record["asset_name"],
    }
