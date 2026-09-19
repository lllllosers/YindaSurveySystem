from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import database

from services.survey_result_package_reader import (
    load_survey_result_package,
)


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


@dataclass(frozen=True)
class SurveyResultPreflightIssue:
    severity: str
    code: str
    message: str
    entity_uid: str = ""


@dataclass(frozen=True)
class SurveyResultImportPreflight:
    package_path: Path
    package_uid: str
    result_uid: str
    project_uid: str
    survey_batch_uid: str

    new_assets: int
    existing_assets: int

    new_records: int
    existing_records: int

    new_inspections: int
    existing_inspections: int

    new_media: int
    existing_media: int

    issues: tuple[SurveyResultPreflightIssue, ...]

    @property
    def error_count(self):
        return sum(
            1
            for item in self.issues
            if item.severity == SEVERITY_ERROR
        )

    @property
    def warning_count(self):
        return sum(
            1
            for item in self.issues
            if item.severity == SEVERITY_WARNING
        )

    @property
    def can_import(self):
        return self.error_count == 0

    @property
    def has_new_data(self):
        return any(
            (
                self.new_assets,
                self.new_records,
                self.new_inspections,
                self.new_media,
            )
        )

    def format_text(self):
        lines = [
            f"成果包：{self.package_path}",
            (
                "预检结果："
                f"{self.error_count} 个错误，"
                f"{self.warning_count} 个警告"
            ),
            (
                "工程对象："
                f"新增 {self.new_assets}，"
                f"已存在 {self.existing_assets}"
            ),
            (
                "调查记录："
                f"新增 {self.new_records}，"
                f"已存在 {self.existing_records}"
            ),
            (
                "分项评价："
                f"新增 {self.new_inspections}，"
                f"已存在 {self.existing_inspections}"
            ),
            (
                "影像："
                f"新增 {self.new_media}，"
                f"已存在 {self.existing_media}"
            ),
        ]

        if not self.issues:
            lines.append(
                "未发现目标数据库冲突。"
            )
        else:
            label = {
                SEVERITY_ERROR: "错误",
                SEVERITY_WARNING: "警告",
                SEVERITY_INFO: "提示",
            }

            for item in self.issues:
                suffix = (
                    f" [{item.entity_uid}]"
                    if item.entity_uid
                    else ""
                )
                lines.append(
                    f"[{label.get(item.severity, item.severity)}] "
                    f"{item.code}：{item.message}{suffix}"
                )

        return "\n".join(lines)


def _clean_text(value):
    return str(
        value or ""
    ).strip()


def _optional_text(value):
    value = _clean_text(
        value
    )
    return value or None


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def _append(
    issues,
    severity,
    code,
    message,
    *,
    entity_uid="",
):
    issues.append(
        SurveyResultPreflightIssue(
            severity=severity,
            code=code,
            message=message,
            entity_uid=(
                _clean_text(
                    entity_uid
                )
            ),
        )
    )


def _lookup_project(
    connection,
    project_uid,
):
    return connection.execute(
        """
        SELECT
            id,
            project_uid,
            name,
            short_name,
            status
        FROM projects
        WHERE project_uid = ?
        """,
        (
            project_uid,
        ),
    ).fetchone()


def _lookup_batch(
    connection,
    survey_batch_uid,
):
    return connection.execute(
        """
        SELECT
            id,
            survey_batch_uid,
            project_id,
            batch_name,
            batch_code,
            start_date,
            end_date,
            status
        FROM survey_batches
        WHERE survey_batch_uid = ?
        """,
        (
            survey_batch_uid,
        ),
    ).fetchone()


def _lookup_organization(
    connection,
    organization_uid,
):
    return connection.execute(
        """
        SELECT
            id,
            organization_unit_uid,
            name,
            status
        FROM organization_units
        WHERE organization_unit_uid = ?
        """,
        (
            organization_uid,
        ),
    ).fetchone()


def _lookup_canal(
    connection,
    canal_uid,
):
    return connection.execute(
        """
        SELECT
            id,
            canal_unit_uid,
            name,
            status
        FROM canal_units
        WHERE canal_unit_uid = ?
        """,
        (
            canal_uid,
        ),
    ).fetchone()



def _load_issued_task_authority(
    connection,
    task_uid,
):
    row = connection.execute(
        """
        SELECT
            id,
            task_uid,
            project_uid,
            survey_batch_uid,
            organization_unit_uid
        FROM survey_task_issues
        WHERE task_uid = ?
        LIMIT 1
        """,
        (
            task_uid,
        ),
    ).fetchone()

    return _row_to_dict(
        row
    )


def _load_issued_scope_authority(
    connection,
    task_issue_id,
    management_scope_uid,
):
    row = connection.execute(
        """
        SELECT
            management_scope_uid,
            canal_unit_uid,
            organization_unit_uid,
            range_mode,
            start_stake_text,
            start_stake_value,
            end_stake_text,
            end_stake_value,
            source_scope_status
        FROM survey_task_issue_scopes
        WHERE task_issue_id = ?
          AND management_scope_uid = ?
        LIMIT 1
        """,
        (
            task_issue_id,
            management_scope_uid,
        ),
    ).fetchone()

    return _row_to_dict(
        row
    )


def _load_current_management_scope(
    connection,
    management_scope_uid,
):
    row = connection.execute(
        """
        SELECT
            cms.management_scope_uid,
            cu.canal_unit_uid,
            ou.organization_unit_uid,
            cms.range_mode,
            cms.start_stake_text,
            cms.start_stake_value,
            cms.end_stake_text,
            cms.end_stake_value,
            cms.status
                AS source_scope_status
        FROM canal_management_scopes AS cms
        JOIN canal_units AS cu
          ON cu.id = cms.canal_unit_id
        JOIN organization_units AS ou
          ON ou.id = cms.organization_unit_id
        WHERE cms.management_scope_uid = ?
        LIMIT 1
        """,
        (
            management_scope_uid,
        ),
    ).fetchone()

    return _row_to_dict(
        row
    )


def _scope_authority_signature(
    item,
):
    return {
        "management_scope_uid": (
            _clean_text(
                item.get(
                    "management_scope_uid"
                )
            )
        ),
        "canal_unit_uid": (
            _clean_text(
                item.get(
                    "canal_unit_uid"
                )
            )
        ),
        "organization_unit_uid": (
            _clean_text(
                item.get(
                    "organization_unit_uid"
                )
            )
        ),
        "range_mode": (
            _clean_text(
                item.get(
                    "range_mode"
                )
            )
        ),
        "start_stake_text": (
            _optional_text(
                item.get(
                    "start_stake_text"
                )
            )
        ),
        "start_stake_value": (
            item.get(
                "start_stake_value"
            )
        ),
        "end_stake_text": (
            _optional_text(
                item.get(
                    "end_stake_text"
                )
            )
        ),
        "end_stake_value": (
            item.get(
                "end_stake_value"
            )
        ),
        "source_scope_status": (
            _clean_text(
                item.get(
                    "source_scope_status"
                )
            )
        ),
    }

def _lookup_form_version(
    connection,
    form_code,
    version_code,
):
    return connection.execute(
        """
        SELECT
            fv.id,
            fd.form_code,
            fv.version_code
        FROM form_definitions AS fd
        JOIN form_versions AS fv
          ON fv.form_definition_id = fd.id
        WHERE fd.form_code = ?
          AND fv.version_code = ?
        """,
        (
            form_code,
            version_code,
        ),
    ).fetchone()


def _load_local_asset(
    connection,
    engineering_asset_uid,
):
    row = connection.execute(
        """
        SELECT
            ea.id,
            ea.engineering_asset_uid,
            p.project_uid,
            ea.asset_name,
            ea.asset_type,
            ou.organization_unit_uid,
            cu.canal_unit_uid,
            ea.business_code,
            ea.code_scheme_version,
            ea.single_stake_text,
            ea.single_stake_value,
            ea.start_stake_text,
            ea.start_stake_value,
            ea.end_stake_text,
            ea.end_stake_value,
            fsb.survey_batch_uid
                AS first_survey_batch_uid,
            ea.status,
            ea.notes
        FROM engineering_assets AS ea
        JOIN projects AS p
          ON p.id = ea.project_id
        JOIN organization_units AS ou
          ON ou.id = ea.organization_unit_id
        JOIN canal_units AS cu
          ON cu.id = ea.canal_unit_id
        LEFT JOIN survey_batches AS fsb
          ON fsb.id = ea.first_survey_batch_id
        WHERE ea.engineering_asset_uid = ?
        """,
        (
            engineering_asset_uid,
        ),
    ).fetchone()

    return _row_to_dict(
        row
    )


def _load_local_asset_by_business_code(
    connection,
    project_id,
    business_code,
):
    row = connection.execute(
        """
        SELECT
            id,
            engineering_asset_uid,
            canal_unit_id,
            business_code
        FROM engineering_assets
        WHERE project_id = ?
          AND business_code = ?
        """,
        (
            project_id,
            business_code,
        ),
    ).fetchone()

    return _row_to_dict(
        row
    )


def _asset_signature(item):
    return {
        "project_uid": (
            _clean_text(
                item.get(
                    "project_uid"
                )
            )
        ),
        "asset_name": (
            _clean_text(
                item.get(
                    "asset_name"
                )
            )
        ),
        "asset_type": (
            _clean_text(
                item.get(
                    "asset_type"
                )
            )
        ),
        "organization_unit_uid": (
            _clean_text(
                item.get(
                    "organization_unit_uid"
                )
            )
        ),
        "canal_unit_uid": (
            _clean_text(
                item.get(
                    "canal_unit_uid"
                )
            )
        ),
        "business_code": (
            _clean_text(
                item.get(
                    "business_code"
                )
            )
        ),
        "code_scheme_version": (
            _optional_text(
                item.get(
                    "code_scheme_version"
                )
            )
        ),
        "single_stake_text": (
            _optional_text(
                item.get(
                    "single_stake_text"
                )
            )
        ),
        "single_stake_value": (
            item.get(
                "single_stake_value"
            )
        ),
        "start_stake_text": (
            _optional_text(
                item.get(
                    "start_stake_text"
                )
            )
        ),
        "start_stake_value": (
            item.get(
                "start_stake_value"
            )
        ),
        "end_stake_text": (
            _optional_text(
                item.get(
                    "end_stake_text"
                )
            )
        ),
        "end_stake_value": (
            item.get(
                "end_stake_value"
            )
        ),
        "first_survey_batch_uid": (
            _optional_text(
                item.get(
                    "first_survey_batch_uid"
                )
            )
        ),
        "status": (
            _clean_text(
                item.get(
                    "status"
                )
            )
        ),
        "notes": (
            _optional_text(
                item.get(
                    "notes"
                )
            )
        ),
    }


def _load_local_record(
    connection,
    survey_record_uid,
):
    row = connection.execute(
        """
        SELECT
            sr.id,
            sr.survey_record_uid,
            sr.source_task_uid,
            sr.source_management_scope_uid,
            p.project_uid,
            sb.survey_batch_uid,
            fd.form_code,
            fv.version_code,
            sr.record_type,
            ou.organization_unit_uid,
            cu.canal_unit_uid,
            ea.engineering_asset_uid,
            sr.business_code,
            sr.survey_date,
            sr.overall_grade,
            sr.survey_comment,
            sr.surveyor_signatures,
            sr.water_office_manager_signature,
            sr.engineering_section_chief_signature,
            sr.department_head_signature,
            sr.record_status,
            sr.record_data_json,
            sr.void_reason
        FROM survey_records AS sr
        JOIN projects AS p
          ON p.id = sr.project_id
        JOIN survey_batches AS sb
          ON sb.id = sr.survey_batch_id
        JOIN form_versions AS fv
          ON fv.id = sr.form_version_id
        JOIN form_definitions AS fd
          ON fd.id = fv.form_definition_id
        LEFT JOIN organization_units AS ou
          ON ou.id = sr.organization_unit_id
        LEFT JOIN canal_units AS cu
          ON cu.id = sr.canal_unit_id
        LEFT JOIN engineering_assets AS ea
          ON ea.id = sr.engineering_asset_id
        WHERE sr.survey_record_uid = ?
        """,
        (
            survey_record_uid,
        ),
    ).fetchone()

    if row is None:
        return None

    result = dict(
        row
    )

    try:
        result[
            "record_data"
        ] = json.loads(
            result.get(
                "record_data_json"
            )
            or "{}"
        )
    except json.JSONDecodeError:
        result[
            "record_data"
        ] = {
            "__invalid_local_json__": (
                result.get(
                    "record_data_json"
                )
            )
        }

    return result


def _record_signature(item):
    form = (
        item.get(
            "form"
        )
        if isinstance(
            item.get(
                "form"
            ),
            dict,
        )
        else {}
    )

    return {
        "source_task_uid": (
            _optional_text(
                item.get(
                    "source_task_uid"
                )
            )
        ),
        "source_management_scope_uid": (
            _optional_text(
                item.get(
                    "source_management_scope_uid"
                )
            )
        ),
        "project_uid": (
            _clean_text(
                item.get(
                    "project_uid"
                )
            )
        ),
        "survey_batch_uid": (
            _clean_text(
                item.get(
                    "survey_batch_uid"
                )
            )
        ),
        "form_code": (
            _clean_text(
                form.get(
                    "form_code"
                )
                or item.get(
                    "form_code"
                )
            )
        ),
        "version_code": (
            _clean_text(
                form.get(
                    "version_code"
                )
                or item.get(
                    "version_code"
                )
            )
        ),
        "record_type": (
            _clean_text(
                item.get(
                    "record_type"
                )
            )
        ),
        "organization_unit_uid": (
            _clean_text(
                item.get(
                    "organization_unit_uid"
                )
            )
        ),
        "canal_unit_uid": (
            _clean_text(
                item.get(
                    "canal_unit_uid"
                )
            )
        ),
        "engineering_asset_uid": (
            _clean_text(
                item.get(
                    "engineering_asset_uid"
                )
            )
        ),
        "business_code": (
            _clean_text(
                item.get(
                    "business_code"
                )
            )
        ),
        "survey_date": (
            _optional_text(
                item.get(
                    "survey_date"
                )
            )
        ),
        "overall_grade": (
            _optional_text(
                item.get(
                    "overall_grade"
                )
            )
        ),
        "survey_comment": (
            _optional_text(
                item.get(
                    "survey_comment"
                )
            )
        ),
        "surveyor_signatures": (
            _optional_text(item.get("surveyor_signatures"))
        ),
        "water_office_manager_signature": (
            _optional_text(item.get("water_office_manager_signature"))
        ),
        "engineering_section_chief_signature": (
            _optional_text(item.get("engineering_section_chief_signature"))
        ),
        "department_head_signature": (
            _optional_text(item.get("department_head_signature"))
        ),
        "record_status": (
            _clean_text(
                item.get(
                    "record_status"
                )
            )
        ),
        "record_data": (
            item.get(
                "record_data"
            )
            or {}
        ),
        "void_reason": (
            _optional_text(
                item.get(
                    "void_reason"
                )
            )
        ),
    }


def _inspection_signature(item):
    return {
        "category": (
            _optional_text(
                item.get(
                    "category"
                )
            )
        ),
        "item_name": (
            _optional_text(
                item.get(
                    "item_name"
                )
            )
        ),
        "grade": (
            _optional_text(
                item.get(
                    "grade"
                )
            )
        ),
        "description": (
            _optional_text(
                item.get(
                    "description"
                )
            )
        ),
        "remark": (
            _optional_text(
                item.get(
                    "remark"
                )
            )
        ),
    }


def _load_local_inspection(
    connection,
    survey_record_uid,
    item_code,
):
    row = connection.execute(
        """
        SELECT
            ir.category,
            ir.item_name,
            ir.grade,
            ir.description,
            ir.remark
        FROM inspection_results AS ir
        JOIN survey_records AS sr
          ON sr.id = ir.survey_record_id
        WHERE sr.survey_record_uid = ?
          AND ir.item_code = ?
        """,
        (
            survey_record_uid,
            item_code,
        ),
    ).fetchone()

    return _row_to_dict(
        row
    )


def _load_local_media(
    connection,
    media_uid,
):
    row = connection.execute(
        """
        SELECT
            sm.media_uid,
            sr.survey_record_uid,
            sm.media_kind,
            sm.media_role,
            sm.item_code,
            sm.part_name,
            sm.sequence_no,
            sm.original_filename,
            sm.file_sha256,
            sm.file_size,
            sm.captured_at,
            sm.notes
        FROM survey_media AS sm
        JOIN survey_records AS sr
          ON sr.id = sm.survey_record_id
        WHERE sm.media_uid = ?
        """,
        (
            media_uid,
        ),
    ).fetchone()

    return _row_to_dict(
        row
    )


def _media_signature(item):
    return {
        "survey_record_uid": (
            _clean_text(
                item.get(
                    "survey_record_uid"
                )
            )
        ),
        "media_kind": (
            _optional_text(
                item.get(
                    "media_kind"
                )
            )
        ),
        "media_role": (
            _optional_text(
                item.get(
                    "media_role"
                )
            )
        ),
        "item_code": (
            _optional_text(
                item.get(
                    "item_code"
                )
            )
        ),
        "part_name": (
            _optional_text(
                item.get(
                    "part_name"
                )
            )
        ),
        "sequence_no": (
            int(
                item.get(
                    "sequence_no"
                )
                or 0
            )
        ),
        "original_filename": (
            _clean_text(
                item.get(
                    "original_filename"
                )
            )
        ),
        "file_sha256": (
            _clean_text(
                item.get(
                    "file_sha256"
                )
            ).lower()
        ),
        "file_size": (
            int(
                item.get(
                    "file_size"
                )
                or 0
            )
        ),
        "captured_at": (
            _optional_text(
                item.get(
                    "captured_at"
                )
            )
        ),
        "notes": (
            _optional_text(
                item.get(
                    "notes"
                )
            )
        ),
    }


def preflight_survey_result_import(
    package_path,
):
    """
    对 .ydresult 做目标数据库预检。

    只读：
    - 不创建项目/批次；
    - 不插入工程对象；
    - 不插入调查记录；
    - 不复制影像；
    - 不写导入日志。

    Stage 12.5 只回答：
    “这个成果包如果导入当前数据库，会发生什么？”
    """

    package_path = Path(
        package_path
    )

    contents = (
        load_survey_result_package(
            package_path
        )
    )

    manifest = (
        contents.manifest
        or {}
    )
    result = (
        contents.result
        or {}
    )

    project = (
        result.get(
            "project"
        )
        if isinstance(
            result.get(
                "project"
            ),
            dict,
        )
        else {}
    )

    batch = (
        result.get(
            "survey_batch"
        )
        if isinstance(
            result.get(
                "survey_batch"
            ),
            dict,
        )
        else {}
    )

    package_uid = _clean_text(
        manifest.get(
            "package_uid"
        )
    )
    result_uid = _clean_text(
        result.get(
            "result_uid"
        )
    )
    project_uid = _clean_text(
        project.get(
            "project_uid"
        )
    )
    survey_batch_uid = _clean_text(
        batch.get(
            "survey_batch_uid"
        )
    )

    issues = []

    new_assets = 0
    existing_assets = 0

    new_records = 0
    existing_records = 0

    new_inspections = 0
    existing_inspections = 0

    new_media = 0
    existing_media = 0

    with database.get_connection() as connection:
        target_project = (
            _lookup_project(
                connection,
                project_uid,
            )
        )

        if target_project is None:
            _append(
                issues,
                SEVERITY_ERROR,
                "TARGET_PROJECT_MISSING",
                (
                    "当前数据库不存在成果包对应的项目。"
                    "成果接收阶段不应自动猜测或新建项目。"
                ),
                entity_uid=project_uid,
            )

            project_id = None

        else:
            project_id = int(
                target_project[
                    "id"
                ]
            )

        target_batch = (
            _lookup_batch(
                connection,
                survey_batch_uid,
            )
        )

        if target_batch is None:
            _append(
                issues,
                SEVERITY_ERROR,
                "TARGET_BATCH_MISSING",
                (
                    "当前数据库不存在成果包对应的调查批次。"
                    "请确认该数据库确实是此任务的上级汇总库。"
                ),
                entity_uid=(
                    survey_batch_uid
                ),
            )

        elif (
            project_id is not None
            and int(
                target_batch[
                    "project_id"
                ]
            )
            != project_id
        ):
            _append(
                issues,
                SEVERITY_ERROR,
                "TARGET_BATCH_PROJECT_MISMATCH",
                (
                    "目标调查批次存在，但不属于成果包对应项目。"
                ),
                entity_uid=(
                    survey_batch_uid
                ),
            )

        # -----------------------------------------------------
        # 先验证所有记录使用的表单、组织机构和渠系是否存在。
        # -----------------------------------------------------

        checked_forms = set()
        checked_orgs = set()
        checked_canals = set()

        for record in contents.survey_records:
            form = (
                record.get(
                    "form"
                )
                if isinstance(
                    record.get(
                        "form"
                    ),
                    dict,
                )
                else {}
            )

            form_key = (
                _clean_text(
                    form.get(
                        "form_code"
                    )
                ),
                _clean_text(
                    form.get(
                        "version_code"
                    )
                ),
            )

            if (
                form_key
                not in checked_forms
            ):
                checked_forms.add(
                    form_key
                )

                if (
                    _lookup_form_version(
                        connection,
                        form_key[0],
                        form_key[1],
                    )
                    is None
                ):
                    _append(
                        issues,
                        SEVERITY_ERROR,
                        "TARGET_FORM_VERSION_MISSING",
                        (
                            "当前数据库缺少成果记录使用的"
                            f"表单版本 {form_key[0]} / {form_key[1]}。"
                        ),
                    )

            org_uid = _clean_text(
                record.get(
                    "organization_unit_uid"
                )
            )

            if (
                org_uid
                and org_uid
                not in checked_orgs
            ):
                checked_orgs.add(
                    org_uid
                )

                if (
                    _lookup_organization(
                        connection,
                        org_uid,
                    )
                    is None
                ):
                    _append(
                        issues,
                        SEVERITY_ERROR,
                        "TARGET_ORGANIZATION_MISSING",
                        "当前数据库缺少成果记录引用的管理单位。",
                        entity_uid=org_uid,
                    )

            canal_uid = _clean_text(
                record.get(
                    "canal_unit_uid"
                )
            )

            if (
                canal_uid
                and canal_uid
                not in checked_canals
            ):
                checked_canals.add(
                    canal_uid
                )

                if (
                    _lookup_canal(
                        connection,
                        canal_uid,
                    )
                    is None
                ):
                    _append(
                        issues,
                        SEVERITY_ERROR,
                        "TARGET_CANAL_MISSING",
                        "当前数据库缺少成果记录引用的渠系。",
                        entity_uid=canal_uid,
                    )

        # -----------------------------------------------------
        # EngineeringAsset
        # -----------------------------------------------------

        for asset in contents.engineering_assets:
            asset_uid = _clean_text(
                asset.get(
                    "engineering_asset_uid"
                )
            )

            local_asset = (
                _load_local_asset(
                    connection,
                    asset_uid,
                )
            )

            if local_asset is not None:
                existing_assets += 1

                if (
                    _canonical_json(
                        _asset_signature(
                            local_asset
                        )
                    )
                    !=
                    _canonical_json(
                        _asset_signature(
                            asset
                        )
                    )
                ):
                    _append(
                        issues,
                        SEVERITY_ERROR,
                        "ASSET_UID_CONFLICT",
                        (
                            "相同 engineering_asset_uid "
                            "在目标数据库中已有不同业务内容。"
                        ),
                        entity_uid=asset_uid,
                    )

                continue

            new_assets += 1

            if project_id is None:
                continue

            business_code = (
                _clean_text(
                    asset.get(
                        "business_code"
                    )
                )
            )

            if not business_code:
                continue

            collision = (
                _load_local_asset_by_business_code(
                    connection,
                    project_id,
                    business_code,
                )
            )

            if (
                collision is not None
                and _clean_text(
                    collision.get(
                        "engineering_asset_uid"
                    )
                )
                != asset_uid
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "ASSET_BUSINESS_CODE_COLLISION",
                    (
                        "目标数据库已有另一工程对象使用相同业务编号。"
                        "当前数据库仍存在项目级 business_code 唯一约束，"
                        "本阶段不自动改号、不自动合并，也不在导入过程中"
                        "修改编号模型。"
                    ),
                    entity_uid=asset_uid,
                )

        # -----------------------------------------------------
        # SurveyRecord
        # -----------------------------------------------------

        package_record_uids = set()

        for record in contents.survey_records:
            record_uid = _clean_text(
                record.get(
                    "survey_record_uid"
                )
            )
            package_record_uids.add(
                record_uid
            )

            local_record = (
                _load_local_record(
                    connection,
                    record_uid,
                )
            )

            if local_record is None:
                new_records += 1
                continue

            existing_records += 1

            if (
                _canonical_json(
                    _record_signature(
                        local_record
                    )
                )
                !=
                _canonical_json(
                    _record_signature(
                        record
                    )
                )
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "RECORD_UID_CONFLICT",
                    (
                        "相同 survey_record_uid "
                        "在目标数据库中已有不同调查内容。"
                    ),
                    entity_uid=record_uid,
                )

        # -----------------------------------------------------
        # InspectionResult
        # -----------------------------------------------------

        for item in contents.inspection_results:
            record_uid = _clean_text(
                item.get(
                    "survey_record_uid"
                )
            )
            item_code = _clean_text(
                item.get(
                    "item_code"
                )
            )

            local_item = (
                _load_local_inspection(
                    connection,
                    record_uid,
                    item_code,
                )
            )

            if local_item is None:
                new_inspections += 1
                continue

            existing_inspections += 1

            if (
                _canonical_json(
                    _inspection_signature(
                        local_item
                    )
                )
                !=
                _canonical_json(
                    _inspection_signature(
                        item
                    )
                )
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "INSPECTION_CONFLICT",
                    (
                        "同一调查记录的相同分项评价"
                        "在目标数据库中已有不同内容。"
                    ),
                    entity_uid=(
                        f"{record_uid}:{item_code}"
                    ),
                )

        # -----------------------------------------------------
        # SurveyMedia
        # -----------------------------------------------------

        for media in contents.survey_media:
            media_uid = _clean_text(
                media.get(
                    "media_uid"
                )
            )

            local_media = (
                _load_local_media(
                    connection,
                    media_uid,
                )
            )

            if local_media is None:
                new_media += 1
                continue

            existing_media += 1

            if (
                _canonical_json(
                    _media_signature(
                        local_media
                    )
                )
                !=
                _canonical_json(
                    _media_signature(
                        media
                    )
                )
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "MEDIA_UID_CONFLICT",
                    (
                        "相同 media_uid 在目标数据库中"
                        "已有不同影像元数据或文件哈希。"
                    ),
                    entity_uid=media_uid,
                )

        # -----------------------------------------------------
        # 来源任务权威校验。
        #
        # 真值来源只允许是“上级当初下发任务时保存的冻结快照”：
        # survey_task_issues + survey_task_issue_scopes。
        #
        # current CanalManagementScope 仅用于提示历史与当前是否有变化，
        # 绝不作为历史任务合法性的判定依据。
        # -----------------------------------------------------

        issued_task_cache = {}
        issued_scope_cache = {}
        current_scope_cache = {}
        verified_pairs = set()

        for record in contents.survey_records:
            task_uid = _clean_text(
                record.get(
                    "source_task_uid"
                )
            )
            scope_uid = _clean_text(
                record.get(
                    "source_management_scope_uid"
                )
            )

            if not task_uid:
                continue

            record_uid = _clean_text(
                record.get(
                    "survey_record_uid"
                )
            )

            if task_uid not in issued_task_cache:
                issued_task_cache[
                    task_uid
                ] = (
                    _load_issued_task_authority(
                        connection,
                        task_uid,
                    )
                )

            issued_task = issued_task_cache[
                task_uid
            ]

            if issued_task is None:
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_TASK_ISSUE_MISSING",
                    (
                        "成果记录声明了来源任务，"
                        "但当前上级数据库没有该任务的"
                        "已下发冻结历史。"
                    ),
                    entity_uid=record_uid,
                )
                continue

            if (
                _clean_text(
                    issued_task.get(
                        "project_uid"
                    )
                )
                != _clean_text(
                    record.get(
                        "project_uid"
                    )
                )
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_TASK_PROJECT_MISMATCH",
                    (
                        "成果记录所属项目与原始下发任务"
                        "冻结项目不一致。"
                    ),
                    entity_uid=record_uid,
                )

            if (
                _clean_text(
                    issued_task.get(
                        "survey_batch_uid"
                    )
                )
                != _clean_text(
                    record.get(
                        "survey_batch_uid"
                    )
                )
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_TASK_BATCH_MISMATCH",
                    (
                        "成果记录所属调查批次与原始下发任务"
                        "冻结批次不一致。"
                    ),
                    entity_uid=record_uid,
                )

            scope_key = (
                int(
                    issued_task[
                        "id"
                    ]
                ),
                scope_uid,
            )

            if (
                scope_key
                not in issued_scope_cache
            ):
                issued_scope_cache[
                    scope_key
                ] = (
                    _load_issued_scope_authority(
                        connection,
                        scope_key[0],
                        scope_uid,
                    )
                )

            issued_scope = (
                issued_scope_cache[
                    scope_key
                ]
            )

            if issued_scope is None:
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_SCOPE_ISSUE_MISSING",
                    (
                        "成果记录声明的分管范围"
                        "不在该来源任务的下发冻结范围中。"
                    ),
                    entity_uid=record_uid,
                )
                continue

            record_org_uid = (
                _clean_text(
                    record.get(
                        "organization_unit_uid"
                    )
                )
            )

            if (
                _clean_text(
                    issued_task.get(
                        "organization_unit_uid"
                    )
                )
                != record_org_uid
                or _clean_text(
                    issued_scope.get(
                        "organization_unit_uid"
                    )
                )
                != record_org_uid
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_SCOPE_ORGANIZATION_MISMATCH",
                    (
                        "成果记录管理单位与原始下发任务"
                        "及其分管范围冻结快照不一致。"
                    ),
                    entity_uid=record_uid,
                )

            if (
                _clean_text(
                    issued_scope.get(
                        "canal_unit_uid"
                    )
                )
                != _clean_text(
                    record.get(
                        "canal_unit_uid"
                    )
                )
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_SCOPE_CANAL_MISMATCH",
                    (
                        "成果记录物理渠系与原始下发任务"
                        "分管范围冻结快照不一致。"
                    ),
                    entity_uid=record_uid,
                )

            authority_ok = (
                _clean_text(
                    issued_task.get(
                        "project_uid"
                    )
                )
                == _clean_text(
                    record.get(
                        "project_uid"
                    )
                )
                and _clean_text(
                    issued_task.get(
                        "survey_batch_uid"
                    )
                )
                == _clean_text(
                    record.get(
                        "survey_batch_uid"
                    )
                )
                and _clean_text(
                    issued_task.get(
                        "organization_unit_uid"
                    )
                )
                == record_org_uid
                and _clean_text(
                    issued_scope.get(
                        "organization_unit_uid"
                    )
                )
                == record_org_uid
                and _clean_text(
                    issued_scope.get(
                        "canal_unit_uid"
                    )
                )
                == _clean_text(
                    record.get(
                        "canal_unit_uid"
                    )
                )
            )

            if authority_ok:
                verified_pairs.add(
                    (
                        task_uid,
                        scope_uid,
                    )
                )

            if (
                scope_uid
                not in current_scope_cache
            ):
                current_scope_cache[
                    scope_uid
                ] = (
                    _load_current_management_scope(
                        connection,
                        scope_uid,
                    )
                )

            current_scope = (
                current_scope_cache[
                    scope_uid
                ]
            )

            if current_scope is None:
                _append(
                    issues,
                    SEVERITY_WARNING,
                    "SOURCE_SCOPE_CURRENT_MASTER_MISSING",
                    (
                        "该历史任务分管范围当前已不在"
                        "CanalManagementScope 主数据中；"
                        "仍以原始下发冻结快照作为历史真值。"
                    ),
                    entity_uid=scope_uid,
                )

            elif (
                _canonical_json(
                    _scope_authority_signature(
                        current_scope
                    )
                )
                !=
                _canonical_json(
                    _scope_authority_signature(
                        issued_scope
                    )
                )
            ):
                _append(
                    issues,
                    SEVERITY_WARNING,
                    "SOURCE_SCOPE_CURRENT_MASTER_CHANGED",
                    (
                        "该分管范围当前主数据与下发时冻结快照"
                        "已经不同；历史成果仍按原始下发事实校验。"
                    ),
                    entity_uid=scope_uid,
                )

        if verified_pairs:
            _append(
                issues,
                SEVERITY_INFO,
                "SOURCE_TASK_PROVENANCE_VERIFIED",
                (
                    "已按上级端原始下发冻结历史核验 "
                    f"{len(verified_pairs)} 个任务/分管范围来源组合。"
                ),
            )

    return SurveyResultImportPreflight(
        package_path=package_path,
        package_uid=package_uid,
        result_uid=result_uid,
        project_uid=project_uid,
        survey_batch_uid=(
            survey_batch_uid
        ),
        new_assets=new_assets,
        existing_assets=existing_assets,
        new_records=new_records,
        existing_records=(
            existing_records
        ),
        new_inspections=(
            new_inspections
        ),
        existing_inspections=(
            existing_inspections
        ),
        new_media=new_media,
        existing_media=existing_media,
        issues=tuple(
            issues
        ),
    )
