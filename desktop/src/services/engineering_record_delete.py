from __future__ import annotations

from pathlib import Path

from database import (
    delete_engineering_survey_record,
)
from services.survey_media import (
    get_survey_media,
)


def delete_engineering_survey_record_with_media(
    *,
    survey_record_id,
    form_code,
):
    """
    删除调查记录并清理其托管影像文件。

    顺序：
    1. 先取得托管影像路径；
    2. 执行既有数据库删除事务；
    3. 数据库删除成功后，再清理文件。

    这样数据库删除失败时不会提前丢失影像。
    文件清理失败不会伪装成数据库删除失败，
    而是作为 cleanup_errors 返回。
    """

    media_records = tuple(
        get_survey_media(
            survey_record_id
        )
    )

    result = (
        delete_engineering_survey_record(
            survey_record_id=(
                survey_record_id
            ),
            form_code=form_code,
        )
    )

    cleanup_errors = []
    deleted_file_count = 0
    parent_directories = set()

    for media in media_records:
        file_path = Path(
            media["absolute_path"]
        )

        parent_directories.add(
            file_path.parent
        )

        try:
            if file_path.exists():
                file_path.unlink()
                deleted_file_count += 1

        except Exception as error:
            cleanup_errors.append(
                (
                    f"{media['original_filename']}："
                    f"{error}"
                )
            )

    for directory in sorted(
        parent_directories,
        key=lambda path:
        len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass

    merged_result = dict(result)

    merged_result[
        "media_file_deleted_count"
    ] = deleted_file_count

    merged_result[
        "media_cleanup_errors"
    ] = tuple(cleanup_errors)

    return merged_result
