from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence


_ALLOWED_RECORD_STATUSES = (
    "draft",
    "completed",
    "void",
)


def _unique_int_tuple(
    values,
    *,
    field_name,
):
    result = []

    for value in values or ():
        try:
            normalized = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{field_name} 必须是正整数。"
            ) from error

        if normalized <= 0:
            raise ValueError(
                f"{field_name} 必须是正整数。"
            )

        if normalized not in result:
            result.append(normalized)

    return tuple(result)


def _unique_text_tuple(values):
    result = []

    for value in values or ():
        normalized = str(value or "").strip()

        if not normalized:
            continue

        if normalized not in result:
            result.append(normalized)

    return tuple(result)


def _row_value(
    row,
    key,
):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            f"范围解析所需字段不存在：{key}"
        ) from error


@dataclass(frozen=True)
class SurveyScope:
    """
    调查范围的纯业务表达。

    约定：
    - project_id / survey_batch_id 必填；
    - organization_unit_ids / canal_unit_ids 为空表示“不限制”；
    - form_codes 为空表示“全部工程调查表”；
    - 正式成果场景默认只取 completed；
    - 是否包含下级节点由各自 include_*_descendants 控制。

    本对象只描述“范围”，不负责数据库查询、Qt 页面或导出。
    """

    project_id: int
    survey_batch_id: int

    organization_unit_ids: tuple[int, ...] = ()
    canal_unit_ids: tuple[int, ...] = ()

    form_codes: tuple[str, ...] = ()
    record_statuses: tuple[str, ...] = (
        "completed",
    )

    include_organization_descendants: bool = True
    include_canal_descendants: bool = True

    def __post_init__(self):
        try:
            project_id = int(self.project_id)
            survey_batch_id = int(
                self.survey_batch_id
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "项目和调查批次必须使用有效ID。"
            ) from error

        if project_id <= 0:
            raise ValueError(
                "project_id 必须是正整数。"
            )

        if survey_batch_id <= 0:
            raise ValueError(
                "survey_batch_id 必须是正整数。"
            )

        organization_unit_ids = (
            _unique_int_tuple(
                self.organization_unit_ids,
                field_name=(
                    "organization_unit_ids"
                ),
            )
        )

        canal_unit_ids = _unique_int_tuple(
            self.canal_unit_ids,
            field_name="canal_unit_ids",
        )

        form_codes = _unique_text_tuple(
            self.form_codes
        )

        record_statuses = _unique_text_tuple(
            self.record_statuses
        )

        if not record_statuses:
            raise ValueError(
                "record_statuses 不能为空。"
            )

        invalid_statuses = tuple(
            status
            for status in record_statuses
            if status not in (
                _ALLOWED_RECORD_STATUSES
            )
        )

        if invalid_statuses:
            raise ValueError(
                "调查记录状态无效："
                + "、".join(invalid_statuses)
            )

        object.__setattr__(
            self,
            "project_id",
            project_id,
        )
        object.__setattr__(
            self,
            "survey_batch_id",
            survey_batch_id,
        )
        object.__setattr__(
            self,
            "organization_unit_ids",
            organization_unit_ids,
        )
        object.__setattr__(
            self,
            "canal_unit_ids",
            canal_unit_ids,
        )
        object.__setattr__(
            self,
            "form_codes",
            form_codes,
        )
        object.__setattr__(
            self,
            "record_statuses",
            record_statuses,
        )


@dataclass(frozen=True)
class ResolvedSurveyScope:
    """
    已把组织/渠系根节点展开后的调查范围。

    None 表示该维度“不限制”；
    frozenset 表示允许匹配的具体节点ID集合。
    """

    scope: SurveyScope

    organization_unit_ids: (
        Optional[frozenset[int]]
    )
    canal_unit_ids: (
        Optional[frozenset[int]]
    )


def resolve_descendant_ids(
    rows,
    root_ids,
    *,
    include_descendants=True,
):
    """
    在任意 id / parent_id 树结构中展开根节点。

    返回值始终包含根节点本身。
    若 include_descendants=False，
    则只返回根节点。

    该函数不依赖 SQLite，后续组织树、渠系树、
    任务包和成果导出均可复用。
    """

    normalized_roots = _unique_int_tuple(
        root_ids,
        field_name="root_ids",
    )

    if not normalized_roots:
        return frozenset()

    node_ids = set()
    children_by_parent = {}

    for row in rows:
        node_id = int(
            _row_value(
                row,
                "id",
            )
        )

        parent_id = _row_value(
            row,
            "parent_id",
        )

        if parent_id is not None:
            parent_id = int(parent_id)

        node_ids.add(node_id)

        children_by_parent.setdefault(
            parent_id,
            [],
        ).append(node_id)

    missing_roots = tuple(
        root_id
        for root_id in normalized_roots
        if root_id not in node_ids
    )

    if missing_roots:
        raise ValueError(
            "调查范围中的基础资料节点不存在："
            + "、".join(
                str(value)
                for value in missing_roots
            )
        )

    if not include_descendants:
        return frozenset(
            normalized_roots
        )

    resolved = set(normalized_roots)
    pending = list(normalized_roots)

    while pending:
        current_id = pending.pop()

        for child_id in (
            children_by_parent.get(
                current_id,
                (),
            )
        ):
            if child_id in resolved:
                continue

            resolved.add(child_id)
            pending.append(child_id)

    return frozenset(resolved)


def resolve_survey_scope(
    scope,
    *,
    organization_rows=(),
    canal_rows=(),
):
    """
    将 SurveyScope 中选定的组织/渠系根节点
    展开为实际可匹配节点集合。
    """

    if not isinstance(
        scope,
        SurveyScope,
    ):
        raise TypeError(
            "scope 必须是 SurveyScope。"
        )

    if scope.organization_unit_ids:
        resolved_organization_ids = (
            resolve_descendant_ids(
                organization_rows,
                scope.organization_unit_ids,
                include_descendants=(
                    scope
                    .include_organization_descendants
                ),
            )
        )
    else:
        resolved_organization_ids = None

    if scope.canal_unit_ids:
        resolved_canal_ids = (
            resolve_descendant_ids(
                canal_rows,
                scope.canal_unit_ids,
                include_descendants=(
                    scope
                    .include_canal_descendants
                ),
            )
        )
    else:
        resolved_canal_ids = None

    return ResolvedSurveyScope(
        scope=scope,
        organization_unit_ids=(
            resolved_organization_ids
        ),
        canal_unit_ids=(
            resolved_canal_ids
        ),
    )


def record_matches_scope(
    record,
    resolved_scope,
):
    """
    判断一条工程调查公共记录是否属于范围。

    record 只要求暴露后续成果导出真正需要的公共键：
    project_id、survey_batch_id、organization_unit_id、
    canal_unit_id、form_code、record_status。
    """

    if not isinstance(
        resolved_scope,
        ResolvedSurveyScope,
    ):
        raise TypeError(
            "resolved_scope 必须是 "
            "ResolvedSurveyScope。"
        )

    scope = resolved_scope.scope

    if int(record["project_id"]) != (
        scope.project_id
    ):
        return False

    if int(record["survey_batch_id"]) != (
        scope.survey_batch_id
    ):
        return False

    if (
        scope.form_codes
        and record["form_code"]
        not in scope.form_codes
    ):
        return False

    if record["record_status"] not in (
        scope.record_statuses
    ):
        return False

    if (
        resolved_scope.organization_unit_ids
        is not None
    ):
        organization_unit_id = record[
            "organization_unit_id"
        ]

        if (
            organization_unit_id is None
            or int(organization_unit_id)
            not in (
                resolved_scope
                .organization_unit_ids
            )
        ):
            return False

    if (
        resolved_scope.canal_unit_ids
        is not None
    ):
        canal_unit_id = record[
            "canal_unit_id"
        ]

        if (
            canal_unit_id is None
            or int(canal_unit_id)
            not in (
                resolved_scope
                .canal_unit_ids
            )
        ):
            return False

    return True


def filter_records_by_scope(
    records,
    resolved_scope,
):
    """
    过滤工程调查公共记录。

    保持输入顺序不变，便于后续沿用数据库既有排序。
    """

    return tuple(
        record
        for record in records
        if record_matches_scope(
            record,
            resolved_scope,
        )
    )
