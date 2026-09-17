from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.engineering_batch_export import (
    sanitize_filename,
)
from services.engineering_media_export import (
    build_media_archive_filename,
)
from services.survey_media import (
    get_survey_media,
)


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

_ALLOWED_SEVERITIES = {
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SEVERITY_INFO,
}


@dataclass(frozen=True)
class PreflightIssue:
    severity: str
    code: str
    message: str
    survey_record_id: int | None = None
    business_code: str = ""
    media_id: int | None = None
    original_filename: str = ""

    def __post_init__(self):
        if self.severity not in (
            _ALLOWED_SEVERITIES
        ):
            raise ValueError(
                "无效的预检问题级别。"
            )


@dataclass(frozen=True)
class BatchPreflightReport:
    issues: tuple[PreflightIssue, ...]

    @property
    def error_count(self):
        return sum(
            1
            for issue in self.issues
            if (
                issue.severity
                == SEVERITY_ERROR
            )
        )

    @property
    def warning_count(self):
        return sum(
            1
            for issue in self.issues
            if (
                issue.severity
                == SEVERITY_WARNING
            )
        )

    @property
    def info_count(self):
        return sum(
            1
            for issue in self.issues
            if (
                issue.severity
                == SEVERITY_INFO
            )
        )

    @property
    def can_export(self):
        return self.error_count == 0

    def format_preview(
        self,
        *,
        limit=8,
    ):
        visible = [
            issue
            for issue in self.issues
            if issue.severity
            in (
                SEVERITY_ERROR,
                SEVERITY_WARNING,
            )
        ]

        if not visible:
            return "未发现需要处理的问题。"

        lines = []

        labels = {
            SEVERITY_ERROR: "错误",
            SEVERITY_WARNING: "警告",
            SEVERITY_INFO: "提示",
        }

        for issue in visible[:limit]:
            identity = (
                issue.business_code
                or (
                    "记录"
                    f"{issue.survey_record_id}"
                    if (
                        issue.survey_record_id
                        is not None
                    )
                    else "当前范围"
                )
            )

            lines.append(
                (
                    f"• [{labels[issue.severity]}] "
                    f"{identity}："
                    f"{issue.message}"
                )
            )

        remaining = (
            len(visible)
            - len(lines)
        )

        if remaining > 0:
            lines.append(
                (
                    "• 另有 "
                    f"{remaining} 项未展开显示。"
                )
            )

        return "\n".join(lines)


def _record_definition_map(
    plan,
):
    return {
        group.definition.form_code:
        group.definition
        for group in plan.groups
    }


def _archive_relative_path(
    *,
    record,
    media,
):
    """
    使用与正式成果导出一致的目录和文件命名规则，
    仅计算相对路径，不创建目录、不复制文件。
    """

    canal_name = sanitize_filename(
        record["canal_name"],
        fallback="未注明渠系",
    )

    position = sanitize_filename(
        record[
            "engineering_position"
        ],
        fallback="未注明位置",
    )

    asset_name = sanitize_filename(
        record["asset_name"],
        fallback="未命名工程",
    )

    filename = (
        build_media_archive_filename(
            record=record,
            media=media,
        )
    )

    return (
        Path(canal_name)
        / f"{position}_{asset_name}"
        / filename
    )


def inspect_batch_export_plan(
    plan,
):
    """
    对正式成果导出范围执行影像资料技术预检。

    当前只检查“已经确定且不会因甲方规则变化而失效”的
    技术完整性问题，不在这里硬编码尚未确认的影像数量要求。

    阻断导出的错误：
    - 托管文件缺失；
    - 托管文件大小与数据库元数据不一致；
    - 正式归档路径无法生成；
    - 两个影像最终会写入同一个正式归档路径。

    可继续导出的警告：
    - 调查记录没有任何影像；
    - 影像未填写工程部位；
    - “问题/隐患”影像没有关联分项评价；
    - 关联评价项已不属于当前调查表定义；
    - 同一调查记录存在重复影像序号。

    不检查：
    - 每个工程必须几张照片；
    - 是否必须有全景照片；
    - 某等级是否必须有问题照片。

    上述数量/业务规则待甲方最终确认后再加入。
    """

    definition_by_form = (
        _record_definition_map(
            plan
        )
    )

    issues = []

    archive_path_owners = {}

    for record in plan.records:
        survey_record_id = int(
            record["survey_record_id"]
        )

        business_code = str(
            record["business_code"]
            or ""
        )

        form_code = str(
            record["form_code"]
        )

        definition = (
            definition_by_form.get(
                form_code
            )
        )

        valid_item_codes = set()

        if definition is not None:
            valid_item_codes = {
                item["item_code"]
                for item in (
                    definition
                    .evaluation_items
                )
            }

        media_records = tuple(
            get_survey_media(
                survey_record_id
            )
        )

        if not media_records:
            issues.append(
                PreflightIssue(
                    severity=(
                        SEVERITY_WARNING
                    ),
                    code="NO_MEDIA",
                    message=(
                        "当前调查记录没有关联"
                        "任何影像资料。"
                    ),
                    survey_record_id=(
                        survey_record_id
                    ),
                    business_code=(
                        business_code
                    ),
                )
            )

            continue

        sequence_counts = {}

        for media in media_records:
            sequence_no = media.get(
                "sequence_no"
            )

            sequence_counts[
                sequence_no
            ] = (
                sequence_counts.get(
                    sequence_no,
                    0,
                )
                + 1
            )

            media_id = media.get("id")

            try:
                media_id = (
                    int(media_id)
                    if media_id is not None
                    else None
                )
            except (
                TypeError,
                ValueError,
            ):
                media_id = None

            original_filename = str(
                media.get(
                    "original_filename"
                )
                or ""
            )

            source_path = Path(
                media["absolute_path"]
            )

            if not source_path.exists():
                issues.append(
                    PreflightIssue(
                        severity=(
                            SEVERITY_ERROR
                        ),
                        code=(
                            "MISSING_MANAGED_FILE"
                        ),
                        message=(
                            "数据库中存在影像记录，"
                            "但系统托管文件已经缺失："
                            f"{original_filename}"
                        ),
                        survey_record_id=(
                            survey_record_id
                        ),
                        business_code=(
                            business_code
                        ),
                        media_id=media_id,
                        original_filename=(
                            original_filename
                        ),
                    )
                )

            elif source_path.is_file():
                expected_size = media.get(
                    "file_size"
                )

                if expected_size is not None:
                    try:
                        expected_size = int(
                            expected_size
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        expected_size = None

                if (
                    expected_size is not None
                    and source_path.stat().st_size
                    != expected_size
                ):
                    issues.append(
                        PreflightIssue(
                            severity=(
                                SEVERITY_ERROR
                            ),
                            code=(
                                "FILE_SIZE_MISMATCH"
                            ),
                            message=(
                                "系统托管影像文件大小"
                                "与数据库记录不一致："
                                f"{original_filename}"
                            ),
                            survey_record_id=(
                                survey_record_id
                            ),
                            business_code=(
                                business_code
                            ),
                            media_id=media_id,
                            original_filename=(
                                original_filename
                            ),
                        )
                    )

            if not str(
                media.get(
                    "part_name"
                )
                or ""
            ).strip():
                issues.append(
                    PreflightIssue(
                        severity=(
                            SEVERITY_WARNING
                        ),
                        code=(
                            "MISSING_PART_NAME"
                        ),
                        message=(
                            "影像尚未填写工程部位："
                            f"{original_filename}"
                        ),
                        survey_record_id=(
                            survey_record_id
                        ),
                        business_code=(
                            business_code
                        ),
                        media_id=media_id,
                        original_filename=(
                            original_filename
                        ),
                    )
                )

            item_code = str(
                media.get(
                    "item_code"
                )
                or ""
            ).strip()

            if (
                media.get(
                    "media_role"
                )
                == "problem"
                and not item_code
            ):
                issues.append(
                    PreflightIssue(
                        severity=(
                            SEVERITY_WARNING
                        ),
                        code=(
                            "PROBLEM_WITHOUT_ITEM"
                        ),
                        message=(
                            "“问题/隐患”影像"
                            "尚未关联分项评价："
                            f"{original_filename}"
                        ),
                        survey_record_id=(
                            survey_record_id
                        ),
                        business_code=(
                            business_code
                        ),
                        media_id=media_id,
                        original_filename=(
                            original_filename
                        ),
                    )
                )

            if (
                item_code
                and definition is not None
                and item_code
                not in valid_item_codes
            ):
                issues.append(
                    PreflightIssue(
                        severity=(
                            SEVERITY_WARNING
                        ),
                        code=(
                            "UNKNOWN_ITEM_CODE"
                        ),
                        message=(
                            "影像关联的分项评价"
                            "已不属于当前调查表定义："
                            f"{item_code}"
                        ),
                        survey_record_id=(
                            survey_record_id
                        ),
                        business_code=(
                            business_code
                        ),
                        media_id=media_id,
                        original_filename=(
                            original_filename
                        ),
                    )
                )

            try:
                relative_path = (
                    _archive_relative_path(
                        record=record,
                        media=media,
                    )
                )

            except Exception as error:
                issues.append(
                    PreflightIssue(
                        severity=(
                            SEVERITY_ERROR
                        ),
                        code=(
                            "ARCHIVE_PATH_INVALID"
                        ),
                        message=(
                            "无法生成正式影像归档路径："
                            f"{original_filename}；"
                            f"{error}"
                        ),
                        survey_record_id=(
                            survey_record_id
                        ),
                        business_code=(
                            business_code
                        ),
                        media_id=media_id,
                        original_filename=(
                            original_filename
                        ),
                    )
                )

                continue

            archive_key = (
                relative_path
                .as_posix()
                .casefold()
            )

            previous = (
                archive_path_owners.get(
                    archive_key
                )
            )

            if previous is not None:
                issues.append(
                    PreflightIssue(
                        severity=(
                            SEVERITY_ERROR
                        ),
                        code=(
                            "DUPLICATE_ARCHIVE_PATH"
                        ),
                        message=(
                            "多个影像将生成相同的"
                            "正式归档路径："
                            f"{relative_path.as_posix()}；"
                            "请调整部位或影像序号。"
                        ),
                        survey_record_id=(
                            survey_record_id
                        ),
                        business_code=(
                            business_code
                        ),
                        media_id=media_id,
                        original_filename=(
                            original_filename
                        ),
                    )
                )

            else:
                archive_path_owners[
                    archive_key
                ] = (
                    survey_record_id,
                    media_id,
                )

        duplicate_sequences = sorted(
            (
                sequence
                for (
                    sequence,
                    count,
                )
                in sequence_counts.items()
                if count > 1
            ),
            key=lambda value:
            str(value),
        )

        for sequence_no in (
            duplicate_sequences
        ):
            issues.append(
                PreflightIssue(
                    severity=(
                        SEVERITY_WARNING
                    ),
                    code=(
                        "DUPLICATE_SEQUENCE"
                    ),
                    message=(
                        "同一调查记录存在重复"
                        "影像序号："
                        f"{sequence_no}。"
                    ),
                    survey_record_id=(
                        survey_record_id
                    ),
                    business_code=(
                        business_code
                    ),
                )
            )

    return BatchPreflightReport(
        issues=tuple(issues)
    )
