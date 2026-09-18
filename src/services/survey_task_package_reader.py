from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.yd_package import (
    SURVEY_TASK_PACKAGE_KIND,
)
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
    "reference/forms.json",
)


@dataclass(frozen=True)
class SurveyTaskPackageContents:
    package_path: Path
    manifest: dict
    task: dict
    organizations: tuple[dict, ...]
    canals: tuple[dict, ...]
    forms: tuple[dict, ...]


@dataclass(frozen=True)
class SurveyTaskPackageInspection:
    package_path: Path
    manifest: dict | None
    task: dict | None
    organizations: tuple[dict, ...]
    canals: tuple[dict, ...]
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
            (
                "检查结果："
                f"{self.error_count} 个错误"
            ),
        ]

        if self.task:
            task_name = self.task.get(
                "task_name"
            )

            if task_name:
                lines.append(
                    f"任务名称：{task_name}"
                )

            assignment = self.task.get(
                "assignment"
            )

            if isinstance(
                assignment,
                dict,
            ):
                organization_name = (
                    assignment.get(
                        "organization_name"
                    )
                )

                if organization_name:
                    lines.append(
                        (
                            "管理单位："
                            f"{organization_name}"
                        )
                    )

        if not self.issues:
            lines.append(
                "未发现问题。"
            )
        else:
            for issue in self.issues:
                suffix = (
                    f" [{issue.path}]"
                    if issue.path
                    else ""
                )

                lines.append(
                    (
                        f"[错误] {issue.code}："
                        f"{issue.message}{suffix}"
                    )
                )

        return "\n".join(lines)


def _append(
    issues,
    code,
    message,
    *,
    path="",
):
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
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
    ):
        _append(
            issues,
            code,
            message,
            path=path,
        )

        return None

    return value.strip()


def _read_items_file(
    package_path,
    logical_path,
    issues,
):
    try:
        data = (
            read_json_file_from_valid_package(
                package_path,
                logical_path,
            )
        )
    except Exception:
        _append(
            issues,
            "REFERENCE_JSON_INVALID",
            "参考数据文件无法读取。",
            path=logical_path,
        )
        return ()

    items = data.get(
        "items"
    )

    if not isinstance(
        items,
        list,
    ):
        _append(
            issues,
            "REFERENCE_ITEMS_INVALID",
            "参考数据 items 必须是数组。",
            path=logical_path,
        )
        return ()

    normalized = []

    for item in items:
        if not isinstance(
            item,
            dict,
        ):
            _append(
                issues,
                "REFERENCE_ITEM_INVALID",
                "参考数据项必须是对象。",
                path=logical_path,
            )
            continue

        normalized.append(
            dict(item)
        )

    return tuple(
        normalized
    )


def inspect_survey_task_package(
    package_path,
):
    package_path = Path(
        package_path
    )

    generic = inspect_package(
        package_path,
        expected_kind=(
            SURVEY_TASK_PACKAGE_KIND
        ),
    )

    issues = list(
        generic.issues
    )

    task = None
    organizations = ()
    canals = ()
    forms = ()

    if not generic.valid:
        return SurveyTaskPackageInspection(
            package_path=package_path,
            manifest=generic.manifest,
            task=None,
            organizations=(),
            canals=(),
            forms=(),
            issues=tuple(issues),
        )

    manifest = generic.manifest or {}

    for path in _REQUIRED_TASK_FILES:
        manifest_paths = {
            entry.get("path")
            for entry in (
                manifest.get(
                    "files"
                )
                or []
            )
            if isinstance(
                entry,
                dict,
            )
        }

        if path not in manifest_paths:
            _append(
                issues,
                "TASK_FILE_NOT_DECLARED",
                (
                    "调查任务包缺少必需文件"
                    "的 manifest 声明。"
                ),
                path=path,
            )

    if issues:
        return SurveyTaskPackageInspection(
            package_path=package_path,
            manifest=manifest,
            task=None,
            organizations=(),
            canals=(),
            forms=(),
            issues=tuple(issues),
        )

    try:
        task = (
            read_json_file_from_valid_package(
                package_path,
                "task.json",
            )
        )
    except Exception:
        _append(
            issues,
            "TASK_JSON_INVALID",
            "task.json 无法读取。",
            path="task.json",
        )

    organizations = (
        _read_items_file(
            package_path,
            (
                "reference/"
                "organization_units.json"
            ),
            issues,
        )
    )

    canals = (
        _read_items_file(
            package_path,
            (
                "reference/"
                "canal_units.json"
            ),
            issues,
        )
    )

    forms = (
        _read_items_file(
            package_path,
            "reference/forms.json",
            issues,
        )
    )

    if task is not None:
        task_uid = (
            _require_nonempty_string(
                task.get(
                    "task_uid"
                ),
                code="TASK_UID_INVALID",
                message=(
                    "task.json 缺少有效 task_uid。"
                ),
                issues=issues,
                path="task.json",
            )
        )

        manifest_task_uid = (
            _require_nonempty_string(
                manifest.get(
                    "task_uid"
                ),
                code=(
                    "MANIFEST_TASK_UID_INVALID"
                ),
                message=(
                    "manifest 缺少有效 task_uid。"
                ),
                issues=issues,
                path="manifest.json",
            )
        )

        if (
            task_uid
            and manifest_task_uid
            and task_uid
            != manifest_task_uid
        ):
            _append(
                issues,
                "TASK_UID_MISMATCH",
                (
                    "manifest 与 task.json "
                    "的 task_uid 不一致。"
                ),
            )

        project = task.get(
            "project"
        )

        if not isinstance(
            project,
            dict,
        ):
            _append(
                issues,
                "TASK_PROJECT_INVALID",
                "task.project 必须是对象。",
                path="task.json",
            )
            project_uid = None
        else:
            project_uid = (
                _require_nonempty_string(
                    project.get(
                        "project_uid"
                    ),
                    code=(
                        "TASK_PROJECT_UID_INVALID"
                    ),
                    message=(
                        "task.project 缺少 project_uid。"
                    ),
                    issues=issues,
                    path="task.json",
                )
            )

        manifest_project_uid = (
            _require_nonempty_string(
                manifest.get(
                    "project_uid"
                ),
                code=(
                    "MANIFEST_PROJECT_UID_INVALID"
                ),
                message=(
                    "manifest 缺少 project_uid。"
                ),
                issues=issues,
                path="manifest.json",
            )
        )

        if (
            project_uid
            and manifest_project_uid
            and project_uid
            != manifest_project_uid
        ):
            _append(
                issues,
                "PROJECT_UID_MISMATCH",
                (
                    "manifest 与 task.json "
                    "的 project_uid 不一致。"
                ),
            )

        batch = task.get(
            "survey_batch"
        )

        if not isinstance(
            batch,
            dict,
        ):
            _append(
                issues,
                "TASK_BATCH_INVALID",
                (
                    "task.survey_batch "
                    "必须是对象。"
                ),
                path="task.json",
            )
            batch_uid = None
        else:
            batch_uid = (
                _require_nonempty_string(
                    batch.get(
                        "survey_batch_uid"
                    ),
                    code=(
                        "TASK_BATCH_UID_INVALID"
                    ),
                    message=(
                        "task.survey_batch "
                        "缺少 survey_batch_uid。"
                    ),
                    issues=issues,
                    path="task.json",
                )
            )

        manifest_batch_uid = (
            _require_nonempty_string(
                manifest.get(
                    "survey_batch_uid"
                ),
                code=(
                    "MANIFEST_BATCH_UID_INVALID"
                ),
                message=(
                    "manifest 缺少 survey_batch_uid。"
                ),
                issues=issues,
                path="manifest.json",
            )
        )

        if (
            batch_uid
            and manifest_batch_uid
            and batch_uid
            != manifest_batch_uid
        ):
            _append(
                issues,
                "BATCH_UID_MISMATCH",
                (
                    "manifest 与 task.json "
                    "的 survey_batch_uid 不一致。"
                ),
            )

        assignment = task.get(
            "assignment"
        )

        if not isinstance(
            assignment,
            dict,
        ):
            _append(
                issues,
                "TASK_ASSIGNMENT_INVALID",
                "task.assignment 必须是对象。",
                path="task.json",
            )
            department_uid = None
            office_uid = None
        else:
            department_uid = (
                _require_nonempty_string(
                    assignment.get(
                        "department_uid"
                    ),
                    code=(
                        "TASK_DEPARTMENT_UID_INVALID"
                    ),
                    message=(
                        "任务缺少 department_uid。"
                    ),
                    issues=issues,
                    path="task.json",
                )
            )

            office_uid = (
                _require_nonempty_string(
                    assignment.get(
                        "organization_unit_uid"
                    ),
                    code=(
                        "TASK_ORGANIZATION_UID_INVALID"
                    ),
                    message=(
                        "任务缺少 organization_unit_uid。"
                    ),
                    issues=issues,
                    path="task.json",
                )
            )

        scope = task.get(
            "scope"
        )

        if not isinstance(
            scope,
            dict,
        ):
            _append(
                issues,
                "TASK_SCOPE_INVALID",
                "task.scope 必须是对象。",
                path="task.json",
            )
            selected_uids = []
        else:
            selected_uids = (
                scope.get(
                    "selected_canal_uids"
                )
            )

            if not isinstance(
                selected_uids,
                list,
            ):
                _append(
                    issues,
                    "TASK_SCOPE_CANALS_INVALID",
                    (
                        "scope.selected_canal_uids "
                        "必须是数组。"
                    ),
                    path="task.json",
                )
                selected_uids = []

            elif not selected_uids:
                _append(
                    issues,
                    "TASK_SCOPE_EMPTY",
                    "调查任务没有选定任何渠系。",
                    path="task.json",
                )

            else:
                normalized_selected = []

                for uid in selected_uids:
                    normalized = (
                        _require_nonempty_string(
                            uid,
                            code=(
                                "TASK_CANAL_UID_INVALID"
                            ),
                            message=(
                                "任务范围包含无效 canal_uid。"
                            ),
                            issues=issues,
                            path="task.json",
                        )
                    )

                    if normalized:
                        normalized_selected.append(
                            normalized
                        )

                if (
                    len(
                        normalized_selected
                    )
                    != len(
                        set(
                            normalized_selected
                        )
                    )
                ):
                    _append(
                        issues,
                        "TASK_CANAL_UID_DUPLICATE",
                        (
                            "任务范围包含重复 canal_uid。"
                        ),
                        path="task.json",
                    )

                selected_uids = (
                    normalized_selected
                )

    organization_by_uid = {}

    for item in organizations:
        uid = (
            _require_nonempty_string(
                item.get(
                    "organization_uid"
                ),
                code=(
                    "REFERENCE_ORGANIZATION_UID_INVALID"
                ),
                message=(
                    "组织参考数据缺少 organization_uid。"
                ),
                issues=issues,
                path=(
                    "reference/"
                    "organization_units.json"
                ),
            )
        )

        if not uid:
            continue

        if uid in organization_by_uid:
            _append(
                issues,
                "REFERENCE_ORGANIZATION_DUPLICATE",
                (
                    "组织参考数据包含重复 "
                    "organization_uid。"
                ),
                path=(
                    "reference/"
                    "organization_units.json"
                ),
            )
            continue

        organization_by_uid[
            uid
        ] = item

    if task is not None:
        if (
            department_uid
            and department_uid
            not in organization_by_uid
        ):
            _append(
                issues,
                "TASK_DEPARTMENT_NOT_IN_REFERENCE",
                (
                    "任务所属基层处不在"
                    "组织参考数据中。"
                ),
            )

        if (
            office_uid
            and office_uid
            not in organization_by_uid
        ):
            _append(
                issues,
                "TASK_ORGANIZATION_NOT_IN_REFERENCE",
                (
                    "任务管理单位不在"
                    "组织参考数据中。"
                ),
            )

        if (
            office_uid
            and department_uid
            and office_uid
            in organization_by_uid
        ):
            office = (
                organization_by_uid[
                    office_uid
                ]
            )

            if (
                office.get(
                    "parent_organization_uid"
                )
                != department_uid
            ):
                _append(
                    issues,
                    "TASK_ORGANIZATION_PARENT_MISMATCH",
                    (
                        "任务管理单位与所属基层处"
                        "参考关系不一致。"
                    ),
                )

    canal_by_uid = {}

    for item in canals:
        uid = (
            _require_nonempty_string(
                item.get(
                    "canal_uid"
                ),
                code=(
                    "REFERENCE_CANAL_UID_INVALID"
                ),
                message=(
                    "渠系参考数据缺少 canal_uid。"
                ),
                issues=issues,
                path=(
                    "reference/"
                    "canal_units.json"
                ),
            )
        )

        if not uid:
            continue

        if uid in canal_by_uid:
            _append(
                issues,
                "REFERENCE_CANAL_DUPLICATE",
                (
                    "渠系参考数据包含重复 canal_uid。"
                ),
                path=(
                    "reference/"
                    "canal_units.json"
                ),
            )
            continue

        canal_by_uid[
            uid
        ] = item

    for uid, item in canal_by_uid.items():
        parent_uid = item.get(
            "parent_canal_uid"
        )

        if (
            parent_uid is not None
            and (
                not isinstance(
                    parent_uid,
                    str,
                )
                or parent_uid
                not in canal_by_uid
            )
        ):
            _append(
                issues,
                "REFERENCE_CANAL_PARENT_MISSING",
                (
                    "渠系参考数据缺少被引用的"
                    "上级渠系。"
                ),
                path=(
                    "reference/"
                    "canal_units.json"
                ),
            )

    if task is not None:
        for selected_uid in (
            selected_uids
        ):
            if (
                selected_uid
                not in canal_by_uid
            ):
                _append(
                    issues,
                    "TASK_CANAL_NOT_IN_REFERENCE",
                    (
                        "任务选定渠系不在"
                        "渠系参考数据中。"
                    ),
                )
                continue

            selected_canal = (
                canal_by_uid[
                    selected_uid
                ]
            )

            if (
                office_uid
                and selected_canal.get(
                    "management_organization_uid"
                )
                != office_uid
            ):
                _append(
                    issues,
                    "TASK_CANAL_OWNER_MISMATCH",
                    (
                        "任务选定渠系的管理单位"
                        "与任务分配单位不一致。"
                    ),
                )

    form_codes = set()

    for item in forms:
        form_code = (
            _require_nonempty_string(
                item.get(
                    "form_code"
                ),
                code=(
                    "REFERENCE_FORM_CODE_INVALID"
                ),
                message=(
                    "表单参考数据缺少 form_code。"
                ),
                issues=issues,
                path=(
                    "reference/"
                    "forms.json"
                ),
            )
        )

        if not form_code:
            continue

        if form_code in form_codes:
            _append(
                issues,
                "REFERENCE_FORM_DUPLICATE",
                (
                    "表单参考数据包含重复 form_code。"
                ),
                path=(
                    "reference/"
                    "forms.json"
                ),
            )
        else:
            form_codes.add(
                form_code
            )

    if not forms:
        _append(
            issues,
            "REFERENCE_FORMS_EMPTY",
            "任务包没有表单参考信息。",
            path="reference/forms.json",
        )

    return SurveyTaskPackageInspection(
        package_path=package_path,
        manifest=manifest,
        task=task,
        organizations=(
            organizations
        ),
        canals=canals,
        forms=forms,
        issues=tuple(issues),
    )


def load_survey_task_package(
    package_path,
):
    """
    仅在完整性检查通过后返回包内容。
    """

    inspection = (
        inspect_survey_task_package(
            package_path
        )
    )

    if not inspection.valid:
        raise ValueError(
            inspection.format_text()
        )

    if inspection.manifest is None:
        raise ValueError(
            "任务包缺少 manifest。"
        )

    if inspection.task is None:
        raise ValueError(
            "任务包缺少 task.json。"
        )

    return SurveyTaskPackageContents(
        package_path=(
            inspection.package_path
        ),
        manifest=dict(
            inspection.manifest
        ),
        task=dict(
            inspection.task
        ),
        organizations=tuple(
            dict(item)
            for item in (
                inspection.organizations
            )
        ),
        canals=tuple(
            dict(item)
            for item in (
                inspection.canals
            )
        ),
        forms=tuple(
            dict(item)
            for item in (
                inspection.forms
            )
        ),
    )
