from __future__ import annotations

from dataclasses import dataclass


LEGACY_TASK_SCHEMA_VERSION = "2.0"
CURRENT_TASK_SCHEMA_VERSION = "3.0"

SUPPORTED_TASK_SCHEMA_VERSIONS = frozenset(
    {
        LEGACY_TASK_SCHEMA_VERSION,
        CURRENT_TASK_SCHEMA_VERSION,
    }
)


@dataclass(frozen=True)
class SurveyTaskLineage:
    parent_task_uid: str | None
    root_task_uid: str
    depth: int

    @property
    def is_root(self):
        return self.parent_task_uid is None

    def as_dict(self):
        return {
            "parent_task_uid": self.parent_task_uid,
            "root_task_uid": self.root_task_uid,
            "depth": self.depth,
        }


def _clean_text(value):
    return str(value or "").strip()


def _required_text(value, field_name):
    value = _clean_text(value)
    if not value:
        raise ValueError(
            f"{field_name}不能为空。"
        )
    return value


def _optional_text(value):
    value = _clean_text(value)
    return value or None


def build_root_task_lineage(task_uid):
    task_uid = _required_text(
        task_uid,
        "task_uid",
    )

    return SurveyTaskLineage(
        parent_task_uid=None,
        root_task_uid=task_uid,
        depth=0,
    )


def build_child_task_lineage(
    *,
    task_uid,
    parent_task_uid,
    root_task_uid,
    parent_depth,
):
    # Stage 4.1 只建立血缘合同，不负责真正生成子任务。
    task_uid = _required_text(
        task_uid,
        "task_uid",
    )
    parent_task_uid = _required_text(
        parent_task_uid,
        "parent_task_uid",
    )
    root_task_uid = _required_text(
        root_task_uid,
        "root_task_uid",
    )

    if task_uid == parent_task_uid:
        raise ValueError(
            "子任务不能把自身作为 parent_task_uid。"
        )

    if task_uid == root_task_uid:
        raise ValueError(
            "子任务的 root_task_uid 不能指向自身。"
        )

    try:
        parent_depth = int(parent_depth)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "parent_depth 必须是非负整数。"
        ) from error

    if parent_depth < 0:
        raise ValueError(
            "parent_depth 必须是非负整数。"
        )

    return SurveyTaskLineage(
        parent_task_uid=parent_task_uid,
        root_task_uid=root_task_uid,
        depth=parent_depth + 1,
    )


def normalize_task_lineage(
    task_document,
    *,
    manifest=None,
):
    # task schema 2.0 统一解释为 root task；
    # task schema 3.0 必须显式携带 lineage。
    if not isinstance(task_document, dict):
        raise ValueError(
            "task_document 必须是对象。"
        )

    task_uid = _required_text(
        task_document.get("task_uid"),
        "task_uid",
    )

    schema_version = _required_text(
        task_document.get(
            "task_schema_version"
        ),
        "task_schema_version",
    )

    if schema_version not in SUPPORTED_TASK_SCHEMA_VERSIONS:
        raise ValueError(
            "不支持的 task_schema_version："
            f"{schema_version}。"
        )

    if schema_version == LEGACY_TASK_SCHEMA_VERSION:
        lineage = build_root_task_lineage(
            task_uid
        )

    else:
        raw = task_document.get(
            "lineage"
        )

        if not isinstance(raw, dict):
            raise ValueError(
                "task schema 3.0 必须包含 lineage 对象。"
            )

        parent_task_uid = _optional_text(
            raw.get("parent_task_uid")
        )

        root_task_uid = _required_text(
            raw.get("root_task_uid"),
            "lineage.root_task_uid",
        )

        depth = raw.get("depth")

        if (
            isinstance(depth, bool)
            or not isinstance(depth, int)
            or depth < 0
        ):
            raise ValueError(
                "lineage.depth 必须是非负整数。"
            )

        if parent_task_uid is None:
            if depth != 0:
                raise ValueError(
                    "根任务 lineage.depth 必须为 0。"
                )

            if root_task_uid != task_uid:
                raise ValueError(
                    "根任务 root_task_uid 必须等于 task_uid。"
                )

        else:
            if depth < 1:
                raise ValueError(
                    "子任务 lineage.depth 必须至少为 1。"
                )

            if parent_task_uid == task_uid:
                raise ValueError(
                    "子任务不能把自身作为 parent_task_uid。"
                )

            if root_task_uid == task_uid:
                raise ValueError(
                    "子任务 root_task_uid 不能指向自身。"
                )

        lineage = SurveyTaskLineage(
            parent_task_uid=parent_task_uid,
            root_task_uid=root_task_uid,
            depth=depth,
        )

    if manifest is not None:
        if not isinstance(manifest, dict):
            raise ValueError(
                "manifest 必须是对象。"
            )

        manifest_schema = _required_text(
            manifest.get(
                "task_schema_version"
            ),
            "manifest.task_schema_version",
        )

        if manifest_schema != schema_version:
            raise ValueError(
                "manifest 与 task.json 的 "
                "task_schema_version 不一致。"
            )

        if schema_version == CURRENT_TASK_SCHEMA_VERSION:
            manifest_parent = _optional_text(
                manifest.get(
                    "parent_task_uid"
                )
            )
            manifest_root = _required_text(
                manifest.get(
                    "root_task_uid"
                ),
                "manifest.root_task_uid",
            )
            manifest_depth = manifest.get(
                "task_depth"
            )

            if (
                manifest_parent != lineage.parent_task_uid
                or manifest_root != lineage.root_task_uid
                or manifest_depth != lineage.depth
            ):
                raise ValueError(
                    "manifest 与 task.json 的任务血缘不一致。"
                )

    return lineage
