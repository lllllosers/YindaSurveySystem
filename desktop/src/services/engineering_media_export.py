from __future__ import annotations

from pathlib import Path
import shutil

from services.engineering_batch_export import (
    sanitize_filename,
)
from services.survey_media import (
    get_survey_media,
)


MEDIA_ROLE_LABELS = {
    "overview": "全景",
    "location": "位置",
    "detail": "细部",
    "problem": "问题/隐患",
    "other": "其他",
}

MEDIA_KIND_LABELS = {
    "photo": "照片",
    "video": "视频",
}


def _archive_directory(
    *,
    media_root,
    record,
):
    """
    正式成果影像目录：

    03_影像资料/
      渠系/
        工程位置_工程名称/

    当前基础资料尚未有“渠系简称”字段，
    所以先使用正式渠系名称。
    """

    canal_name = sanitize_filename(
        record["canal_name"],
        fallback="未注明渠系",
    )

    position = sanitize_filename(
        record["engineering_position"],
        fallback="未注明位置",
    )

    asset_name = sanitize_filename(
        record["asset_name"],
        fallback="未命名工程",
    )

    return (
        media_root
        / canal_name
        / f"{position}_{asset_name}"
    )


def build_media_archive_filename(
    *,
    record,
    media,
):
    """
    按当前实施方案规则生成正式影像归档名：

    渠系-工程位置-建筑物名称-部位-序号.扩展名

    内部受管文件仍保持 media_uid 文件名。
    """

    canal_name = sanitize_filename(
        record["canal_name"],
        fallback="未注明渠系",
    )

    position = sanitize_filename(
        record["engineering_position"],
        fallback="未注明位置",
    )

    asset_name = sanitize_filename(
        record["asset_name"],
        fallback="未命名工程",
    )

    part_name = sanitize_filename(
        media.get("part_name"),
        fallback="未注明部位",
    )

    try:
        sequence_no = int(
            media["sequence_no"]
        )
    except (
        TypeError,
        ValueError,
        KeyError,
    ) as error:
        raise ValueError(
            "影像序号无效。"
        ) from error

    if sequence_no <= 0:
        raise ValueError(
            "影像序号无效。"
        )

    source_path = Path(
        media["absolute_path"]
    )

    suffix = (
        source_path.suffix
        or Path(
            media.get(
                "original_filename",
                "",
            )
        ).suffix
    )

    if not suffix:
        raise ValueError(
            "影像文件缺少扩展名。"
        )

    return (
        f"{canal_name}-"
        f"{position}-"
        f"{asset_name}-"
        f"{part_name}-"
        f"{sequence_no:02d}"
        f"{suffix.lower()}"
    )


def export_record_media(
    *,
    record,
    media_root,
):
    """
    导出一条调查记录关联的全部影像。

    单个影像失败不会阻断其它文件；
    正式文件名冲突直接作为失败报告，
    不静默追加随机后缀。
    """

    media_records = tuple(
        get_survey_media(
            int(
                record[
                    "survey_record_id"
                ]
            )
        )
    )

    entries = []
    errors = []

    if not media_records:
        return {
            "entries": entries,
            "errors": errors,
        }

    target_directory = (
        _archive_directory(
            media_root=media_root,
            record=record,
        )
    )

    target_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    used_names = set()

    for media in media_records:
        source_path = Path(
            media["absolute_path"]
        )

        try:
            if not source_path.exists():
                raise FileNotFoundError(
                    "系统托管影像文件缺失。"
                )

            filename = (
                build_media_archive_filename(
                    record=record,
                    media=media,
                )
            )

            normalized_name = (
                filename.casefold()
            )

            if normalized_name in used_names:
                raise ValueError(
                    "正式影像文件名重复，"
                    "请检查部位和影像序号。"
                )

            target_path = (
                target_directory
                / filename
            )

            if target_path.exists():
                raise ValueError(
                    "正式影像目标文件已存在。"
                )

            shutil.copy2(
                source_path,
                target_path,
            )

            used_names.add(
                normalized_name
            )

            entries.append(
                {
                    "survey_record_id": int(
                        record[
                            "survey_record_id"
                        ]
                    ),
                    "business_code": (
                        record[
                            "business_code"
                        ]
                        or ""
                    ),
                    "asset_name": (
                        record[
                            "asset_name"
                        ]
                        or ""
                    ),
                    "canal_name": (
                        record[
                            "canal_name"
                        ]
                        or ""
                    ),
                    "engineering_position": (
                        record[
                            "engineering_position"
                        ]
                        or ""
                    ),
                    "media_uid": (
                        media["media_uid"]
                    ),
                    "media_kind": (
                        media["media_kind"]
                    ),
                    "media_kind_label": (
                        MEDIA_KIND_LABELS.get(
                            media[
                                "media_kind"
                            ],
                            media[
                                "media_kind"
                            ],
                        )
                    ),
                    "media_role": (
                        media["media_role"]
                    ),
                    "media_role_label": (
                        MEDIA_ROLE_LABELS.get(
                            media[
                                "media_role"
                            ],
                            media[
                                "media_role"
                            ],
                        )
                    ),
                    "part_name": (
                        media["part_name"]
                        or ""
                    ),
                    "item_code": (
                        media["item_code"]
                        or ""
                    ),
                    "sequence_no": (
                        media["sequence_no"]
                    ),
                    "original_filename": (
                        media[
                            "original_filename"
                        ]
                    ),
                    "relative_path": str(
                        target_path.relative_to(
                            media_root.parent
                        )
                    ),
                    "status": "成功",
                    "error": "",
                }
            )

        except Exception as error:
            errors.append(
                (
                    f"调查记录"
                    f"{record['survey_record_id']} "
                    f"影像"
                    f"{media.get('original_filename', '')}"
                    " 导出失败："
                    f"{error}"
                )
            )

            entries.append(
                {
                    "survey_record_id": int(
                        record[
                            "survey_record_id"
                        ]
                    ),
                    "business_code": (
                        record[
                            "business_code"
                        ]
                        or ""
                    ),
                    "asset_name": (
                        record[
                            "asset_name"
                        ]
                        or ""
                    ),
                    "canal_name": (
                        record[
                            "canal_name"
                        ]
                        or ""
                    ),
                    "engineering_position": (
                        record[
                            "engineering_position"
                        ]
                        or ""
                    ),
                    "media_uid": (
                        media.get(
                            "media_uid",
                            "",
                        )
                    ),
                    "media_kind": (
                        media.get(
                            "media_kind",
                            "",
                        )
                    ),
                    "media_kind_label": (
                        MEDIA_KIND_LABELS.get(
                            media.get(
                                "media_kind",
                                "",
                            ),
                            media.get(
                                "media_kind",
                                "",
                            ),
                        )
                    ),
                    "media_role": (
                        media.get(
                            "media_role",
                            "",
                        )
                    ),
                    "media_role_label": (
                        MEDIA_ROLE_LABELS.get(
                            media.get(
                                "media_role",
                                "",
                            ),
                            media.get(
                                "media_role",
                                "",
                            ),
                        )
                    ),
                    "part_name": (
                        media.get(
                            "part_name",
                            "",
                        )
                        or ""
                    ),
                    "item_code": (
                        media.get(
                            "item_code",
                            "",
                        )
                        or ""
                    ),
                    "sequence_no": (
                        media.get(
                            "sequence_no",
                            "",
                        )
                    ),
                    "original_filename": (
                        media.get(
                            "original_filename",
                            "",
                        )
                    ),
                    "relative_path": "",
                    "status": "失败",
                    "error": str(error),
                }
            )

    return {
        "entries": entries,
        "errors": errors,
    }
