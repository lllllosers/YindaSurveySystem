from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from services.yd_package import (
    PACKAGE_FORMAT_VERSION,
)


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

MAX_PACKAGE_FILE_COUNT = 200
MAX_SINGLE_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024

_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)


@dataclass(frozen=True)
class PackageInspectionIssue:
    severity: str
    code: str
    message: str
    path: str = ""


@dataclass(frozen=True)
class PackageInspectionReport:
    package_path: Path
    manifest: dict | None
    issues: tuple[PackageInspectionIssue, ...]
    file_count: int
    total_uncompressed_bytes: int

    @property
    def error_count(self):
        return sum(
            1
            for issue in self.issues
            if issue.severity == SEVERITY_ERROR
        )

    @property
    def warning_count(self):
        return sum(
            1
            for issue in self.issues
            if issue.severity == SEVERITY_WARNING
        )

    @property
    def valid(self):
        return self.error_count == 0

    def format_text(self):
        lines = [
            f"包文件：{self.package_path}",
            (
                "检查结果："
                f"{self.error_count} 个错误，"
                f"{self.warning_count} 个警告"
            ),
        ]

        if not self.issues:
            lines.append("未发现问题。")
            return "\n".join(lines)

        labels = {
            SEVERITY_ERROR: "错误",
            SEVERITY_WARNING: "警告",
        }

        for issue in self.issues:
            suffix = (
                f" [{issue.path}]"
                if issue.path
                else ""
            )

            lines.append(
                (
                    f"[{labels.get(issue.severity, issue.severity)}] "
                    f"{issue.code}：{issue.message}{suffix}"
                )
            )

        return "\n".join(lines)


def _issue(
    issues,
    code,
    message,
    *,
    path="",
    severity=SEVERITY_ERROR,
):
    issues.append(
        PackageInspectionIssue(
            severity=severity,
            code=code,
            message=message,
            path=path,
        )
    )


def _validate_member_path(
    raw_name,
):
    if not isinstance(
        raw_name,
        str,
    ):
        return False

    name = raw_name.strip()

    if (
        not name
        or "\x00" in name
        or "\\" in name
    ):
        return False

    pure = PurePosixPath(name)

    if pure.is_absolute():
        return False

    if any(
        part in (
            "",
            ".",
            "..",
        )
        for part in pure.parts
    ):
        return False

    return True


def _read_json_object(
    archive,
    path,
    issues,
):
    try:
        raw = archive.read(path)
    except KeyError:
        _issue(
            issues,
            "REQUIRED_FILE_MISSING",
            "缺少必需文件。",
            path=path,
        )
        return None

    try:
        value = json.loads(
            raw.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        _issue(
            issues,
            "INVALID_JSON",
            "文件不是有效 UTF-8 JSON。",
            path=path,
        )
        return None

    if not isinstance(
        value,
        dict,
    ):
        _issue(
            issues,
            "JSON_ROOT_INVALID",
            "JSON 顶层必须是对象。",
            path=path,
        )
        return None

    return value


def inspect_package(
    package_path,
    *,
    expected_kind=None,
):
    """
    通用 YD 包只读检查。

    不解压到磁盘，不修改数据库，不导入任何业务数据。
    """

    package_path = Path(
        package_path
    )

    issues = []

    if not package_path.exists():
        _issue(
            issues,
            "PACKAGE_NOT_FOUND",
            "包文件不存在。",
        )

        return PackageInspectionReport(
            package_path=package_path,
            manifest=None,
            issues=tuple(issues),
            file_count=0,
            total_uncompressed_bytes=0,
        )

    if not package_path.is_file():
        _issue(
            issues,
            "PACKAGE_NOT_FILE",
            "指定路径不是文件。",
        )

        return PackageInspectionReport(
            package_path=package_path,
            manifest=None,
            issues=tuple(issues),
            file_count=0,
            total_uncompressed_bytes=0,
        )

    if not zipfile.is_zipfile(
        package_path
    ):
        _issue(
            issues,
            "PACKAGE_NOT_ZIP",
            "包不是有效的 ZIP-compatible 文件。",
        )

        return PackageInspectionReport(
            package_path=package_path,
            manifest=None,
            issues=tuple(issues),
            file_count=0,
            total_uncompressed_bytes=0,
        )

    manifest = None
    file_count = 0
    total_uncompressed_bytes = 0

    try:
        with zipfile.ZipFile(
            package_path,
            "r",
        ) as archive:
            infos = archive.infolist()

            file_count = len(
                infos
            )

            if file_count > MAX_PACKAGE_FILE_COUNT:
                _issue(
                    issues,
                    "TOO_MANY_FILES",
                    (
                        "包内文件数量超过安全上限 "
                        f"{MAX_PACKAGE_FILE_COUNT}。"
                    ),
                )

            seen_names = set()

            for info in infos:
                name = info.filename

                if name in seen_names:
                    _issue(
                        issues,
                        "DUPLICATE_ZIP_MEMBER",
                        "ZIP 中存在重复文件路径。",
                        path=name,
                    )
                else:
                    seen_names.add(
                        name
                    )

                if not _validate_member_path(
                    name
                ):
                    _issue(
                        issues,
                        "UNSAFE_PATH",
                        "包内路径不安全。",
                        path=name,
                    )

                if info.is_dir():
                    continue

                if (
                    info.file_size
                    > MAX_SINGLE_FILE_BYTES
                ):
                    _issue(
                        issues,
                        "FILE_TOO_LARGE",
                        (
                            "单个包内文件超过安全上限 "
                            f"{MAX_SINGLE_FILE_BYTES} bytes。"
                        ),
                        path=name,
                    )

                total_uncompressed_bytes += (
                    int(
                        info.file_size
                    )
                )

            if (
                total_uncompressed_bytes
                > MAX_TOTAL_UNCOMPRESSED_BYTES
            ):
                _issue(
                    issues,
                    "PACKAGE_TOO_LARGE",
                    (
                        "包解压后总大小超过安全上限 "
                        f"{MAX_TOTAL_UNCOMPRESSED_BYTES} bytes。"
                    ),
                )

            if "manifest.json" not in seen_names:
                _issue(
                    issues,
                    "MANIFEST_MISSING",
                    "缺少 manifest.json。",
                )
            else:
                manifest = _read_json_object(
                    archive,
                    "manifest.json",
                    issues,
                )

            if manifest is not None:
                package_uid = manifest.get(
                    "package_uid"
                )

                if (
                    not isinstance(
                        package_uid,
                        str,
                    )
                    or not package_uid.strip()
                ):
                    _issue(
                        issues,
                        "PACKAGE_UID_INVALID",
                        "manifest 缺少有效 package_uid。",
                    )

                package_kind = manifest.get(
                    "package_kind"
                )

                if (
                    not isinstance(
                        package_kind,
                        str,
                    )
                    or not package_kind.strip()
                ):
                    _issue(
                        issues,
                        "PACKAGE_KIND_INVALID",
                        "manifest 缺少有效 package_kind。",
                    )

                elif (
                    expected_kind is not None
                    and package_kind
                    != expected_kind
                ):
                    _issue(
                        issues,
                        "PACKAGE_KIND_MISMATCH",
                        (
                            "包类型不匹配："
                            f"期望 {expected_kind}，"
                            f"实际 {package_kind}。"
                        ),
                    )

                format_version = manifest.get(
                    "package_format_version"
                )

                if (
                    format_version
                    != PACKAGE_FORMAT_VERSION
                ):
                    _issue(
                        issues,
                        "FORMAT_VERSION_UNSUPPORTED",
                        (
                            "不支持的包格式版本："
                            f"{format_version!r}。"
                        ),
                    )

                files = manifest.get(
                    "files"
                )

                if not isinstance(
                    files,
                    list,
                ):
                    _issue(
                        issues,
                        "MANIFEST_FILES_INVALID",
                        "manifest.files 必须是数组。",
                    )

                    files = []

                manifest_paths = set()

                for index, entry in enumerate(
                    files
                ):
                    if not isinstance(
                        entry,
                        dict,
                    ):
                        _issue(
                            issues,
                            "MANIFEST_FILE_ENTRY_INVALID",
                            (
                                "manifest.files "
                                f"第 {index + 1} 项不是对象。"
                            ),
                        )
                        continue

                    path = entry.get(
                        "path"
                    )

                    if (
                        not isinstance(
                            path,
                            str,
                        )
                        or not _validate_member_path(
                            path
                        )
                    ):
                        _issue(
                            issues,
                            "MANIFEST_PATH_INVALID",
                            "manifest 文件路径无效。",
                            path=(
                                str(
                                    path
                                )
                                if path is not None
                                else ""
                            ),
                        )
                        continue

                    if path == "manifest.json":
                        _issue(
                            issues,
                            "MANIFEST_SELF_REFERENCE",
                            (
                                "manifest.files "
                                "不能包含 manifest.json。"
                            ),
                            path=path,
                        )

                    if path in manifest_paths:
                        _issue(
                            issues,
                            "MANIFEST_PATH_DUPLICATE",
                            (
                                "manifest.files "
                                "包含重复路径。"
                            ),
                            path=path,
                        )
                        continue

                    manifest_paths.add(
                        path
                    )

                    expected_size = entry.get(
                        "size"
                    )

                    if (
                        not isinstance(
                            expected_size,
                            int,
                        )
                        or expected_size < 0
                    ):
                        _issue(
                            issues,
                            "MANIFEST_SIZE_INVALID",
                            "manifest 文件大小无效。",
                            path=path,
                        )
                        continue

                    expected_hash = entry.get(
                        "sha256"
                    )

                    if (
                        not isinstance(
                            expected_hash,
                            str,
                        )
                        or not _SHA256_PATTERN.fullmatch(
                            expected_hash
                        )
                    ):
                        _issue(
                            issues,
                            "MANIFEST_HASH_INVALID",
                            "manifest SHA-256 无效。",
                            path=path,
                        )
                        continue

                    try:
                        content = archive.read(
                            path
                        )
                    except KeyError:
                        _issue(
                            issues,
                            "MANIFEST_FILE_MISSING",
                            (
                                "manifest 声明的文件"
                                "在包中不存在。"
                            ),
                            path=path,
                        )
                        continue

                    if len(
                        content
                    ) != expected_size:
                        _issue(
                            issues,
                            "SIZE_MISMATCH",
                            (
                                "文件大小与 manifest "
                                "记录不一致。"
                            ),
                            path=path,
                        )

                    actual_hash = sha256(
                        content
                    ).hexdigest()

                    if (
                        actual_hash
                        != expected_hash
                    ):
                        _issue(
                            issues,
                            "HASH_MISMATCH",
                            (
                                "文件 SHA-256 与 manifest "
                                "记录不一致。"
                            ),
                            path=path,
                        )

                actual_payload_paths = {
                    info.filename
                    for info in infos
                    if (
                        not info.is_dir()
                        and info.filename
                        != "manifest.json"
                    )
                }

                untracked = (
                    actual_payload_paths
                    - manifest_paths
                )

                for path in sorted(
                    untracked
                ):
                    _issue(
                        issues,
                        "UNTRACKED_FILE",
                        (
                            "包内存在未在 manifest "
                            "登记的文件。"
                        ),
                        path=path,
                    )

                declared_but_missing = (
                    manifest_paths
                    - actual_payload_paths
                )

                for path in sorted(
                    declared_but_missing
                ):
                    _issue(
                        issues,
                        "DECLARED_FILE_MISSING",
                        (
                            "manifest 声明了"
                            "包中不存在的文件。"
                        ),
                        path=path,
                    )

    except (
        OSError,
        zipfile.BadZipFile,
        RuntimeError,
    ) as error:
        _issue(
            issues,
            "PACKAGE_READ_FAILED",
            (
                "读取包失败："
                f"{error}"
            ),
        )

    return PackageInspectionReport(
        package_path=package_path,
        manifest=manifest,
        issues=tuple(issues),
        file_count=file_count,
        total_uncompressed_bytes=(
            total_uncompressed_bytes
        ),
    )


def read_json_file_from_valid_package(
    package_path,
    path,
):
    """
    只用于已经通过 inspect_package() 的包。
    """

    package_path = Path(
        package_path
    )

    with zipfile.ZipFile(
        package_path,
        "r",
    ) as archive:
        raw = archive.read(
            path
        )

    value = json.loads(
        raw.decode("utf-8")
    )

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"{path} 顶层必须是 JSON 对象。"
        )

    return value
