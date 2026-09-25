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

    # V1.0.1 以前已经公开使用的构造参数保持原顺序和必填语义，
    # 这样旧 UI / 单元测试 / 外部调用无需跟随内部统计扩展修改。
    new_assets: int
    existing_assets: int

    new_records: int
    existing_records: int

    new_inspections: int
    existing_inspections: int

    new_media: int
    existing_media: int

    issues: tuple[SurveyResultPreflightIssue, ...]

    # V1.0.2 新增分类均提供向后兼容默认值。
    updated_assets: int = 0
    stale_assets: int = 0
    conflict_assets: int = 0

    updated_records: int = 0
    stale_records: int = 0
    conflict_records: int = 0

    updated_inspections: int = 0

    asset_update_uids: tuple[str, ...] = ()
    asset_stale_uids: tuple[str, ...] = ()
    record_update_uids: tuple[str, ...] = ()
    record_stale_uids: tuple[str, ...] = ()

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
    def info_count(self):
        return sum(
            1
            for item in self.issues
            if item.severity == SEVERITY_INFO
        )

    @property
    def can_import(self):
        return self.error_count == 0

    @property
    def has_new_data(self):
        # 保留 Stage 12.8 旧接口语义：这里只回答“是否有新增”。
        return any(
            (
                self.new_assets,
                self.new_records,
                self.new_inspections,
                self.new_media,
            )
        )

    @property
    def has_updates(self):
        return any(
            (
                self.updated_assets,
                self.updated_records,
                self.updated_inspections,
            )
        )

    @property
    def has_importable_changes(self):
        return self.has_new_data or self.has_updates

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
                f"已存在 {self.existing_assets}，"
                f"待更新 {self.updated_assets}，"
                f"旧版本 {self.stale_assets}，"
                f"冲突 {self.conflict_assets}"
            ),
            (
                "调查记录："
                f"新增 {self.new_records}，"
                f"已存在 {self.existing_records}，"
                f"待更新 {self.updated_records}，"
                f"旧版本 {self.stale_records}，"
                f"冲突 {self.conflict_records}"
            ),
            (
                "分项评价："
                f"新增 {self.new_inspections}，"
                f"已存在 {self.existing_inspections}，"
                f"随记录更新 {self.updated_inspections}"
            ),
            (
                "影像："
                f"新增 {self.new_media}，"
                f"已存在 {self.existing_media}"
            ),
        ]

        if not self.issues:
            lines.append("未发现目标数据库冲突。")
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

    def format_user_text(self):
        lines = [
            f"成果包：{self.package_path.name}",
            (
                "检查结果："
                f"{self.error_count} 个必须处理的问题，"
                f"{self.warning_count} 条需要注意的信息"
            ),
            (
                "工程："
                f"新增 {self.new_assets}，已存在 {self.existing_assets}，"
                f"可更新 {self.updated_assets}，较早版本 {self.stale_assets}，"
                f"冲突 {self.conflict_assets}"
            ),
            (
                "调查记录："
                f"新增 {self.new_records}，已存在 {self.existing_records}，"
                f"可更新 {self.updated_records}，较早版本 {self.stale_records}，"
                f"冲突 {self.conflict_records}"
            ),
            (
                "分项评价："
                f"新增 {self.new_inspections}，已存在 {self.existing_inspections}，"
                f"随记录更新 {self.updated_inspections}"
            ),
            f"影像：新增 {self.new_media}，已存在 {self.existing_media}",
        ]

        if not self.issues:
            lines.append("未发现需要处理的问题。")
            return "\n".join(lines)

        labels = {
            SEVERITY_ERROR: "需处理",
            SEVERITY_WARNING: "请注意",
            SEVERITY_INFO: "说明",
        }
        lines.append("")
        for item in self.issues:
            lines.append(
                f"[{labels.get(item.severity, '说明')}] {item.message}"
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



def _safe_revision(
    value,
    default=1,
):
    try:
        parsed = int(
            value
            if value is not None
            else default
        )
    except (
        TypeError,
        ValueError,
    ):
        parsed = int(default)

    return max(
        0,
        parsed,
    )


def _asset_identity_signature(item):
    return {
        "project_uid": _clean_text(
            item.get("project_uid")
        ),
        "asset_type": _clean_text(
            item.get("asset_type")
        ),
        "organization_unit_uid": _clean_text(
            item.get("organization_unit_uid")
        ),
        "canal_unit_uid": _clean_text(
            item.get("canal_unit_uid")
        ),
        "first_survey_batch_uid": _optional_text(
            item.get("first_survey_batch_uid")
        ),
    }


def _record_identity_signature(item):
    form = (
        item.get("form")
        if isinstance(
            item.get("form"),
            dict,
        )
        else {}
    )

    return {
        "source_task_uid": _optional_text(
            item.get("source_task_uid")
        ),
        "source_management_scope_uid": _optional_text(
            item.get("source_management_scope_uid")
        ),
        "project_uid": _clean_text(
            item.get("project_uid")
        ),
        "survey_batch_uid": _clean_text(
            item.get("survey_batch_uid")
        ),
        "form_code": _clean_text(
            form.get("form_code")
            or item.get("form_code")
        ),
        "version_code": _clean_text(
            form.get("version_code")
            or item.get("version_code")
        ),
        "record_type": _clean_text(
            item.get("record_type")
        ),
        "organization_unit_uid": _clean_text(
            item.get("organization_unit_uid")
        ),
        "canal_unit_uid": _clean_text(
            item.get("canal_unit_uid")
        ),
        "engineering_asset_uid": _clean_text(
            item.get("engineering_asset_uid")
        ),
    }


def _revision_state(
    local_item,
    incoming_item,
    *,
    identity_signature,
    content_signature,
):
    """
    返回：
    existing / update / stale /
    identity_conflict / same_revision_conflict / diverged

    关键规则：完全相同的业务内容永远先按 existing 处理。
    revision_no 用于判断“内容不同”时谁更新、是否回退、是否双向分叉；
    不应把同内容仅因来源基线为 0 判成一次业务更新。
    """
    if (
        _canonical_json(identity_signature(local_item))
        != _canonical_json(identity_signature(incoming_item))
    ):
        return ("identity_conflict", None)

    incoming_revision = _safe_revision(
        incoming_item.get("revision_no"),
        1,
    )
    local_revision = _safe_revision(
        local_item.get("revision_no"),
        1,
    )
    source_revision = _safe_revision(
        local_item.get("source_revision_no"),
        0,
    )

    same_content = (
        _canonical_json(content_signature(local_item))
        == _canonical_json(content_signature(incoming_item))
    )

    metadata = {
        "incoming_revision": incoming_revision,
        "local_revision": local_revision,
        "source_revision": source_revision,
        "same_content": same_content,
    }

    # 幂等优先：相同 UID + 相同身份 + 相同业务内容就是已存在。
    # 这同时兼容“同库预检”和 V1.0.1 升级后 source_revision_no=0 的记录。
    if same_content:
        return ("existing", metadata)

    if incoming_revision < source_revision:
        return ("stale", metadata)

    if incoming_revision == source_revision:
        return ("same_revision_conflict", metadata)

    # incoming_revision > source_revision
    # 上级在最近一次下级版本之后也发生过本地修改，
    # 同时下级提交更高 revision：需要人工解决双向分叉。
    if local_revision > source_revision:
        return ("diverged", metadata)

    return ("update", metadata)

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
            organization_unit_uid,
            target_unit_type
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
            ea.notes,
            ea.revision_no,
            ea.source_revision_no
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
            sr.void_reason,
            sr.revision_no,
            sr.source_revision_no
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
    updated_assets = 0
    stale_assets = 0
    conflict_assets = 0

    new_records = 0
    existing_records = 0
    updated_records = 0
    stale_records = 0
    conflict_records = 0

    new_inspections = 0
    existing_inspections = 0
    updated_inspections = 0

    new_media = 0
    existing_media = 0

    asset_update_uids = set()
    asset_stale_uids = set()
    record_update_uids = set()
    record_stale_uids = set()
    record_conflict_uids = set()

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
                state, metadata = _revision_state(
                    local_asset,
                    asset,
                    identity_signature=(
                        _asset_identity_signature
                    ),
                    content_signature=(
                        _asset_signature
                    ),
                )

                if state == "existing":
                    existing_assets += 1

                elif state == "update":
                    updated_assets += 1
                    asset_update_uids.add(
                        asset_uid
                    )
                    _append(
                        issues,
                        SEVERITY_INFO,
                        "ASSET_UPDATE_AVAILABLE",
                        (
                            "下级工程对象版本较新，"
                            "确认后可更新。"
                            f" 来源版本 {metadata['source_revision']}"
                            f" -> {metadata['incoming_revision']}。"
                        ),
                        entity_uid=asset_uid,
                    )

                elif state == "stale":
                    stale_assets += 1
                    asset_stale_uids.add(
                        asset_uid
                    )
                    _append(
                        issues,
                        SEVERITY_WARNING,
                        "ASSET_STALE_VERSION",
                        (
                            "成果包中的工程对象版本旧于"
                            "当前已接收来源版本，将自动忽略，"
                            "不会回退上级数据。"
                        ),
                        entity_uid=asset_uid,
                    )

                else:
                    conflict_assets += 1

                    code = {
                        "identity_conflict": (
                            "ASSET_IDENTITY_CONFLICT"
                        ),
                        "same_revision_conflict": (
                            "ASSET_REVISION_CONTENT_CONFLICT"
                        ),
                        "diverged": (
                            "ASSET_DIVERGED"
                        ),
                    }.get(
                        state,
                        "ASSET_UID_CONFLICT",
                    )

                    if state == "diverged":
                        message = (
                            "上下级在最近一次已接收版本之后"
                            "都修改了该工程对象，当前禁止自动覆盖。"
                        )
                    elif state == "identity_conflict":
                        message = (
                            "相同 engineering_asset_uid 的"
                            "项目/渠系/工程类型等身份字段发生变化。"
                        )
                    else:
                        message = (
                            "相同工程对象 revision_no 下出现"
                            "不同业务内容，版本契约异常。"
                        )

                    _append(
                        issues,
                        SEVERITY_ERROR,
                        code,
                        message,
                        entity_uid=asset_uid,
                    )

                continue

            new_assets += 1

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

            state, metadata = _revision_state(
                local_record,
                record,
                identity_signature=(
                    _record_identity_signature
                ),
                content_signature=(
                    _record_signature
                ),
            )

            if state == "existing":
                existing_records += 1

            elif state == "update":
                updated_records += 1
                record_update_uids.add(
                    record_uid
                )
                _append(
                    issues,
                    SEVERITY_INFO,
                    "RECORD_UPDATE_AVAILABLE",
                    (
                        "检测到下级修订记录，确认后可更新。"
                        f" 来源版本 {metadata['source_revision']}"
                        f" -> {metadata['incoming_revision']}。"
                    ),
                    entity_uid=record_uid,
                )

            elif state == "stale":
                stale_records += 1
                record_stale_uids.add(
                    record_uid
                )
                _append(
                    issues,
                    SEVERITY_WARNING,
                    "RECORD_STALE_VERSION",
                    (
                        "成果包中的调查记录版本旧于"
                        "当前已接收来源版本，将自动忽略，"
                        "不会回退上级数据。"
                    ),
                    entity_uid=record_uid,
                )

            else:
                conflict_records += 1
                record_conflict_uids.add(
                    record_uid
                )

                code = {
                    "identity_conflict": (
                        "RECORD_IDENTITY_CONFLICT"
                    ),
                    "same_revision_conflict": (
                        "RECORD_REVISION_CONTENT_CONFLICT"
                    ),
                    "diverged": (
                        "RECORD_DIVERGED"
                    ),
                }.get(
                    state,
                    "RECORD_UID_CONFLICT",
                )

                if state == "diverged":
                    message = (
                        "上下级在最近一次已接收版本之后"
                        "都修改了该调查记录，当前禁止自动覆盖；"
                        "需要人工决定采用哪一版。"
                    )
                elif state == "identity_conflict":
                    message = (
                        "相同 survey_record_uid 的任务来源、"
                        "渠系、工程对象或表单身份发生变化。"
                    )
                else:
                    message = (
                        "相同调查记录 revision_no 下出现"
                        "不同业务内容，版本契约异常。"
                    )

                _append(
                    issues,
                    SEVERITY_ERROR,
                    code,
                    message,
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

            # 调查记录整体更新时，分项评价作为该 revision 的
            # 权威子内容一并替换；旧版本和冲突记录都不写入。
            if record_uid in record_update_uids:
                updated_inspections += 1
                continue

            if (
                record_uid in record_stale_uids
                or record_uid in record_conflict_uids
            ):
                existing_inspections += 1
                continue

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
                # 记录 revision 未变化却出现分项内容变化，
                # 说明成果版本契约不一致，仍然阻断。
                if record_uid not in record_conflict_uids:
                    conflict_records += 1
                    record_conflict_uids.add(
                        record_uid
                    )

                _append(
                    issues,
                    SEVERITY_ERROR,
                    "INSPECTION_REVISION_CONFLICT",
                    (
                        "调查记录 revision 未变化，但分项评价内容不同。"
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
        # 来源任务 / 汇总提交任务权威校验
        # -----------------------------------------------------

        submission_task_uid = _optional_text(
            result.get("submission_task_uid")
        )

        submission_task = None

        if submission_task_uid:
            submission_task = _load_issued_task_authority(
                connection,
                submission_task_uid,
            )

            if submission_task is None:
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SUBMISSION_TASK_ISSUE_MISSING",
                    (
                        "成果包声明了汇总提交任务，"
                        "但当前数据库没有该任务的已下发冻结历史。"
                    ),
                    entity_uid=submission_task_uid,
                )
            else:
                if (
                    _clean_text(
                        submission_task.get("project_uid")
                    )
                    != project_uid
                ):
                    _append(
                        issues,
                        SEVERITY_ERROR,
                        "SUBMISSION_TASK_PROJECT_MISMATCH",
                        "汇总提交任务所属项目与成果包项目不一致。",
                        entity_uid=submission_task_uid,
                    )

                if (
                    _clean_text(
                        submission_task.get("survey_batch_uid")
                    )
                    != survey_batch_uid
                ):
                    _append(
                        issues,
                        SEVERITY_ERROR,
                        "SUBMISSION_TASK_BATCH_MISMATCH",
                        "汇总提交任务所属调查批次与成果包批次不一致。",
                        entity_uid=submission_task_uid,
                    )

        issued_task_cache = {}
        issued_scope_cache = {}
        current_scope_cache = {}
        verified_pairs = set()
        aggregate_verified = False

        for record in contents.survey_records:
            task_uid = _clean_text(
                record.get("source_task_uid")
            )
            scope_uid = _clean_text(
                record.get("source_management_scope_uid")
            )

            if not task_uid:
                continue

            record_uid = _clean_text(
                record.get("survey_record_uid")
            )

            if submission_task_uid:
                issued_task = submission_task
                authority_task_uid = submission_task_uid

                if issued_task is None:
                    continue

                target_unit_type = (
                    _clean_text(
                        issued_task.get("target_unit_type")
                    )
                    or "water_office"
                )

                if (
                    task_uid != submission_task_uid
                    and target_unit_type != "department"
                ):
                    _append(
                        issues,
                        SEVERITY_ERROR,
                        "SUBMISSION_TASK_AGGREGATION_NOT_ALLOWED",
                        (
                            "成果记录来源任务与本次提交任务不同，"
                            "但提交任务不是处级父任务。"
                        ),
                        entity_uid=record_uid,
                    )
            else:
                authority_task_uid = task_uid

                if authority_task_uid not in issued_task_cache:
                    issued_task_cache[authority_task_uid] = (
                        _load_issued_task_authority(
                            connection,
                            authority_task_uid,
                        )
                    )

                issued_task = issued_task_cache[
                    authority_task_uid
                ]

                if issued_task is None:
                    _append(
                        issues,
                        SEVERITY_ERROR,
                        "SOURCE_TASK_ISSUE_MISSING",
                        (
                            "成果记录声明了来源任务，"
                            "但当前上级数据库没有该任务的已下发冻结历史。"
                        ),
                        entity_uid=record_uid,
                    )
                    continue

            if (
                _clean_text(issued_task.get("project_uid"))
                != _clean_text(record.get("project_uid"))
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_TASK_PROJECT_MISMATCH",
                    "成果记录所属项目与验收任务冻结项目不一致。",
                    entity_uid=record_uid,
                )

            if (
                _clean_text(
                    issued_task.get("survey_batch_uid")
                )
                != _clean_text(
                    record.get("survey_batch_uid")
                )
            ):
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_TASK_BATCH_MISMATCH",
                    (
                        "成果记录所属调查批次与验收任务"
                        "冻结批次不一致。"
                    ),
                    entity_uid=record_uid,
                )

            scope_key = (
                int(issued_task["id"]),
                scope_uid,
            )

            if scope_key not in issued_scope_cache:
                issued_scope_cache[scope_key] = (
                    _load_issued_scope_authority(
                        connection,
                        scope_key[0],
                        scope_uid,
                    )
                )

            issued_scope = issued_scope_cache[
                scope_key
            ]

            if issued_scope is None:
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_SCOPE_ISSUE_MISSING",
                    (
                        "成果记录声明的分管范围"
                        "不在本次验收任务的下发冻结范围中。"
                    ),
                    entity_uid=record_uid,
                )
                continue

            record_org_uid = _clean_text(
                record.get("organization_unit_uid")
            )

            target_unit_type = (
                _clean_text(
                    issued_task.get("target_unit_type")
                )
                or "water_office"
            )

            task_org_matches = True

            if target_unit_type == "water_office":
                task_org_matches = (
                    _clean_text(
                        issued_task.get("organization_unit_uid")
                    )
                    == record_org_uid
                )

            scope_org_matches = (
                _clean_text(
                    issued_scope.get("organization_unit_uid")
                )
                == record_org_uid
            )

            if not task_org_matches or not scope_org_matches:
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_SCOPE_ORGANIZATION_MISMATCH",
                    (
                        "成果记录管理单位与验收任务"
                        "及其分管范围冻结快照不一致。"
                    ),
                    entity_uid=record_uid,
                )

            canal_matches = (
                _clean_text(
                    issued_scope.get("canal_unit_uid")
                )
                == _clean_text(
                    record.get("canal_unit_uid")
                )
            )

            if not canal_matches:
                _append(
                    issues,
                    SEVERITY_ERROR,
                    "SOURCE_SCOPE_CANAL_MISMATCH",
                    (
                        "成果记录物理渠系与验收任务"
                        "分管范围冻结快照不一致。"
                    ),
                    entity_uid=record_uid,
                )

            authority_ok = (
                _clean_text(
                    issued_task.get("project_uid")
                )
                == _clean_text(
                    record.get("project_uid")
                )
                and _clean_text(
                    issued_task.get("survey_batch_uid")
                )
                == _clean_text(
                    record.get("survey_batch_uid")
                )
                and task_org_matches
                and scope_org_matches
                and canal_matches
            )

            if authority_ok:
                verified_pairs.add(
                    (
                        authority_task_uid,
                        scope_uid,
                    )
                )

                if (
                    submission_task_uid
                    and task_uid != submission_task_uid
                ):
                    aggregate_verified = True

            if scope_uid not in current_scope_cache:
                current_scope_cache[scope_uid] = (
                    _load_current_management_scope(
                        connection,
                        scope_uid,
                    )
                )

            current_scope = current_scope_cache[
                scope_uid
            ]

            if current_scope is None:
                _append(
                    issues,
                    (
                        SEVERITY_INFO
                        if authority_ok
                        else SEVERITY_WARNING
                    ),
                    "SOURCE_SCOPE_CURRENT_MASTER_MISSING",
                    (
                        "任务下发后，这条分管范围在当前基础资料中已不存在。"
                        "系统已按任务下发时保存的范围完成核验，"
                        "不影响本次历史成果导入。"
                        if authority_ok
                        else
                        "当前基础资料中已找不到这条分管范围，"
                        "且任务来源核验未完全通过，请先检查任务和分管范围。"
                    ),
                    entity_uid=scope_uid,
                )
            elif (
                _canonical_json(
                    _scope_authority_signature(
                        current_scope
                    )
                )
                != _canonical_json(
                    _scope_authority_signature(
                        issued_scope
                    )
                )
            ):
                _append(
                    issues,
                    (
                        SEVERITY_INFO
                        if authority_ok
                        else SEVERITY_WARNING
                    ),
                    "SOURCE_SCOPE_CURRENT_MASTER_CHANGED",
                    (
                        "这条分管范围在任务下发后已经调整。"
                        "系统已按任务下发时保存的范围完成核验，"
                        "不影响本次历史成果导入。"
                        if authority_ok
                        else
                        "这条分管范围与任务下发时的范围不同，"
                        "且任务来源核验未完全通过，请先确认后再导入。"
                    ),
                    entity_uid=scope_uid,
                )

        if aggregate_verified:
            _append(
                issues,
                SEVERITY_INFO,
                "AGGREGATE_SUBMISSION_AUTHORITY_VERIFIED",
                (
                    "处级汇总成果已按上级下发的任务范围核验通过；"
                    "各调查记录的原始来源保持不变。"
                ),
                entity_uid=(
                    submission_task_uid
                    or ""
                ),
            )

        if verified_pairs:
            _append(
                issues,
                SEVERITY_INFO,
                "SOURCE_TASK_PROVENANCE_VERIFIED",
                (
                    "成果来源任务已核验，"
                    f"共确认 {len(verified_pairs)} 组任务与分管范围，"
                    "调查记录均在任务授权范围内。"
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
        updated_assets=updated_assets,
        stale_assets=stale_assets,
        conflict_assets=conflict_assets,
        new_records=new_records,
        existing_records=(
            existing_records
        ),
        updated_records=updated_records,
        stale_records=stale_records,
        conflict_records=conflict_records,
        new_inspections=(
            new_inspections
        ),
        existing_inspections=(
            existing_inspections
        ),
        updated_inspections=(
            updated_inspections
        ),
        new_media=new_media,
        existing_media=existing_media,
        asset_update_uids=tuple(
            sorted(
                asset_update_uids
            )
        ),
        asset_stale_uids=tuple(
            sorted(
                asset_stale_uids
            )
        ),
        record_update_uids=tuple(
            sorted(
                record_update_uids
            )
        ),
        record_stale_uids=tuple(
            sorted(
                record_stale_uids
            )
        ),
        issues=tuple(
            issues
        ),
    )
