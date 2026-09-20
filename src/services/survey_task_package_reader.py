from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.survey_task_package import TASK_SCHEMA_VERSION
from services.survey_task_lineage import (
    SUPPORTED_TASK_SCHEMA_VERSIONS,
    normalize_task_lineage,
)
from services.yd_package import SURVEY_TASK_PACKAGE_KIND
from services.yd_package_reader import (
    PackageInspectionIssue,
    SEVERITY_ERROR,
    inspect_package,
    read_json_file_from_valid_package,
)


_REQUIRED_TASK_FILES = (
    "task.json",
    "reference/organization_units.json",
    "reference/canal_units.json",
    "reference/canal_management_scopes.json",
    "reference/forms.json",
)

_VALID_RANGE_MODES = {
    "whole",
    "segment_known",
    "segment_unknown",
}


@dataclass(frozen=True)
class SurveyTaskPackageContents:
    package_path: Path
    manifest: dict
    task: dict
    organizations: tuple[dict, ...]
    canals: tuple[dict, ...]
    management_scopes: tuple[dict, ...]
    forms: tuple[dict, ...]


@dataclass(frozen=True)
class SurveyTaskPackageInspection:
    package_path: Path
    manifest: dict | None
    task: dict | None
    organizations: tuple[dict, ...]
    canals: tuple[dict, ...]
    management_scopes: tuple[dict, ...]
    forms: tuple[dict, ...]
    issues: tuple[PackageInspectionIssue, ...]

    @property
    def error_count(self):
        return sum(
            1
            for issue in self.issues
            if issue.severity == SEVERITY_ERROR
        )

    @property
    def valid(self):
        return self.error_count == 0

    def format_text(self):
        lines = [
            f"调查任务包：{self.package_path}",
            f"检查结果：{self.error_count} 个错误",
        ]

        if self.task:
            task_name = self.task.get("task_name")
            if task_name:
                lines.append(f"任务名称：{task_name}")

            assignment = self.task.get("assignment")
            if isinstance(assignment, dict):
                organization_name = assignment.get("organization_name")
                if organization_name:
                    lines.append(f"管理单位：{organization_name}")

            scope = self.task.get("scope")
            if isinstance(scope, dict):
                count = scope.get("selected_management_scope_count")
                if count is not None:
                    lines.append(f"分管范围：{count} 项")

        if not self.issues:
            lines.append("未发现问题。")
        else:
            for issue in self.issues:
                suffix = f" [{issue.path}]" if issue.path else ""
                lines.append(
                    f"[错误] {issue.code}：{issue.message}{suffix}"
                )

        return "\n".join(lines)


def _inspection(
    package_path,
    manifest,
    task,
    organizations,
    canals,
    management_scopes,
    forms,
    issues,
):
    return SurveyTaskPackageInspection(
        package_path=package_path,
        manifest=manifest,
        task=task,
        organizations=tuple(organizations),
        canals=tuple(canals),
        management_scopes=tuple(management_scopes),
        forms=tuple(forms),
        issues=tuple(issues),
    )


def _append(issues, code, message, *, path=""):
    issues.append(
        PackageInspectionIssue(
            severity=SEVERITY_ERROR,
            code=code,
            message=message,
            path=path,
        )
    )


def _require_nonempty_string(
    value,
    *,
    code,
    message,
    issues,
    path="",
):
    if not isinstance(value, str) or not value.strip():
        _append(issues, code, message, path=path)
        return None
    return value.strip()


def _read_items_file(package_path, logical_path, issues):
    try:
        data = read_json_file_from_valid_package(package_path, logical_path)
    except Exception:
        _append(
            issues,
            "REFERENCE_JSON_INVALID",
            "参考数据文件无法读取。",
            path=logical_path,
        )
        return ()

    if not isinstance(data, dict):
        _append(
            issues,
            "REFERENCE_JSON_INVALID",
            "参考数据文件根节点必须是对象。",
            path=logical_path,
        )
        return ()

    items = data.get("items")
    if not isinstance(items, list):
        _append(
            issues,
            "REFERENCE_ITEMS_INVALID",
            "参考数据 items 必须是数组。",
            path=logical_path,
        )
        return ()

    result = []
    for item in items:
        if not isinstance(item, dict):
            _append(
                issues,
                "REFERENCE_ITEM_INVALID",
                "参考数据项必须是对象。",
                path=logical_path,
            )
            continue
        result.append(dict(item))
    return tuple(result)


def _validate_task_schema(task, manifest, issues):
    task_version = task.get("task_schema_version") if isinstance(task, dict) else None
    manifest_version = (
        manifest.get("task_schema_version") if isinstance(manifest, dict) else None
    )

    if task_version != manifest_version:
        _append(
            issues,
            "TASK_SCHEMA_VERSION_MISMATCH",
            "manifest 与 task.json 的 task_schema_version 不一致。",
        )
        return False

    if task_version not in SUPPORTED_TASK_SCHEMA_VERSIONS:
        _append(
            issues,
            "TASK_SCHEMA_VERSION_UNSUPPORTED",
            "该调查任务包格式不受当前版本支持。",
        )
        return False

    return True


def _validate_range_snapshot(item, issues):
    mode = item.get("range_mode")
    path = "reference/canal_management_scopes.json"

    if mode not in _VALID_RANGE_MODES:
        _append(
            issues,
            "REFERENCE_SCOPE_RANGE_MODE_INVALID",
            "分管范围包含无效 range_mode。",
            path=path,
        )
        return

    values = (
        item.get("start_stake_text"),
        item.get("start_stake_value"),
        item.get("end_stake_text"),
        item.get("end_stake_value"),
    )

    if mode in {"whole", "segment_unknown"}:
        if any(value is not None for value in values):
            _append(
                issues,
                "REFERENCE_SCOPE_RANGE_INVALID",
                "全渠或边界未知分管范围不能携带起止桩号。",
                path=path,
            )
        return

    start_value = item.get("start_stake_value")
    end_value = item.get("end_stake_value")

    if (
        isinstance(start_value, bool)
        or isinstance(end_value, bool)
        or not isinstance(start_value, (int, float))
        or not isinstance(end_value, (int, float))
    ):
        _append(
            issues,
            "REFERENCE_SCOPE_RANGE_INVALID",
            "边界已知分管范围必须包含有效起止桩号数值。",
            path=path,
        )
        return

    if float(start_value) > float(end_value):
        _append(
            issues,
            "REFERENCE_SCOPE_RANGE_INVALID",
            "分管范围起始桩号不能大于终止桩号。",
            path=path,
        )


def inspect_survey_task_package(package_path):
    package_path = Path(package_path)
    generic = inspect_package(
        package_path,
        expected_kind=SURVEY_TASK_PACKAGE_KIND,
    )
    issues = list(generic.issues)

    if not generic.valid:
        return _inspection(
            package_path,
            generic.manifest,
            None,
            (),
            (),
            (),
            (),
            issues,
        )

    manifest = generic.manifest or {}
    manifest_paths = {
        entry.get("path")
        for entry in (manifest.get("files") or [])
        if isinstance(entry, dict)
    }

    for logical_path in _REQUIRED_TASK_FILES:
        if logical_path not in manifest_paths:
            _append(
                issues,
                "TASK_FILE_NOT_DECLARED",
                "调查任务包缺少必需文件的 manifest 声明。",
                path=logical_path,
            )

    try:
        task = read_json_file_from_valid_package(package_path, "task.json")
    except Exception:
        task = None
        _append(
            issues,
            "TASK_JSON_INVALID",
            "task.json 无法读取。",
            path="task.json",
        )

    def read_if_declared(path):
        if path not in manifest_paths:
            return ()
        return _read_items_file(package_path, path, issues)

    organizations = read_if_declared("reference/organization_units.json")
    canals = read_if_declared("reference/canal_units.json")
    management_scopes = read_if_declared(
        "reference/canal_management_scopes.json"
    )
    forms = read_if_declared("reference/forms.json")

    if not isinstance(task, dict):
        if task is not None:
            _append(
                issues,
                "TASK_JSON_INVALID",
                "task.json 根节点必须是对象。",
                path="task.json",
            )
        return _inspection(
            package_path,
            manifest,
            None,
            organizations,
            canals,
            management_scopes,
            forms,
            issues,
        )

    _validate_task_schema(task, manifest, issues)

    task_uid = _require_nonempty_string(
        task.get("task_uid"),
        code="TASK_UID_INVALID",
        message="task.json 缺少有效 task_uid。",
        issues=issues,
        path="task.json",
    )
    manifest_task_uid = _require_nonempty_string(
        manifest.get("task_uid"),
        code="MANIFEST_TASK_UID_INVALID",
        message="manifest 缺少有效 task_uid。",
        issues=issues,
        path="manifest.json",
    )
    if task_uid and manifest_task_uid and task_uid != manifest_task_uid:
        _append(
            issues,
            "TASK_UID_MISMATCH",
            "manifest 与 task.json 的 task_uid 不一致。",
        )

    if (
        task_uid
        and task.get("task_schema_version")
        in SUPPORTED_TASK_SCHEMA_VERSIONS
    ):
        try:
            normalize_task_lineage(
                task,
                manifest=manifest,
            )
        except ValueError as error:
            _append(
                issues,
                "TASK_LINEAGE_INVALID",
                str(error),
                path="task.json",
            )

    project = task.get("project")
    if not isinstance(project, dict):
        _append(
            issues,
            "TASK_PROJECT_INVALID",
            "task.project 必须是对象。",
            path="task.json",
        )
        project_uid = None
    else:
        project_uid = _require_nonempty_string(
            project.get("project_uid"),
            code="TASK_PROJECT_UID_INVALID",
            message="task.project 缺少 project_uid。",
            issues=issues,
            path="task.json",
        )

    manifest_project_uid = _require_nonempty_string(
        manifest.get("project_uid"),
        code="MANIFEST_PROJECT_UID_INVALID",
        message="manifest 缺少 project_uid。",
        issues=issues,
        path="manifest.json",
    )
    if project_uid and manifest_project_uid and project_uid != manifest_project_uid:
        _append(
            issues,
            "PROJECT_UID_MISMATCH",
            "manifest 与 task.json 的 project_uid 不一致。",
        )

    batch = task.get("survey_batch")
    if not isinstance(batch, dict):
        _append(
            issues,
            "TASK_BATCH_INVALID",
            "task.survey_batch 必须是对象。",
            path="task.json",
        )
        batch_uid = None
    else:
        batch_uid = _require_nonempty_string(
            batch.get("survey_batch_uid"),
            code="TASK_BATCH_UID_INVALID",
            message="task.survey_batch 缺少 survey_batch_uid。",
            issues=issues,
            path="task.json",
        )

    manifest_batch_uid = _require_nonempty_string(
        manifest.get("survey_batch_uid"),
        code="MANIFEST_BATCH_UID_INVALID",
        message="manifest 缺少 survey_batch_uid。",
        issues=issues,
        path="manifest.json",
    )
    if batch_uid and manifest_batch_uid and batch_uid != manifest_batch_uid:
        _append(
            issues,
            "BATCH_UID_MISMATCH",
            "manifest 与 task.json 的 survey_batch_uid 不一致。",
        )

    assignment = task.get("assignment")
    if not isinstance(assignment, dict):
        _append(
            issues,
            "TASK_ASSIGNMENT_INVALID",
            "task.assignment 必须是对象。",
            path="task.json",
        )
        department_uid = None
        office_uid = None
    else:
        department_uid = _require_nonempty_string(
            assignment.get("department_uid"),
            code="TASK_DEPARTMENT_UID_INVALID",
            message="任务缺少 department_uid。",
            issues=issues,
            path="task.json",
        )
        office_uid = _require_nonempty_string(
            assignment.get("organization_unit_uid"),
            code="TASK_ORGANIZATION_UID_INVALID",
            message="任务缺少 organization_unit_uid。",
            issues=issues,
            path="task.json",
        )

    scope = task.get("scope")
    selected_uids = []
    if not isinstance(scope, dict):
        _append(
            issues,
            "TASK_SCOPE_INVALID",
            "task.scope 必须是对象。",
            path="task.json",
        )
    else:
        if "selected_canal_uids" in scope:
            _append(
                issues,
                "TASK_SCOPE_LEGACY_FIELD",
                "旧 selected_canal_uids 字段不再受支持。",
                path="task.json",
            )

        raw_selected = scope.get("selected_management_scope_uids")
        if not isinstance(raw_selected, list):
            _append(
                issues,
                "TASK_SCOPE_UIDS_INVALID",
                "scope.selected_management_scope_uids 必须是数组。",
                path="task.json",
            )
        elif not raw_selected:
            _append(
                issues,
                "TASK_SCOPE_EMPTY",
                "调查任务没有选定任何分管范围。",
                path="task.json",
            )
        else:
            for raw_uid in raw_selected:
                uid = _require_nonempty_string(
                    raw_uid,
                    code="TASK_SCOPE_UID_INVALID",
                    message="任务范围包含无效 management_scope_uid。",
                    issues=issues,
                    path="task.json",
                )
                if uid:
                    selected_uids.append(uid)

            if len(selected_uids) != len(set(selected_uids)):
                _append(
                    issues,
                    "TASK_SCOPE_UID_DUPLICATE",
                    "任务范围包含重复 management_scope_uid。",
                    path="task.json",
                )

        declared_count = scope.get("selected_management_scope_count")
        if (
            not isinstance(declared_count, int)
            or isinstance(declared_count, bool)
            or declared_count != len(selected_uids)
        ):
            _append(
                issues,
                "TASK_SCOPE_COUNT_MISMATCH",
                "任务分管范围计数与 UID 列表不一致。",
                path="task.json",
            )

    organization_by_uid = {}
    for item in organizations:
        uid = _require_nonempty_string(
            item.get("organization_uid"),
            code="REFERENCE_ORGANIZATION_UID_INVALID",
            message="组织参考数据缺少 organization_uid。",
            issues=issues,
            path="reference/organization_units.json",
        )
        if not uid:
            continue
        if uid in organization_by_uid:
            _append(
                issues,
                "REFERENCE_ORGANIZATION_DUPLICATE",
                "组织参考数据包含重复 organization_uid。",
                path="reference/organization_units.json",
            )
            continue
        organization_by_uid[uid] = item

    if department_uid and department_uid not in organization_by_uid:
        _append(
            issues,
            "TASK_DEPARTMENT_NOT_IN_REFERENCE",
            "任务所属基层处不在组织参考数据中。",
        )
    if office_uid and office_uid not in organization_by_uid:
        _append(
            issues,
            "TASK_ORGANIZATION_NOT_IN_REFERENCE",
            "任务管理单位不在组织参考数据中。",
        )
    if office_uid and department_uid and office_uid in organization_by_uid:
        office = organization_by_uid[office_uid]
        if office.get("parent_organization_uid") != department_uid:
            _append(
                issues,
                "TASK_ORGANIZATION_PARENT_MISMATCH",
                "任务管理单位与所属基层处参考关系不一致。",
            )

    canal_by_uid = {}
    for item in canals:
        uid = _require_nonempty_string(
            item.get("canal_uid"),
            code="REFERENCE_CANAL_UID_INVALID",
            message="渠系参考数据缺少 canal_uid。",
            issues=issues,
            path="reference/canal_units.json",
        )
        if not uid:
            continue

        if "management_organization_uid" in item:
            _append(
                issues,
                "REFERENCE_CANAL_LEGACY_OWNER_FIELD",
                "新任务包的物理渠系参考不能携带旧管理单位归属字段。",
                path="reference/canal_units.json",
            )

        if uid in canal_by_uid:
            _append(
                issues,
                "REFERENCE_CANAL_DUPLICATE",
                "渠系参考数据包含重复 canal_uid。",
                path="reference/canal_units.json",
            )
            continue
        canal_by_uid[uid] = item

    for item in canal_by_uid.values():
        parent_uid = item.get("parent_canal_uid")
        if (
            parent_uid is not None
            and (
                not isinstance(parent_uid, str)
                or parent_uid not in canal_by_uid
            )
        ):
            _append(
                issues,
                "REFERENCE_CANAL_PARENT_MISSING",
                "渠系参考数据缺少被引用的上级渠系。",
                path="reference/canal_units.json",
            )

    scope_by_uid = {}
    for item in management_scopes:
        uid = _require_nonempty_string(
            item.get("management_scope_uid"),
            code="REFERENCE_SCOPE_UID_INVALID",
            message="分管范围参考数据缺少 management_scope_uid。",
            issues=issues,
            path="reference/canal_management_scopes.json",
        )
        if not uid:
            continue
        if uid in scope_by_uid:
            _append(
                issues,
                "REFERENCE_SCOPE_DUPLICATE",
                "分管范围参考数据包含重复 management_scope_uid。",
                path="reference/canal_management_scopes.json",
            )
            continue
        scope_by_uid[uid] = item

        canal_uid = _require_nonempty_string(
            item.get("canal_uid"),
            code="REFERENCE_SCOPE_CANAL_UID_INVALID",
            message="分管范围参考数据缺少 canal_uid。",
            issues=issues,
            path="reference/canal_management_scopes.json",
        )
        item_office_uid = _require_nonempty_string(
            item.get("organization_unit_uid"),
            code="REFERENCE_SCOPE_ORGANIZATION_UID_INVALID",
            message="分管范围参考数据缺少 organization_unit_uid。",
            issues=issues,
            path="reference/canal_management_scopes.json",
        )

        if canal_uid and canal_uid not in canal_by_uid:
            _append(
                issues,
                "REFERENCE_SCOPE_CANAL_MISSING",
                "分管范围对应物理渠系不在渠系参考数据中。",
                path="reference/canal_management_scopes.json",
            )
        if office_uid and item_office_uid and item_office_uid != office_uid:
            _append(
                issues,
                "REFERENCE_SCOPE_OWNER_MISMATCH",
                "分管范围管理单位与任务分配单位不一致。",
                path="reference/canal_management_scopes.json",
            )
        if item.get("status") != "active":
            _append(
                issues,
                "REFERENCE_SCOPE_STATUS_INVALID",
                "任务只能包含下发时处于启用状态的分管范围。",
                path="reference/canal_management_scopes.json",
            )
        _validate_range_snapshot(item, issues)

    if set(selected_uids) != set(scope_by_uid):
        _append(
            issues,
            "TASK_SCOPE_REFERENCE_MISMATCH",
            "任务选定分管范围与分管范围参考快照不一致。",
        )

    form_codes = set()
    for item in forms:
        form_code = _require_nonempty_string(
            item.get("form_code"),
            code="REFERENCE_FORM_CODE_INVALID",
            message="表单参考数据缺少 form_code。",
            issues=issues,
            path="reference/forms.json",
        )
        if not form_code:
            continue
        if form_code in form_codes:
            _append(
                issues,
                "REFERENCE_FORM_DUPLICATE",
                "表单参考数据包含重复 form_code。",
                path="reference/forms.json",
            )
        else:
            form_codes.add(form_code)

    if not forms:
        _append(
            issues,
            "REFERENCE_FORMS_EMPTY",
            "任务包没有表单参考信息。",
            path="reference/forms.json",
        )

    return _inspection(
        package_path,
        manifest,
        task,
        organizations,
        canals,
        management_scopes,
        forms,
        issues,
    )


def load_survey_task_package(package_path):
    inspection = inspect_survey_task_package(package_path)
    if not inspection.valid:
        raise ValueError(inspection.format_text())
    if inspection.manifest is None:
        raise ValueError("任务包缺少 manifest。")
    if inspection.task is None:
        raise ValueError("任务包缺少 task.json。")

    return SurveyTaskPackageContents(
        package_path=inspection.package_path,
        manifest=dict(inspection.manifest),
        task=dict(inspection.task),
        organizations=tuple(dict(item) for item in inspection.organizations),
        canals=tuple(dict(item) for item in inspection.canals),
        management_scopes=tuple(
            dict(item) for item in inspection.management_scopes
        ),
        forms=tuple(dict(item) for item in inspection.forms),
    )
