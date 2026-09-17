from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import uuid
import zipfile


PACKAGE_FORMAT_VERSION = "1.0"
SURVEY_TASK_PACKAGE_KIND = "survey_task"
SURVEY_TASK_EXTENSION = ".ydtask"


@dataclass(frozen=True)
class PackageWriteResult:
    output_path: Path
    package_uid: str
    file_count: int
    total_payload_bytes: int


def new_stable_token():
    """
    生成 128 bit 随机标识。
    与 Stage 08 稳定 UID 一样，对外只作为不透明字符串使用。
    """

    return uuid.uuid4().hex


def encode_json_bytes(data):
    text = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )

    return (
        text
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data):
    return sha256(data).hexdigest()


def _validate_logical_path(path):
    """
    包内路径一律使用 POSIX 相对路径。

    虽然 Stage 10.1 只负责“写”，仍先禁止：
    - 绝对路径；
    - .. 路径穿越；
    - 空路径；
    - 反斜杠。
    """

    path = str(
        path or ""
    ).strip()

    if not path:
        raise ValueError(
            "包内文件路径不能为空。"
        )

    if "\\" in path:
        raise ValueError(
            "包内文件路径必须使用 /。"
        )

    pure = PurePosixPath(path)

    if pure.is_absolute():
        raise ValueError(
            "包内文件路径不能是绝对路径。"
        )

    if any(
        part in (
            "",
            ".",
            "..",
        )
        for part in pure.parts
    ):
        raise ValueError(
            "包内文件路径包含非法片段。"
        )

    return str(pure)


def normalize_task_package_path(
    output_path,
):
    path = Path(
        output_path
    )

    if path.suffix == "":
        path = path.with_suffix(
            SURVEY_TASK_EXTENSION
        )

    elif (
        path.suffix.lower()
        != SURVEY_TASK_EXTENSION
    ):
        raise ValueError(
            "调查任务包文件扩展名必须为 .ydtask。"
        )

    return path


def write_package(
    output_path,
    *,
    package_uid,
    manifest,
    payload_files,
):
    """
    原子写入 ZIP-compatible 包。

    manifest.json 不自我哈希。
    其余 payload 文件全部在 manifest 中记录：
    - 相对路径；
    - SHA-256；
    - byte size。

    目标文件已经存在时拒绝覆盖。
    """

    output_path = Path(
        output_path
    )

    if output_path.exists():
        raise FileExistsError(
            f"目标任务包已经存在：{output_path}"
        )

    if not package_uid:
        raise ValueError(
            "package_uid 不能为空。"
        )

    normalized_payload = {}

    for raw_path, raw_bytes in (
        payload_files.items()
    ):
        logical_path = (
            _validate_logical_path(
                raw_path
            )
        )

        if (
            logical_path
            == "manifest.json"
        ):
            raise ValueError(
                "payload_files 不能包含 manifest.json。"
            )

        if logical_path in normalized_payload:
            raise ValueError(
                "包内文件路径重复："
                f"{logical_path}"
            )

        if not isinstance(
            raw_bytes,
            (
                bytes,
                bytearray,
            ),
        ):
            raise TypeError(
                "包内文件内容必须是 bytes。"
            )

        normalized_payload[
            logical_path
        ] = bytes(raw_bytes)

    file_entries = []

    for logical_path in sorted(
        normalized_payload
    ):
        content = (
            normalized_payload[
                logical_path
            ]
        )

        file_entries.append(
            {
                "path": logical_path,
                "sha256": (
                    sha256_bytes(
                        content
                    )
                ),
                "size": len(content),
            }
        )

    manifest_data = dict(
        manifest
    )

    manifest_data[
        "package_uid"
    ] = package_uid

    manifest_data[
        "package_format_version"
    ] = PACKAGE_FORMAT_VERSION

    manifest_data[
        "files"
    ] = file_entries

    manifest_bytes = (
        encode_json_bytes(
            manifest_data
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        output_path.parent
        / (
            "."
            + output_path.name
            + "."
            + package_uid
            + ".tmp"
        )
    )

    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=(
                zipfile.ZIP_DEFLATED
            ),
        ) as archive:
            archive.writestr(
                "manifest.json",
                manifest_bytes,
            )

            for logical_path in sorted(
                normalized_payload
            ):
                archive.writestr(
                    logical_path,
                    normalized_payload[
                        logical_path
                    ],
                )

        os.replace(
            temporary_path,
            output_path,
        )

    except Exception:
        try:
            temporary_path.unlink(
                missing_ok=True
            )
        except Exception:
            pass

        raise

    return PackageWriteResult(
        output_path=output_path,
        package_uid=package_uid,
        file_count=(
            len(normalized_payload)
        ),
        total_payload_bytes=sum(
            len(content)
            for content in (
                normalized_payload.values()
            )
        ),
    )
