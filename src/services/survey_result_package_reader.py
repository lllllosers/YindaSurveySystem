from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from services.survey_result_package import SURVEY_RESULT_PACKAGE_KIND
from services.yd_package_reader import (
    PackageInspectionIssue,
    SEVERITY_ERROR,
    inspect_package,
    read_json_file_from_valid_package,
)


MAX_RESULT_FILE_COUNT = 100_000
MAX_RESULT_SINGLE_FILE_BYTES = 8 * 1024 * 1024 * 1024
MAX_RESULT_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024 * 1024

_REQUIRED_RESULT_FILES = (
    "result.json",
    "data/engineering_assets.json",
    "data/survey_records.json",
    "data/inspection_results.json",
    "data/survey_media.json",
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SurveyResultPackageContents:
    package_path: Path
    manifest: dict
    result: dict
    engineering_assets: tuple[dict, ...]
    survey_records: tuple[dict, ...]
    inspection_results: tuple[dict, ...]
    survey_media: tuple[dict, ...]


@dataclass(frozen=True)
class SurveyResultPackageInspection:
    package_path: Path
    manifest: dict | None
    result: dict | None
    engineering_assets: tuple[dict, ...]
    survey_records: tuple[dict, ...]
    inspection_results: tuple[dict, ...]
    survey_media: tuple[dict, ...]
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
            f"调查成果包：{self.package_path}",
            f"检查结果：{self.error_count} 个错误",
        ]

        if self.result:
            name = self.result.get("result_name")
            if name:
                lines.append(f"成果名称：{name}")

            counts = self.result.get("counts")
            if isinstance(counts, dict):
                lines.append(
                    "调查记录："
                    f"{counts.get('survey_records', 0)} 条，"
                    "影像："
                    f"{counts.get('survey_media', 0)} 个"
                )

        if not self.issues:
            lines.append("未发现问题。")
        else:
            for issue in self.issues:
                suffix = f" [{issue.path}]" if issue.path else ""
                lines.append(
                    f"[错误] {issue.code}：{issue.message}{suffix}"
                )

        return "\n".join(lines)


def _append(issues, code, message, *, path=""):
    issues.append(
        PackageInspectionIssue(
            severity=SEVERITY_ERROR,
            code=code,
            message=message,
            path=path,
        )
    )


def _require_text(value, issues, code, message, *, path=""):
    if not isinstance(value, str) or not value.strip():
        _append(
            issues,
            code,
            message,
            path=path,
        )
        return None
    return value.strip()


def _read_items(package_path, logical_path, issues):
    try:
        document = read_json_file_from_valid_package(
            package_path,
            logical_path,
        )
    except Exception:
        _append(
            issues,
            "RESULT_DATA_JSON_INVALID",
            "成果数据文件无法读取。",
            path=logical_path,
        )
        return ()

    items = document.get("items")

    if not isinstance(items, list):
        _append(
            issues,
            "RESULT_ITEMS_INVALID",
            "成果数据 items 必须是数组。",
            path=logical_path,
        )
        return ()

    result = []

    for item in items:
        if not isinstance(item, dict):
            _append(
                issues,
                "RESULT_ITEM_INVALID",
                "成果数据项必须是对象。",
                path=logical_path,
            )
            continue
        result.append(dict(item))

    return tuple(result)


def _manifest_files(manifest):
    result = {}

    for item in manifest.get("files") or []:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if isinstance(path, str):
            result[path] = item

    return result


def inspect_survey_result_package(package_path):
    """
    只读检查 .ydresult。
    不解压到磁盘，不修改数据库，不执行导入。
    """

    package_path = Path(package_path)

    generic = inspect_package(
        package_path,
        expected_kind=SURVEY_RESULT_PACKAGE_KIND,
        max_file_count=MAX_RESULT_FILE_COUNT,
        max_single_file_bytes=MAX_RESULT_SINGLE_FILE_BYTES,
        max_total_uncompressed_bytes=MAX_RESULT_TOTAL_UNCOMPRESSED_BYTES,
    )

    issues = list(generic.issues)

    if not generic.valid:
        return SurveyResultPackageInspection(
            package_path=package_path,
            manifest=generic.manifest,
            result=None,
            engineering_assets=(),
            survey_records=(),
            inspection_results=(),
            survey_media=(),
            issues=tuple(issues),
        )

    manifest = generic.manifest or {}
    manifest_files = _manifest_files(manifest)

    for path in _REQUIRED_RESULT_FILES:
        if path not in manifest_files:
            _append(
                issues,
                "RESULT_FILE_NOT_DECLARED",
                "调查成果包缺少必需文件的 manifest 声明。",
                path=path,
            )

    if issues:
        return SurveyResultPackageInspection(
            package_path=package_path,
            manifest=manifest,
            result=None,
            engineering_assets=(),
            survey_records=(),
            inspection_results=(),
            survey_media=(),
            issues=tuple(issues),
        )

    try:
        result_document = read_json_file_from_valid_package(
            package_path,
            "result.json",
        )
    except Exception:
        _append(
            issues,
            "RESULT_JSON_INVALID",
            "result.json 无法读取。",
            path="result.json",
        )
        result_document = None

    assets = _read_items(
        package_path,
        "data/engineering_assets.json",
        issues,
    )
    records = _read_items(
        package_path,
        "data/survey_records.json",
        issues,
    )
    inspections = _read_items(
        package_path,
        "data/inspection_results.json",
        issues,
    )
    media = _read_items(
        package_path,
        "data/survey_media.json",
        issues,
    )

    if result_document is None:
        return SurveyResultPackageInspection(
            package_path=package_path,
            manifest=manifest,
            result=None,
            engineering_assets=assets,
            survey_records=records,
            inspection_results=inspections,
            survey_media=media,
            issues=tuple(issues),
        )

    # 顶层 UID 一致性
    result_uid = _require_text(
        result_document.get("result_uid"),
        issues,
        "RESULT_UID_INVALID",
        "result.json 缺少有效 result_uid。",
        path="result.json",
    )
    manifest_result_uid = _require_text(
        manifest.get("result_uid"),
        issues,
        "MANIFEST_RESULT_UID_INVALID",
        "manifest 缺少有效 result_uid。",
        path="manifest.json",
    )
    if (
        result_uid
        and manifest_result_uid
        and result_uid != manifest_result_uid
    ):
        _append(
            issues,
            "RESULT_UID_MISMATCH",
            "manifest 与 result.json 的 result_uid 不一致。",
        )

    project = result_document.get("project")
    project_uid = None
    if isinstance(project, dict):
        project_uid = _require_text(
            project.get("project_uid"),
            issues,
            "RESULT_PROJECT_UID_INVALID",
            "result.project 缺少 project_uid。",
            path="result.json",
        )
    else:
        _append(
            issues,
            "RESULT_PROJECT_INVALID",
            "result.project 必须是对象。",
            path="result.json",
        )

    manifest_project_uid = _require_text(
        manifest.get("project_uid"),
        issues,
        "MANIFEST_PROJECT_UID_INVALID",
        "manifest 缺少 project_uid。",
        path="manifest.json",
    )
    if (
        project_uid
        and manifest_project_uid
        and project_uid != manifest_project_uid
    ):
        _append(
            issues,
            "RESULT_PROJECT_UID_MISMATCH",
            "manifest 与 result.json 的 project_uid 不一致。",
        )

    batch = result_document.get("survey_batch")
    batch_uid = None
    if isinstance(batch, dict):
        batch_uid = _require_text(
            batch.get("survey_batch_uid"),
            issues,
            "RESULT_BATCH_UID_INVALID",
            "result.survey_batch 缺少 survey_batch_uid。",
            path="result.json",
        )
    else:
        _append(
            issues,
            "RESULT_BATCH_INVALID",
            "result.survey_batch 必须是对象。",
            path="result.json",
        )

    manifest_batch_uid = _require_text(
        manifest.get("survey_batch_uid"),
        issues,
        "MANIFEST_BATCH_UID_INVALID",
        "manifest 缺少 survey_batch_uid。",
        path="manifest.json",
    )
    if (
        batch_uid
        and manifest_batch_uid
        and batch_uid != manifest_batch_uid
    ):
        _append(
            issues,
            "RESULT_BATCH_UID_MISMATCH",
            "manifest 与 result.json 的 survey_batch_uid 不一致。",
        )

    if (
        manifest.get("source_task_uid")
        != result_document.get("source_task_uid")
    ):
        _append(
            issues,
            "SOURCE_TASK_UID_MISMATCH",
            "manifest 与 result.json 的 source_task_uid 不一致。",
        )

    # 工程对象
    asset_by_uid = {}

    for item in assets:
        uid = _require_text(
            item.get("engineering_asset_uid"),
            issues,
            "RESULT_ASSET_UID_INVALID",
            "工程对象缺少 engineering_asset_uid。",
            path="data/engineering_assets.json",
        )

        if not uid:
            continue

        if uid in asset_by_uid:
            _append(
                issues,
                "RESULT_ASSET_UID_DUPLICATE",
                "工程对象包含重复 engineering_asset_uid。",
                path="data/engineering_assets.json",
            )
            continue

        asset_by_uid[uid] = item

        if project_uid and item.get("project_uid") != project_uid:
            _append(
                issues,
                "RESULT_ASSET_PROJECT_MISMATCH",
                "工程对象 project_uid 与成果包项目不一致。",
                path="data/engineering_assets.json",
            )

    # 调查记录
    record_by_uid = {}
    referenced_asset_uids = set()

    for item in records:
        uid = _require_text(
            item.get("survey_record_uid"),
            issues,
            "RESULT_RECORD_UID_INVALID",
            "调查记录缺少 survey_record_uid。",
            path="data/survey_records.json",
        )

        if not uid:
            continue

        if uid in record_by_uid:
            _append(
                issues,
                "RESULT_RECORD_UID_DUPLICATE",
                "调查记录包含重复 survey_record_uid。",
                path="data/survey_records.json",
            )
            continue

        record_by_uid[uid] = item

        if project_uid and item.get("project_uid") != project_uid:
            _append(
                issues,
                "RESULT_RECORD_PROJECT_MISMATCH",
                "调查记录 project_uid 与成果包项目不一致。",
                path="data/survey_records.json",
            )

        if batch_uid and item.get("survey_batch_uid") != batch_uid:
            _append(
                issues,
                "RESULT_RECORD_BATCH_MISMATCH",
                "调查记录 survey_batch_uid 与成果包批次不一致。",
                path="data/survey_records.json",
            )

        if item.get("record_type") != "engineering":
            _append(
                issues,
                "RESULT_RECORD_TYPE_INVALID",
                "成果包当前只允许 engineering 调查记录。",
                path="data/survey_records.json",
            )

        if item.get("record_status") != "completed":
            _append(
                issues,
                "RESULT_RECORD_STATUS_INVALID",
                "成果包中的调查记录必须为 completed。",
                path="data/survey_records.json",
            )

        asset_uid = _require_text(
            item.get("engineering_asset_uid"),
            issues,
            "RESULT_RECORD_ASSET_UID_INVALID",
            "调查记录缺少 engineering_asset_uid。",
            path="data/survey_records.json",
        )

        if asset_uid:
            referenced_asset_uids.add(asset_uid)
            if asset_uid not in asset_by_uid:
                _append(
                    issues,
                    "RESULT_RECORD_ASSET_MISSING",
                    "调查记录引用的工程对象不在成果包中。",
                    path="data/survey_records.json",
                )

        _require_text(
            item.get("organization_unit_uid"),
            issues,
            "RESULT_RECORD_ORGANIZATION_UID_INVALID",
            "调查记录缺少 organization_unit_uid。",
            path="data/survey_records.json",
        )
        _require_text(
            item.get("canal_unit_uid"),
            issues,
            "RESULT_RECORD_CANAL_UID_INVALID",
            "调查记录缺少 canal_unit_uid。",
            path="data/survey_records.json",
        )

        form = item.get("form")
        if not isinstance(form, dict):
            _append(
                issues,
                "RESULT_RECORD_FORM_INVALID",
                "调查记录 form 必须是对象。",
                path="data/survey_records.json",
            )
        else:
            _require_text(
                form.get("form_code"),
                issues,
                "RESULT_RECORD_FORM_CODE_INVALID",
                "调查记录缺少 form_code。",
                path="data/survey_records.json",
            )
            _require_text(
                form.get("version_code"),
                issues,
                "RESULT_RECORD_FORM_VERSION_INVALID",
                "调查记录缺少表单 version_code。",
                path="data/survey_records.json",
            )

    if set(asset_by_uid) != referenced_asset_uids:
        _append(
            issues,
            "RESULT_ASSET_SET_MISMATCH",
            "成果包工程对象集合与调查记录实际引用集合不一致。",
            path="data/engineering_assets.json",
        )

    # 分项评价
    inspection_keys = set()

    for item in inspections:
        record_uid = _require_text(
            item.get("survey_record_uid"),
            issues,
            "RESULT_INSPECTION_RECORD_UID_INVALID",
            "分项评价缺少 survey_record_uid。",
            path="data/inspection_results.json",
        )
        item_code = _require_text(
            item.get("item_code"),
            issues,
            "RESULT_INSPECTION_ITEM_CODE_INVALID",
            "分项评价缺少 item_code。",
            path="data/inspection_results.json",
        )

        if record_uid and record_uid not in record_by_uid:
            _append(
                issues,
                "RESULT_INSPECTION_RECORD_MISSING",
                "分项评价引用的调查记录不在成果包中。",
                path="data/inspection_results.json",
            )

        if record_uid and item_code:
            key = (record_uid, item_code)
            if key in inspection_keys:
                _append(
                    issues,
                    "RESULT_INSPECTION_DUPLICATE",
                    "分项评价存在重复稳定身份。",
                    path="data/inspection_results.json",
                )
            inspection_keys.add(key)

    # 影像
    media_uids = set()
    media_paths = set()

    for item in media:
        media_uid = _require_text(
            item.get("media_uid"),
            issues,
            "RESULT_MEDIA_UID_INVALID",
            "影像元数据缺少 media_uid。",
            path="data/survey_media.json",
        )

        if media_uid:
            if media_uid in media_uids:
                _append(
                    issues,
                    "RESULT_MEDIA_UID_DUPLICATE",
                    "影像元数据包含重复 media_uid。",
                    path="data/survey_media.json",
                )
            media_uids.add(media_uid)

        record_uid = _require_text(
            item.get("survey_record_uid"),
            issues,
            "RESULT_MEDIA_RECORD_UID_INVALID",
            "影像元数据缺少 survey_record_uid。",
            path="data/survey_media.json",
        )

        if record_uid and record_uid not in record_by_uid:
            _append(
                issues,
                "RESULT_MEDIA_RECORD_MISSING",
                "影像引用的调查记录不在成果包中。",
                path="data/survey_media.json",
            )

        package_path_value = _require_text(
            item.get("package_path"),
            issues,
            "RESULT_MEDIA_PATH_INVALID",
            "影像元数据缺少 package_path。",
            path="data/survey_media.json",
        )

        if not package_path_value:
            continue

        if not package_path_value.startswith("media/"):
            _append(
                issues,
                "RESULT_MEDIA_PATH_OUTSIDE_MEDIA",
                "影像 package_path 必须位于 media/ 下。",
                path=package_path_value,
            )

        if package_path_value in media_paths:
            _append(
                issues,
                "RESULT_MEDIA_PATH_DUPLICATE",
                "影像 package_path 重复。",
                path=package_path_value,
            )

        media_paths.add(package_path_value)

        manifest_entry = manifest_files.get(package_path_value)

        if manifest_entry is None:
            _append(
                issues,
                "RESULT_MEDIA_FILE_MISSING",
                "影像元数据引用的文件未在 manifest 中登记。",
                path=package_path_value,
            )
            continue

        media_hash = item.get("file_sha256")
        if (
            not isinstance(media_hash, str)
            or not _SHA256_PATTERN.fullmatch(media_hash)
        ):
            _append(
                issues,
                "RESULT_MEDIA_HASH_INVALID",
                "影像元数据 SHA-256 无效。",
                path=package_path_value,
            )
        elif manifest_entry.get("sha256") != media_hash:
            _append(
                issues,
                "RESULT_MEDIA_HASH_MISMATCH",
                "影像元数据与 manifest 的 SHA-256 不一致。",
                path=package_path_value,
            )

        media_size = item.get("file_size")
        if not isinstance(media_size, int) or media_size < 0:
            _append(
                issues,
                "RESULT_MEDIA_SIZE_INVALID",
                "影像元数据 file_size 无效。",
                path=package_path_value,
            )
        elif manifest_entry.get("size") != media_size:
            _append(
                issues,
                "RESULT_MEDIA_SIZE_MISMATCH",
                "影像元数据与 manifest 的 file_size 不一致。",
                path=package_path_value,
            )

    manifest_media_paths = {
        path
        for path in manifest_files
        if path.startswith("media/")
    }

    if manifest_media_paths != media_paths:
        _append(
            issues,
            "RESULT_MEDIA_SET_MISMATCH",
            "survey_media.json 与 manifest 中的影像集合不一致。",
            path="data/survey_media.json",
        )

    # counts
    counts = result_document.get("counts")

    if not isinstance(counts, dict):
        _append(
            issues,
            "RESULT_COUNTS_INVALID",
            "result.counts 必须是对象。",
            path="result.json",
        )
    else:
        expected_counts = {
            "engineering_assets": len(assets),
            "survey_records": len(records),
            "inspection_results": len(inspections),
            "survey_media": len(media),
        }

        for key, expected in expected_counts.items():
            if counts.get(key) != expected:
                _append(
                    issues,
                    "RESULT_COUNT_MISMATCH",
                    (
                        f"result.counts.{key} 应为 {expected}，"
                        f"实际为 {counts.get(key)!r}。"
                    ),
                    path="result.json",
                )

    return SurveyResultPackageInspection(
        package_path=package_path,
        manifest=manifest,
        result=result_document,
        engineering_assets=assets,
        survey_records=records,
        inspection_results=inspections,
        survey_media=media,
        issues=tuple(issues),
    )


def load_survey_result_package(package_path):
    """
    检查通过后返回结构化元数据。
    影像文件仍保留在包内，本阶段不解压。
    """

    inspection = inspect_survey_result_package(
        package_path
    )

    if not inspection.valid:
        raise ValueError(
            inspection.format_text()
        )

    if inspection.manifest is None:
        raise ValueError(
            "成果包缺少 manifest。"
        )

    if inspection.result is None:
        raise ValueError(
            "成果包缺少 result.json。"
        )

    return SurveyResultPackageContents(
        package_path=inspection.package_path,
        manifest=dict(inspection.manifest),
        result=dict(inspection.result),
        engineering_assets=tuple(
            dict(item)
            for item in inspection.engineering_assets
        ),
        survey_records=tuple(
            dict(item)
            for item in inspection.survey_records
        ),
        inspection_results=tuple(
            dict(item)
            for item in inspection.inspection_results
        ),
        survey_media=tuple(
            dict(item)
            for item in inspection.survey_media
        ),
    )
