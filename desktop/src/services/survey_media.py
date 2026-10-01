from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import os
import shutil
import uuid

import database


PHOTO_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".m4v",
}

MEDIA_ROLES = (
    "overview",
    "location",
    "detail",
    "problem",
    "other",
)


def _clean_text(value):
    value = str(value or "").strip()
    return value or None


def _validate_media_role(media_role):
    media_role = str(
        media_role or "other"
    ).strip()

    if media_role not in MEDIA_ROLES:
        raise ValueError(
            "无效的影像用途类型。"
        )

    return media_role


def _detect_media_kind(
    source_path,
):
    suffix = (
        Path(source_path)
        .suffix
        .lower()
    )

    if suffix in PHOTO_EXTENSIONS:
        return "photo"

    if suffix in VIDEO_EXTENSIONS:
        return "video"

    raise ValueError(
        "当前文件格式不属于系统支持的"
        "照片或视频格式。"
    )


def _calculate_sha256(
    file_path,
):
    digest = sha256()

    with open(
        file_path,
        "rb",
    ) as source:
        while True:
            chunk = source.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def _get_record_context(
    survey_record_id,
):
    with database.get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                project_id,
                survey_batch_id
            FROM survey_records
            WHERE id = ?
            """,
            (survey_record_id,),
        ).fetchone()

    if row is None:
        raise ValueError(
            "没有找到需要关联影像的调查记录。"
        )

    return {
        "survey_record_id": int(
            row["id"]
        ),
        "project_id": int(
            row["project_id"]
        ),
        "survey_batch_id": int(
            row["survey_batch_id"]
        ),
    }


def _media_root():
    return (
        database.DATA_DIR
        / "media"
    )


def _build_storage_path(
    *,
    project_id,
    survey_batch_id,
    survey_record_id,
    media_uid,
    suffix,
):
    relative_path = Path(
        "media",
        f"project_{project_id}",
        f"batch_{survey_batch_id}",
        f"record_{survey_record_id}",
        f"{media_uid}{suffix.lower()}",
    )

    absolute_path = (
        database.DATA_DIR
        / relative_path
    )

    return (
        relative_path,
        absolute_path,
    )


def import_survey_media(
    *,
    survey_record_id,
    source_file,
    media_role="other",
    item_code=None,
    part_name=None,
    sequence_no=1,
    captured_at=None,
    notes=None,
):
    """
    将一份照片/视频纳入系统托管。

    设计原则：
    - SQLite 只保存影像元数据；
    - 原始文件复制到 local_data/media；
    - 托管文件名使用稳定 media_uid，
      不直接使用渠系/桩号/建筑物名称；
    - 正式归档名称在成果导出阶段按规则生成。
    """

    source_path = Path(
        source_file
    ).expanduser()

    if not source_path.exists():
        raise FileNotFoundError(
            "没有找到需要导入的影像文件。"
        )

    if not source_path.is_file():
        raise ValueError(
            "影像来源必须是文件。"
        )

    media_kind = (
        _detect_media_kind(
            source_path
        )
    )

    media_role = (
        _validate_media_role(
            media_role
        )
    )

    try:
        sequence_no = int(
            sequence_no
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "影像序号必须是正整数。"
        ) from error

    if sequence_no <= 0:
        raise ValueError(
            "影像序号必须是正整数。"
        )

    context = _get_record_context(
        survey_record_id
    )

    file_hash = _calculate_sha256(
        source_path
    )

    file_size = (
        source_path.stat().st_size
    )

    with database.get_connection() as connection:
        duplicate = connection.execute(
            """
            SELECT
                id,
                media_uid,
                original_filename
            FROM survey_media
            WHERE survey_record_id = ?
              AND file_sha256 = ?
            LIMIT 1
            """,
            (
                survey_record_id,
                file_hash,
            ),
        ).fetchone()

    if duplicate is not None:
        raise ValueError(
            "该调查记录已经导入过相同影像文件。"
        )

    media_uid = str(
        uuid.uuid4()
    )

    (
        relative_path,
        absolute_path,
    ) = _build_storage_path(
        project_id=(
            context["project_id"]
        ),
        survey_batch_id=(
            context["survey_batch_id"]
        ),
        survey_record_id=(
            context["survey_record_id"]
        ),
        media_uid=media_uid,
        suffix=source_path.suffix,
    )

    absolute_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        absolute_path.with_name(
            absolute_path.name
            + ".importing"
        )
    )

    if temporary_path.exists():
        temporary_path.unlink()

    shutil.copy2(
        source_path,
        temporary_path,
    )

    os.replace(
        temporary_path,
        absolute_path,
    )

    try:
        with database.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO survey_media (
                    media_uid,
                    survey_record_id,
                    media_kind,
                    media_role,
                    item_code,
                    part_name,
                    sequence_no,
                    original_filename,
                    stored_relative_path,
                    file_sha256,
                    file_size,
                    captured_at,
                    notes
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    media_uid,
                    survey_record_id,
                    media_kind,
                    media_role,
                    _clean_text(
                        item_code
                    ),
                    _clean_text(
                        part_name
                    ),
                    sequence_no,
                    source_path.name,
                    relative_path.as_posix(),
                    file_hash,
                    file_size,
                    _clean_text(
                        captured_at
                    ),
                    _clean_text(
                        notes
                    ),
                ),
            )

            media_id = (
                cursor.lastrowid
            )

    except Exception:
        try:
            absolute_path.unlink(
                missing_ok=True
            )
        finally:
            raise

    return {
        "media_id": media_id,
        "media_uid": media_uid,
        "survey_record_id": (
            survey_record_id
        ),
        "media_kind": media_kind,
        "stored_relative_path": (
            relative_path.as_posix()
        ),
        "absolute_path": (
            absolute_path
        ),
        "file_sha256": file_hash,
        "file_size": file_size,
    }


def get_survey_media(
    survey_record_id,
):
    with database.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                media_uid,
                survey_record_id,
                media_kind,
                media_role,
                item_code,
                part_name,
                sequence_no,
                original_filename,
                stored_relative_path,
                file_sha256,
                file_size,
                captured_at,
                notes,
                created_at,
                updated_at
            FROM survey_media
            WHERE survey_record_id = ?
            ORDER BY
                sequence_no,
                id
            """,
            (
                survey_record_id,
            ),
        ).fetchall()

    result = []

    for row in rows:
        item = dict(row)

        item["absolute_path"] = (
            database.DATA_DIR
            / item[
                "stored_relative_path"
            ]
        )

        result.append(item)

    return result


def get_media_record(
    media_id,
):
    with database.get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                media_uid,
                survey_record_id,
                media_kind,
                media_role,
                item_code,
                part_name,
                sequence_no,
                original_filename,
                stored_relative_path,
                file_sha256,
                file_size,
                captured_at,
                notes,
                created_at,
                updated_at
            FROM survey_media
            WHERE id = ?
            """,
            (media_id,),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)

    result["absolute_path"] = (
        database.DATA_DIR
        / result[
            "stored_relative_path"
        ]
    )

    return result


def update_media_metadata(
    media_id,
    *,
    media_role,
    item_code=None,
    part_name=None,
    sequence_no=1,
    captured_at=None,
    notes=None,
):
    media_role = (
        _validate_media_role(
            media_role
        )
    )

    try:
        sequence_no = int(
            sequence_no
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "影像序号必须是正整数。"
        ) from error

    if sequence_no <= 0:
        raise ValueError(
            "影像序号必须是正整数。"
        )

    with database.get_connection() as connection:
        current = connection.execute(
            """
            SELECT id
            FROM survey_media
            WHERE id = ?
            """,
            (media_id,),
        ).fetchone()

        if current is None:
            raise ValueError(
                "没有找到需要修改的影像记录。"
            )

        connection.execute(
            """
            UPDATE survey_media
            SET
                media_role = ?,
                item_code = ?,
                part_name = ?,
                sequence_no = ?,
                captured_at = ?,
                notes = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                media_role,
                _clean_text(
                    item_code
                ),
                _clean_text(
                    part_name
                ),
                sequence_no,
                _clean_text(
                    captured_at
                ),
                _clean_text(
                    notes
                ),
                media_id,
            ),
        )


def delete_survey_media(
    media_id,
):
    media = get_media_record(
        media_id
    )

    if media is None:
        raise ValueError(
            "没有找到需要删除的影像记录。"
        )

    absolute_path = Path(
        media["absolute_path"]
    )

    temporary_path = (
        absolute_path.with_name(
            absolute_path.name
            + ".deleting"
        )
    )

    moved = False

    if absolute_path.exists():
        os.replace(
            absolute_path,
            temporary_path,
        )
        moved = True

    try:
        with database.get_connection() as connection:
            connection.execute(
                """
                DELETE FROM survey_media
                WHERE id = ?
                """,
                (media_id,),
            )

    except Exception:
        if moved and temporary_path.exists():
            os.replace(
                temporary_path,
                absolute_path,
            )
        raise

    if moved:
        temporary_path.unlink(
            missing_ok=True
        )

    return {
        "media_id": media_id,
        "deleted_file": moved,
    }
