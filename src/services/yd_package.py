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
def write_package_streaming(
    output_path,
    *,
    package_uid,
    manifest,
    payload_files,
    source_files,
    chunk_size=1024 * 1024,
):
    """
    原子写入同时包含内存 JSON 与磁盘文件的 YD 包。

    与 write_package() 的区别：
    - payload_files 仍用于较小的 JSON/文本 bytes；
    - source_files 直接从磁盘分块写入 ZIP，不把照片/视频整体读入内存；
    - SHA-256 和 size 在写入 ZIP 的同时计算；
    - manifest 最后写入，因此可以记录真实写入后的哈希与大小。

    适合 .ydresult 这类可能包含大量影像的成果包。
    """

    output_path = Path(
        output_path
    )

    if output_path.exists():
        raise FileExistsError(
            f"目标包已经存在：{output_path}"
        )

    if not package_uid:
        raise ValueError(
            "package_uid 不能为空。"
        )

    try:
        chunk_size = int(
            chunk_size
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "chunk_size 必须是正整数。"
        ) from error

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size 必须是正整数。"
        )

    normalized_payload = {}
    normalized_sources = {}

    for raw_path, raw_bytes in (
        payload_files.items()
    ):
        logical_path = (
            _validate_logical_path(
                raw_path
            )
        )

        if logical_path == "manifest.json":
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
                "包内 payload 内容必须是 bytes。"
            )

        normalized_payload[
            logical_path
        ] = bytes(raw_bytes)

    for raw_path, raw_source in (
        source_files.items()
    ):
        logical_path = (
            _validate_logical_path(
                raw_path
            )
        )

        if logical_path == "manifest.json":
            raise ValueError(
                "source_files 不能包含 manifest.json。"
            )

        if (
            logical_path in normalized_payload
            or logical_path
            in normalized_sources
        ):
            raise ValueError(
                "包内文件路径重复："
                f"{logical_path}"
            )

        source_path = Path(
            raw_source
        )

        if not source_path.exists():
            raise FileNotFoundError(
                f"源文件不存在：{source_path}"
            )

        if not source_path.is_file():
            raise ValueError(
                f"源路径不是文件：{source_path}"
            )

        normalized_sources[
            logical_path
        ] = source_path

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

    file_entries = []
    total_payload_bytes = 0

    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=(
                zipfile.ZIP_DEFLATED
            ),
        ) as archive:
            for logical_path in sorted(
                normalized_payload
            ):
                content = (
                    normalized_payload[
                        logical_path
                    ]
                )

                archive.writestr(
                    logical_path,
                    content,
                )

                file_entries.append(
                    {
                        "path": logical_path,
                        "sha256": (
                            sha256_bytes(
                                content
                            )
                        ),
                        "size": len(
                            content
                        ),
                    }
                )

                total_payload_bytes += (
                    len(content)
                )

            for logical_path in sorted(
                normalized_sources
            ):
                source_path = (
                    normalized_sources[
                        logical_path
                    ]
                )

                digest = sha256()
                file_size = 0

                with open(
                    source_path,
                    "rb",
                ) as source:
                    with archive.open(
                        logical_path,
                        "w",
                    ) as destination:
                        while True:
                            chunk = (
                                source.read(
                                    chunk_size
                                )
                            )

                            if not chunk:
                                break

                            destination.write(
                                chunk
                            )

                            digest.update(
                                chunk
                            )

                            file_size += len(
                                chunk
                            )

                file_entries.append(
                    {
                        "path": logical_path,
                        "sha256": (
                            digest.hexdigest()
                        ),
                        "size": (
                            file_size
                        ),
                    }
                )

                total_payload_bytes += (
                    file_size
                )

            file_entries.sort(
                key=lambda item:
                item["path"]
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

            archive.writestr(
                "manifest.json",
                encode_json_bytes(
                    manifest_data
                ),
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
            len(file_entries)
        ),
        total_payload_bytes=(
            total_payload_bytes
        ),
    )
