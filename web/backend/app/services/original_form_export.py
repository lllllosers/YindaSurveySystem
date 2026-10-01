"""Central PostgreSQL record adapter for the shared formal Excel renderer."""

from io import BytesIO
from pathlib import Path
import re

from app.services.master_data_service import REPOSITORY_ROOT, get_snapshot


from shared.forms.engineering.registry import get_engineering_form_definition
from shared.export.original_form_export_common import fill_original_form_ownership_header
from shared.export.original_form_renderer import render_original_form


def _ownership(snapshot, organization_uid: str, canal_uid: str):
    departments = {item.stable_uid: item for item in snapshot.departments}
    offices = {item.stable_uid: item for item in snapshot.offices}
    canals = {item.stable_uid: item for item in snapshot.canals}
    canal_by_key = {item.master_key: item for item in snapshot.canals}

    office = offices.get(organization_uid)
    department = departments.get(organization_uid)
    if office is not None:
        department_name = office.parent_name
        office_name = office.name
    elif department is not None:
        department_name = department.name
        office_name = ""
    else:
        raise ValueError("正式记录的管理单位不在中央基础资料中。")

    lineage = []
    current = canals.get(canal_uid)
    seen = set()
    while current is not None:
        if current.master_key in seen:
            raise ValueError("中央渠道层级存在循环。")
        seen.add(current.master_key)
        lineage.append({"name": current.name, "canal_level": current.canal_level})
        current = canal_by_key.get(current.parent_master_key)
    if not lineage:
        raise ValueError("正式记录的渠道不在中央基础资料中。")
    return {"department_name": department_name, "office_name": office_name}, list(reversed(lineage))


def export_central_original_form(record, asset, inspections) -> tuple[bytes, str]:
    definition = get_engineering_form_definition(record.form_code)
    if definition is None or definition.original_form_export_definition is None:
        raise ValueError("该调查表尚未配置正式原表导出。")
    snapshot = get_snapshot()
    ownership, lineage = _ownership(snapshot, record.organization_unit_uid, record.canal_unit_uid)
    payload = record.payload_json if isinstance(record.payload_json, dict) else {}
    record_data = payload.get("record_data")
    if not isinstance(record_data, dict) or not record_data:
        raise ValueError("正式记录缺少调查数据，无法导出原表。")
    asset_payload = asset.payload_json if isinstance(asset.payload_json, dict) else {}
    values = {
        **asset_payload,
        **payload,
        "business_code": asset.business_code or payload.get("business_code") or "",
        "asset_name": asset.asset_name or "",
        "organization_unit_uid": record.organization_unit_uid,
        "canal_unit_uid": record.canal_unit_uid,
        "start_stake_text": asset_payload.get("start_stake_text") or record_data.get("start_stake") or "",
        "end_stake_text": asset_payload.get("end_stake_text") or record_data.get("end_stake") or "",
    }
    grades = {
        item.item_code: item.payload_json.get("grade")
        for item in inspections
        if isinstance(item.payload_json, dict)
    }
    output = BytesIO()
    render_original_form(
        definition,
        template_root=Path(REPOSITORY_ROOT) / "templates" / "excel",
        output=output,
        record=values,
        record_data=record_data,
        evaluation_map=grades,
        fill_header=lambda worksheet: fill_original_form_ownership_header(
            worksheet,
            asset=ownership,
            business_code=values["business_code"],
            canal_lineage=lineage,
        ),
    )
    label = re.sub(r'[\\/:*?"<>|\r\n]+', "_", str(values["business_code"] or record.survey_record_uid))[:100]
    filename = f"{definition.display_name}-{label}.xlsx"
    return output.getvalue(), filename
