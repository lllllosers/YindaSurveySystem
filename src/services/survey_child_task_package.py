from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import database

from services.master_data_integrity import (
    check_master_data_integrity,
)
from services.survey_task_issue_history import (
    record_issued_survey_task,
)
from services.survey_task_lineage import (
    CURRENT_TASK_SCHEMA_VERSION,
    build_child_task_lineage,
)
from services.survey_task_package_reader import (
    load_survey_task_package,
)
from services.survey_task_workspace import (
    get_current_task_workspace,
)
from services.yd_package import (
    SURVEY_TASK_PACKAGE_KIND,
    encode_json_bytes,
    new_stable_token,
    normalize_task_package_path,
    write_package,
)
from version import (
    APP_VERSION,
    APP_VERSION_LABEL,
)


@dataclass(frozen=True)
class ChildSurveyTaskExportRequest:
    organization_unit_id: int
    management_scope_uids: tuple[str, ...]
    task_name: str
    output_path: Path
    notes: str = ""


@dataclass(frozen=True)
class ChildSurveyTaskExportResult:
    output_path: Path
    package_uid: str
    task_uid: str
    parent_task_uid: str
    root_task_uid: str
    task_depth: int
    organization_name: str
    selected_management_scope_count: int


def _clean_text(value):
    return str(
        value or ""
    ).strip()


def _require_text(
    value,
    field_name,
):
    value = _clean_text(
        value
    )
    if not value:
        raise ValueError(
            f"{field_name}不能为空。"
        )
    return value


def _normalize_request(
    request,
):
    try:
        organization_unit_id = int(
            request.organization_unit_id
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "子任务目标水管所 ID 无效。"
        ) from error

    scope_uids = []

    for raw_uid in (
        request.management_scope_uids
        or ()
    ):
        uid = _clean_text(
            raw_uid
        )

        if not uid:
            raise ValueError(
                "子任务包含无效分管范围 UID。"
            )

        if uid not in scope_uids:
            scope_uids.append(
                uid
            )

    if not scope_uids:
        raise ValueError(
            "子任务至少需要选择一个分管范围。"
        )

    task_name = _require_text(
        request.task_name,
        "子任务名称",
    )

    return {
        "organization_unit_id": (
            organization_unit_id
        ),
        "management_scope_uids": tuple(
            scope_uids
        ),
        "task_name": task_name,
        "notes": _clean_text(
            request.notes
        ),
        "output_path": (
            normalize_task_package_path(
                request.output_path
            )
        ),
    }


def _load_parent_workspace():
    workspace = (
        get_current_task_workspace()
    )

    if workspace is None:
        raise ValueError(
            "当前没有已接收的父任务工作区。"
        )

    if (
        _clean_text(
            workspace.get(
                "target_unit_type"
            )
        )
        != "department"
    ):
        raise ValueError(
            "只有基层处任务工作区可以继续派生所级子任务。"
        )

    parent_task_uid = _require_text(
        workspace.get(
            "task_uid"
        ),
        "父任务 task_uid",
    )

    root_task_uid = (
        _clean_text(
            workspace.get(
                "root_task_uid"
            )
        )
        or parent_task_uid
    )

    try:
        parent_depth = int(
            workspace.get(
                "task_depth"
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "父任务 task_depth 无效。"
        ) from error

    if parent_depth < 0:
        raise ValueError(
            "父任务 task_depth 无效。"
        )

    managed_path = Path(
        workspace[
            "managed_package_path"
        ]
    )

    if not managed_path.exists():
        raise FileNotFoundError(
            "当前父任务托管包不存在，"
            "不能继续派生子任务。"
        )

    parent_contents = (
        load_survey_task_package(
            managed_path
        )
    )

    if (
        _require_text(
            parent_contents.task.get(
                "task_uid"
            ),
            "父任务包 task_uid",
        )
        != parent_task_uid
    ):
        raise ValueError(
            "当前工作区与托管父任务包身份不一致。"
        )

    return (
        workspace,
        parent_contents,
        parent_task_uid,
        root_task_uid,
        parent_depth,
    )


def _load_target_office(
    workspace,
    organization_unit_id,
):
    department_id = int(
        workspace[
            "organization_unit_id"
        ]
    )

    with database.get_connection() as connection:
        office = connection.execute(
            """
            SELECT
                id,
                organization_unit_uid,
                parent_id,
                name,
                unit_type,
                status
            FROM organization_units
            WHERE id = ?
            """,
            (
                int(
                    organization_unit_id
                ),
            ),
        ).fetchone()

    if office is None:
        raise ValueError(
            "没有找到子任务目标水管所。"
        )

    if (
        office[
            "unit_type"
        ]
        != "water_office"
        or office[
            "status"
        ]
        != "active"
    ):
        raise ValueError(
            "子任务只能分配给当前启用的水管所。"
        )

    if int(
        office[
            "parent_id"
        ]
        or 0
    ) != department_id:
        raise ValueError(
            "子任务目标水管所不属于当前父任务基层处。"
        )

    return dict(
        office
    )


def _select_authorized_scopes(
    workspace,
    parent_contents,
    *,
    office_uid,
    selected_uids,
):
    workspace_scopes = {
        _require_text(
            item.get(
                "management_scope_uid"
            ),
            "父任务 scope UID",
        ): item
        for item in (
            workspace.get(
                "management_scopes"
            )
            or ()
        )
    }

    requested = set(
        selected_uids
    )

    missing = (
        requested
        - set(
            workspace_scopes
        )
    )

    if missing:
        raise ValueError(
            "子任务分管范围必须完全来自父任务冻结范围；"
            "发现越权 scope："
            + "、".join(
                sorted(
                    missing
                )
            )
        )

    wrong_owner = [
        uid
        for uid in selected_uids
        if _clean_text(
            workspace_scopes[
                uid
            ].get(
                "organization_unit_uid"
            )
        )
        != office_uid
    ]

    if wrong_owner:
        raise ValueError(
            "子任务只能包含目标水管所自己的父任务分管范围；"
            "发现跨所 scope："
            + "、".join(
                wrong_owner
            )
        )

    parent_scope_by_uid = {
        _require_text(
            item.get(
                "management_scope_uid"
            ),
            "父任务包 scope UID",
        ): item
        for item in (
            parent_contents.management_scopes
        )
    }

    result = []

    for uid in selected_uids:
        item = (
            parent_scope_by_uid.get(
                uid
            )
        )

        if item is None:
            raise ValueError(
                "父任务工作区与托管任务包的"
                "分管范围快照不一致："
                f"{uid}。"
            )

        if (
            _clean_text(
                item.get(
                    "organization_unit_uid"
                )
            )
            != office_uid
        ):
            raise ValueError(
                "父任务托管包中的 scope owner "
                "与目标水管所不一致。"
            )

        result.append(
            dict(
                item
            )
        )

    return tuple(
        result
    )


def _filter_organization_reference(
    parent_contents,
    *,
    department_uid,
    office_uid,
):
    by_uid = {
        _require_text(
            item.get(
                "organization_uid"
            ),
            "organization reference UID",
        ): dict(
            item
        )
        for item in (
            parent_contents.organizations
        )
    }

    department = by_uid.get(
        department_uid
    )
    office = by_uid.get(
        office_uid
    )

    if department is None:
        raise ValueError(
            "父任务包缺少基层处组织快照。"
        )

    if office is None:
        raise ValueError(
            "父任务包缺少目标水管所组织快照。"
        )

    if (
        office.get(
            "parent_organization_uid"
        )
        != department_uid
    ):
        raise ValueError(
            "父任务包中的水管所与基层处"
            "冻结关系不一致。"
        )

    return (
        dict(
            department
        ),
        dict(
            office
        ),
    )


def _filter_canal_reference(
    parent_contents,
    selected_scopes,
):
    canal_by_uid = {
        _require_text(
            item.get(
                "canal_uid"
            ),
            "canal reference UID",
        ): dict(
            item
        )
        for item in (
            parent_contents.canals
        )
    }

    needed = set()

    for scope in selected_scopes:
        current_uid = _require_text(
            scope.get(
                "canal_uid"
            ),
            "scope canal_uid",
        )

        visited = set()

        while current_uid:
            if current_uid in visited:
                raise ValueError(
                    "父任务渠系参考存在循环引用。"
                )

            visited.add(
                current_uid
            )
            needed.add(
                current_uid
            )

            current = (
                canal_by_uid.get(
                    current_uid
                )
            )

            if current is None:
                raise ValueError(
                    "父任务包缺少子任务 scope "
                    "对应的渠系参考："
                    f"{current_uid}。"
                )

            parent_uid = _clean_text(
                current.get(
                    "parent_canal_uid"
                )
            )

            current_uid = (
                parent_uid
                or None
            )

    result = [
        dict(
            item
        )
        for item in (
            parent_contents.canals
        )
        if _clean_text(
            item.get(
                "canal_uid"
            )
        )
        in needed
    ]

    if not result:
        raise ValueError(
            "子任务没有可用的渠系参考。"
        )

    return tuple(
        result
    )


def export_child_survey_task_package(
    request,
):
    """
    从当前处级父任务冻结工作区派生所级子任务。

    权限边界：
    1. 当前 workspace 必须是 department；
    2. child scope UID 必须属于 parent frozen scopes；
    3. child scope owner 必须等于目标 water_office；
    4. 子任务使用父任务包中的冻结 scope / canal /
       organization / form reference，不重新读取 current CMS。
    """
    integrity = (
        check_master_data_integrity()
    )

    if not integrity.passed:
        raise ValueError(
            "正式主数据一致性检查未通过，"
            "不能生成所级子任务。"
        )

    normalized = _normalize_request(
        request
    )

    (
        workspace,
        parent_contents,
        parent_task_uid,
        root_task_uid,
        parent_depth,
    ) = _load_parent_workspace()

    office = _load_target_office(
        workspace,
        normalized[
            "organization_unit_id"
        ],
    )

    office_uid = _require_text(
        office[
            "organization_unit_uid"
        ],
        "目标水管所 UID",
    )

    parent_task = (
        parent_contents.task
    )

    assignment = (
        parent_task.get(
            "assignment"
        )
        if isinstance(
            parent_task.get(
                "assignment"
            ),
            dict,
        )
        else {}
    )

    department_uid = _require_text(
        assignment.get(
            "department_uid"
        ),
        "父任务 department_uid",
    )

    department_name = _require_text(
        assignment.get(
            "department_name"
        ),
        "父任务 department_name",
    )

    selected_scopes = (
        _select_authorized_scopes(
            workspace,
            parent_contents,
            office_uid=office_uid,
            selected_uids=(
                normalized[
                    "management_scope_uids"
                ]
            ),
        )
    )

    organizations = (
        _filter_organization_reference(
            parent_contents,
            department_uid=(
                department_uid
            ),
            office_uid=office_uid,
        )
    )

    canals = (
        _filter_canal_reference(
            parent_contents,
            selected_scopes,
        )
    )

    task_uid = new_stable_token()
    package_uid = new_stable_token()

    lineage = (
        build_child_task_lineage(
            task_uid=task_uid,
            parent_task_uid=(
                parent_task_uid
            ),
            root_task_uid=(
                root_task_uid
            ),
            parent_depth=(
                parent_depth
            ),
        )
    )

    created_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    project = parent_task.get(
        "project"
    )
    survey_batch = (
        parent_task.get(
            "survey_batch"
        )
    )

    if not isinstance(
        project,
        dict,
    ):
        raise ValueError(
            "父任务 project 结构无效。"
        )

    if not isinstance(
        survey_batch,
        dict,
    ):
        raise ValueError(
            "父任务 survey_batch 结构无效。"
        )

    project_uid = _require_text(
        project.get(
            "project_uid"
        ),
        "project_uid",
    )

    batch_uid = _require_text(
        survey_batch.get(
            "survey_batch_uid"
        ),
        "survey_batch_uid",
    )

    selected_scope_uids = [
        _require_text(
            item.get(
                "management_scope_uid"
            ),
            "management_scope_uid",
        )
        for item in selected_scopes
    ]

    office_reference = (
        organizations[
            1
        ]
    )

    task_data = {
        "task_schema_version": (
            CURRENT_TASK_SCHEMA_VERSION
        ),
        "task_uid": task_uid,
        "lineage": (
            lineage.as_dict()
        ),
        "task_name": (
            normalized[
                "task_name"
            ]
        ),
        "notes": (
            normalized[
                "notes"
            ]
            or None
        ),
        "project": dict(
            project
        ),
        "survey_batch": dict(
            survey_batch
        ),
        "assignment": {
            "target_unit_type": (
                "water_office"
            ),
            "department_uid": (
                department_uid
            ),
            "department_name": (
                department_name
            ),
            "organization_unit_uid": (
                office_uid
            ),
            "organization_name": (
                _require_text(
                    office_reference.get(
                        "name"
                    ),
                    "目标水管所名称",
                )
            ),
        },
        "scope": {
            "selected_management_scope_uids": (
                selected_scope_uids
            ),
            "selected_management_scope_count": (
                len(
                    selected_scope_uids
                )
            ),
        },
        "created_at": created_at,
    }

    payload_files = {
        "task.json": (
            encode_json_bytes(
                task_data
            )
        ),
        "reference/organization_units.json": (
            encode_json_bytes(
                {
                    "items": list(
                        organizations
                    )
                }
            )
        ),
        "reference/canal_units.json": (
            encode_json_bytes(
                {
                    "items": list(
                        canals
                    )
                }
            )
        ),
        "reference/canal_management_scopes.json": (
            encode_json_bytes(
                {
                    "items": list(
                        selected_scopes
                    )
                }
            )
        ),
        "reference/forms.json": (
            encode_json_bytes(
                {
                    "items": [
                        dict(
                            item
                        )
                        for item in (
                            parent_contents.forms
                        )
                    ]
                }
            )
        ),
    }

    manifest = {
        "package_kind": (
            SURVEY_TASK_PACKAGE_KIND
        ),
        "task_schema_version": (
            CURRENT_TASK_SCHEMA_VERSION
        ),
        "created_at": created_at,
        "app_version": APP_VERSION,
        "app_version_label": (
            APP_VERSION_LABEL
        ),
        "task_uid": task_uid,
        "parent_task_uid": (
            lineage.parent_task_uid
        ),
        "root_task_uid": (
            lineage.root_task_uid
        ),
        "task_depth": (
            lineage.depth
        ),
        "project_uid": (
            project_uid
        ),
        "survey_batch_uid": (
            batch_uid
        ),
    }

    write_result = (
        write_package(
            normalized[
                "output_path"
            ],
            package_uid=package_uid,
            manifest=manifest,
            payload_files=(
                payload_files
            ),
        )
    )

    try:
        record_issued_survey_task(
            package_uid=package_uid,
            manifest=manifest,
            task_document=(
                task_data
            ),
            management_scopes=(
                selected_scopes
            ),
            canal_units=canals,
            organization_units=(
                organizations
            ),
        )

    except Exception:
        try:
            write_result.output_path.unlink(
                missing_ok=True
            )
        except Exception as cleanup_error:
            raise RuntimeError(
                "所级子任务包已经生成，"
                "但下发历史保存失败，"
                "且未登记任务包无法自动删除："
                f"{write_result.output_path}。"
                "请勿分发该任务包。"
            ) from cleanup_error

        raise

    return ChildSurveyTaskExportResult(
        output_path=(
            write_result.output_path
        ),
        package_uid=package_uid,
        task_uid=task_uid,
        parent_task_uid=(
            parent_task_uid
        ),
        root_task_uid=(
            lineage.root_task_uid
        ),
        task_depth=(
            lineage.depth
        ),
        organization_name=(
            _require_text(
                office_reference.get(
                    "name"
                ),
                "目标水管所名称",
            )
        ),
        selected_management_scope_count=(
            len(
                selected_scope_uids
            )
        ),
    )
