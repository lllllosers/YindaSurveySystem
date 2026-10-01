"""Compare all fourteen real Excel outputs with the legacy renderer snapshot."""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from openpyxl import load_workbook
import pytest
from shared.forms.engineering.registry import get_engineering_form_definition
from shared.export.original_form_renderer import render_original_form
from shared.export.original_form_export_common import fill_original_form_ownership_header

BASELINE = json.loads((Path(__file__).parent / "fixtures/original_render_baseline.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("form_code", BASELINE)
def test_official_workbook_matches_legacy_output(form_code):
    definition = get_engineering_form_definition(form_code)
    fixture = BASELINE[form_code]
    output = BytesIO()
    render_original_form(
        definition, template_root=Path(__file__).resolve().parents[2] / "templates/excel",
        output=output, record=fixture["record"], record_data=fixture["record_data"],
        evaluation_map={item["item_code"]: definition.grade_options[i % len(definition.grade_options)] for i, item in enumerate(definition.evaluation_items)},
        fill_header=lambda worksheet: fill_original_form_ownership_header(
            worksheet, asset={"department_name": "一处", "office_name": "二所"},
            business_code="1-01-01-01-001", canal_lineage=[
                {"canal_level": "01", "name": "总干渠"},
                {"canal_level": "03", "name": "第一支渠"},
            ],
        ),
    )
    workbook = load_workbook(BytesIO(output.getvalue()))
    try:
        worksheet = workbook[definition.original_form_export_definition.sheet_name]
        state = {
            "cells": [[cell.coordinate, cell.value, cell.style_id, cell.number_format] for row in worksheet for cell in row if cell.value is not None],
            "merged": sorted(str(item) for item in worksheet.merged_cells.ranges),
            "print_area": worksheet.print_area,
            "orientation": worksheet.page_setup.orientation,
            "paper_size": worksheet.page_setup.paperSize,
            "fit_width": worksheet.page_setup.fitToWidth,
            "fit_height": worksheet.page_setup.fitToHeight,
            "grid": worksheet.sheet_view.showGridLines,
        }
        digest = sha256(json.dumps(state, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
        assert digest == fixture["sha256"]
    finally:
        workbook.close()
