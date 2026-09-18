from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


PACKAGE_FORMAT_VERSION = "1.0"
EXPECTED_PACKAGE_KIND = "survey_result"
MAX_FILE_COUNT = 100_000
MAX_SINGLE_FILE_BYTES = 8 * 1024 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024 * 1024

REQUIRED_FILES = {
    "result.json",
    "data/engineering_assets.json",
    "data/survey_records.json",
    "data/inspection_results.json",
    "data/survey_media.json",
}

HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class InspectionIssue:
    code: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "path": self.path}


@dataclass(frozen=True)
class ResultPackageInspection:
    valid: bool
    issues: tuple[InspectionIssue, ...]
    manifest: dict | None
    result: dict | None

    @property
    def error_count(self) -> int:
        return len(self.issues)


def add_issue(issues: list[InspectionIssue], code: str, message: str, path: str | None = None) -> None:
    issues.append(InspectionIssue(code=code, message=message, path=path))


def safe_path(name: str) -> bool:
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        return False
    pure = PurePosixPath(name)
    if pure.is_absolute():
        return False
    return all(part not in {"", ".", ".."} for part in pure.parts)


def is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def read_json_object(archive: zipfile.ZipFile, path: str, issues: list[InspectionIssue]) -> dict | None:
    try:
        raw = archive.read(path)
    except KeyError:
        add_issue(issues, "REQUIRED_FILE_MISSING", "缺少必需文件。", path)
        return None

    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        add_issue(issues, "INVALID_JSON", "文件不是有效 UTF-8 JSON。", path)
        return None

    if not isinstance(value, dict):
        add_issue(issues, "JSON_ROOT_INVALID", "JSON 顶层必须是对象。", path)
        return None
    return value


def inspect_result_package(package_path: Path) -> ResultPackageInspection:
    issues: list[InspectionIssue] = []

    if not zipfile.is_zipfile(package_path):
        add_issue(issues, "PACKAGE_NOT_ZIP", "文件不是有效 ZIP-compatible 成果包。")
        return ResultPackageInspection(False, tuple(issues), None, None)

    manifest = None
    result = None

    try:
        with zipfile.ZipFile(package_path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILE_COUNT:
                add_issue(issues, "TOO_MANY_FILES", "包内文件数量超过安全上限。")

            names: set[str] = set()
            total = 0

            for info in infos:
                name = info.filename
                if name in names:
                    add_issue(issues, "DUPLICATE_ZIP_MEMBER", "ZIP 中存在重复路径。", name)
                names.add(name)

                if not safe_path(name):
                    add_issue(issues, "UNSAFE_PATH", "包内路径不安全。", name)
                if is_symlink(info):
                    add_issue(issues, "SYMLINK_NOT_ALLOWED", "包内不允许符号链接。", name)
                if info.is_dir():
                    continue

                if info.file_size > MAX_SINGLE_FILE_BYTES:
                    add_issue(issues, "FILE_TOO_LARGE", "包内单文件超过安全上限。", name)
                total += int(info.file_size)

            if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
                add_issue(issues, "PACKAGE_TOO_LARGE", "成果包解压后总大小超过安全上限。")

            if "manifest.json" not in names:
                add_issue(issues, "MANIFEST_MISSING", "缺少 manifest.json。")
                return ResultPackageInspection(False, tuple(issues), None, None)

            manifest = read_json_object(archive, "manifest.json", issues)
            if manifest is None:
                return ResultPackageInspection(False, tuple(issues), None, None)

            if manifest.get("package_kind") != EXPECTED_PACKAGE_KIND:
                add_issue(
                    issues,
                    "PACKAGE_KIND_MISMATCH",
                    "package_kind 必须为 survey_result。",
                    "manifest.json",
                )

            if manifest.get("package_format_version") != PACKAGE_FORMAT_VERSION:
                add_issue(
                    issues,
                    "FORMAT_VERSION_UNSUPPORTED",
                    "当前仅支持 package_format_version=1.0。",
                    "manifest.json",
                )

            package_uid = manifest.get("package_uid")
            if not isinstance(package_uid, str) or not HEX32.fullmatch(package_uid):
                add_issue(
                    issues,
                    "PACKAGE_UID_INVALID",
                    "package_uid 必须为 32 位小写十六进制字符串。",
                    "manifest.json",
                )

            entries = manifest.get("files")
            if not isinstance(entries, list):
                add_issue(
                    issues,
                    "MANIFEST_FILES_INVALID",
                    "manifest.files 必须为数组。",
                    "manifest.json",
                )
                entries = []

            declared: dict[str, dict] = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    add_issue(
                        issues,
                        "MANIFEST_FILE_ENTRY_INVALID",
                        "manifest.files 项必须为对象。",
                        "manifest.json",
                    )
                    continue

                path = entry.get("path")
                expected_hash = entry.get("sha256")
                expected_size = entry.get("size")

                if not isinstance(path, str) or not safe_path(path):
                    add_issue(
                        issues,
                        "MANIFEST_PATH_INVALID",
                        "manifest 文件路径无效。",
                        "manifest.json",
                    )
                    continue
                if path in declared:
                    add_issue(
                        issues,
                        "MANIFEST_PATH_DUPLICATE",
                        "manifest.files 存在重复路径。",
                        path,
                    )
                    continue

                declared[path] = entry
                if path not in names:
                    add_issue(
                        issues,
                        "DECLARED_FILE_MISSING",
                        "manifest 声明文件在 ZIP 中不存在。",
                        path,
                    )
                    continue
                if not isinstance(expected_hash, str) or not HEX64.fullmatch(expected_hash):
                    add_issue(
                        issues,
                        "MANIFEST_SHA256_INVALID",
                        "manifest 文件 SHA-256 无效。",
                        path,
                    )
                    continue
                if not isinstance(expected_size, int) or expected_size < 0:
                    add_issue(
                        issues,
                        "MANIFEST_SIZE_INVALID",
                        "manifest 文件大小无效。",
                        path,
                    )
                    continue

                digest = sha256()
                actual_size = 0
                with archive.open(path, "r") as source:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        actual_size += len(chunk)

                if actual_size != expected_size:
                    add_issue(issues, "FILE_SIZE_MISMATCH", "文件大小与 manifest 不一致。", path)
                if digest.hexdigest() != expected_hash:
                    add_issue(issues, "FILE_SHA256_MISMATCH", "文件 SHA-256 与 manifest 不一致。", path)

            actual_payloads = {
                name for name in names
                if name != "manifest.json" and not name.endswith("/")
            }
            for path in sorted(actual_payloads - set(declared)):
                add_issue(issues, "UNDECLARED_FILE", "ZIP 中存在未声明文件。", path)

            for path in sorted(REQUIRED_FILES):
                if path not in declared:
                    add_issue(issues, "RESULT_FILE_NOT_DECLARED", "缺少成果必需文件声明。", path)

            if issues:
                return ResultPackageInspection(False, tuple(issues), manifest, None)

            result = read_json_object(archive, "result.json", issues)

            for path in REQUIRED_FILES - {"result.json"}:
                document = read_json_object(archive, path, issues)
                if document is not None and not isinstance(document.get("items"), list):
                    add_issue(
                        issues,
                        "RESULT_ITEMS_INVALID",
                        "成果数据 items 必须为数组。",
                        path,
                    )

            if result is None:
                return ResultPackageInspection(False, tuple(issues), manifest, None)

            project = result.get("project")
            batch = result.get("survey_batch")
            pairs = (
                ("result_uid", result.get("result_uid"), manifest.get("result_uid")),
                (
                    "project_uid",
                    project.get("project_uid") if isinstance(project, dict) else None,
                    manifest.get("project_uid"),
                ),
                (
                    "survey_batch_uid",
                    batch.get("survey_batch_uid") if isinstance(batch, dict) else None,
                    manifest.get("survey_batch_uid"),
                ),
            )

            for field, left, right in pairs:
                if not isinstance(left, str) or not HEX32.fullmatch(left):
                    add_issue(issues, f"{field.upper()}_INVALID", f"result.json 中 {field} 无效。")
                if not isinstance(right, str) or not HEX32.fullmatch(right):
                    add_issue(
                        issues,
                        f"MANIFEST_{field.upper()}_INVALID",
                        f"manifest 中 {field} 无效。",
                    )
                if isinstance(left, str) and isinstance(right, str) and left != right:
                    add_issue(
                        issues,
                        f"{field.upper()}_MISMATCH",
                        f"manifest 与 result.json 的 {field} 不一致。",
                    )

            if not isinstance(result.get("counts"), dict):
                add_issue(issues, "COUNTS_INVALID", "result.counts 必须为对象。", "result.json")

            source_task_uids = result.get("source_task_uids", [])
            if not isinstance(source_task_uids, list) or any(
                not isinstance(value, str) or not value.strip()
                for value in source_task_uids
            ):
                add_issue(
                    issues,
                    "SOURCE_TASK_UIDS_INVALID",
                    "source_task_uids 必须为字符串数组。",
                    "result.json",
                )

    except (OSError, zipfile.BadZipFile) as exc:
        add_issue(issues, "PACKAGE_READ_ERROR", f"成果包读取失败：{exc}")

    return ResultPackageInspection(
        valid=not issues,
        issues=tuple(issues),
        manifest=manifest,
        result=result,
    )
