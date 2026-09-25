from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.central_record import (
    CentralEngineeringAsset,
    CentralInspectionResult,
    CentralSurveyMedia,
    CentralSurveyRecord,
)
from app.services.master_data_service import get_snapshot


def _filters(
    *,
    project_uid: str | None,
    survey_batch_uid: str | None,
    form_code: str | None,
    organization_unit_uid: str | None,
    canal_unit_uid: str | None,
    search: str | None,
) -> list:
    filters = []
    if project_uid:
        filters.append(CentralSurveyRecord.project_uid == project_uid)
    if survey_batch_uid:
        filters.append(CentralSurveyRecord.survey_batch_uid == survey_batch_uid)
    if form_code:
        filters.append(CentralSurveyRecord.form_code == form_code)
    if organization_unit_uid:
        filters.append(CentralSurveyRecord.organization_unit_uid == organization_unit_uid)
    if canal_unit_uid:
        filters.append(CentralSurveyRecord.canal_unit_uid == canal_unit_uid)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                CentralEngineeringAsset.asset_name.ilike(pattern),
                CentralEngineeringAsset.business_code.ilike(pattern),
                CentralSurveyRecord.survey_record_uid.ilike(pattern),
            )
        )
    return filters


def list_records(
    db: Session,
    *,
    project_uid: str | None = None,
    survey_batch_uid: str | None = None,
    form_code: str | None = None,
    organization_unit_uid: str | None = None,
    canal_unit_uid: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[CentralSurveyRecord, CentralEngineeringAsset]], int]:
    filters = _filters(
        project_uid=project_uid,
        survey_batch_uid=survey_batch_uid,
        form_code=form_code,
        organization_unit_uid=organization_unit_uid,
        canal_unit_uid=canal_unit_uid,
        search=search,
    )
    joined = (
        select(CentralSurveyRecord, CentralEngineeringAsset)
        .join(
            CentralEngineeringAsset,
            CentralEngineeringAsset.engineering_asset_uid
            == CentralSurveyRecord.engineering_asset_uid,
        )
        .where(*filters)
    )
    total = int(
        db.scalar(
            select(func.count())
            .select_from(CentralSurveyRecord)
            .join(
                CentralEngineeringAsset,
                CentralEngineeringAsset.engineering_asset_uid
                == CentralSurveyRecord.engineering_asset_uid,
            )
            .where(*filters)
        )
        or 0
    )
    rows = list(
        db.execute(
            joined.order_by(
                CentralSurveyRecord.updated_at.desc(),
                CentralSurveyRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total


def get_record(
    db: Session,
    survey_record_uid: str,
) -> tuple[
    CentralSurveyRecord,
    CentralEngineeringAsset,
    list[CentralInspectionResult],
    list[CentralSurveyMedia],
] | None:
    pair = db.execute(
        select(CentralSurveyRecord, CentralEngineeringAsset)
        .join(
            CentralEngineeringAsset,
            CentralEngineeringAsset.engineering_asset_uid
            == CentralSurveyRecord.engineering_asset_uid,
        )
        .where(CentralSurveyRecord.survey_record_uid == survey_record_uid)
    ).one_or_none()
    if pair is None:
        return None
    record, asset = pair
    inspections = list(
        db.scalars(
            select(CentralInspectionResult)
            .where(CentralInspectionResult.survey_record_uid == survey_record_uid)
            .order_by(CentralInspectionResult.item_code)
        )
    )
    media = list(
        db.scalars(
            select(CentralSurveyMedia)
            .where(CentralSurveyMedia.survey_record_uid == survey_record_uid)
            .order_by(CentralSurveyMedia.id)
        )
    )
    return record, asset, inspections, media


def summary(db: Session) -> dict:
    snapshot = get_snapshot()
    organization_names = {
        item.stable_uid: item.name
        for item in [*snapshot.departments, *snapshot.offices]
    }
    canal_names = {item.stable_uid: item.name for item in snapshot.canals}

    def grouped(column) -> list[tuple[str, int]]:
        return [
            (str(key), int(count))
            for key, count in db.execute(
                select(column, func.count())
                .select_from(CentralSurveyRecord)
                .group_by(column)
                .order_by(func.count().desc(), column)
            ).all()
        ]

    return {
        "asset_count": int(db.scalar(select(func.count()).select_from(CentralEngineeringAsset)) or 0),
        "record_count": int(db.scalar(select(func.count()).select_from(CentralSurveyRecord)) or 0),
        "inspection_count": int(db.scalar(select(func.count()).select_from(CentralInspectionResult)) or 0),
        "media_count": int(db.scalar(select(func.count()).select_from(CentralSurveyMedia)) or 0),
        "by_form": [
            {"key": key, "name": key, "count": count}
            for key, count in grouped(CentralSurveyRecord.form_code)
        ],
        "by_organization": [
            {"key": key, "name": organization_names.get(key, key), "count": count}
            for key, count in grouped(CentralSurveyRecord.organization_unit_uid)
        ],
        "by_canal": [
            {"key": key, "name": canal_names.get(key, key), "count": count}
            for key, count in grouped(CentralSurveyRecord.canal_unit_uid)
        ],
    }
