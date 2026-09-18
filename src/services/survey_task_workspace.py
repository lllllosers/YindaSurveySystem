from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import shutil

import database

from services.survey_task_package_reader import (
    load_survey_task_package,
)


@dataclass(frozen=True)
class SurveyTaskReceiveResult:
    task_workspace_id: int
    task_uid: str
    package_uid: str
    project_id: int
    survey_batch_id: int
    organization_unit_id: int
    task_name: str
    selected_management_scope_count: int
    managed_package_path: Path
    created_project: bool
    created_batch: bool
    already_received: bool


def _clean_text(value):
    return str(
        value or ""
    ).strip()


def _require_text(
    value,
    field_name,
):
    text = _clean_text(
        value
    )

    if not text:
        raise ValueError(
            f"{field_name}不能为空。"
        )

    return text


def ensure_survey_task_workspace_schema():
    """
    建立“已接收调查任务”本地工作区。

    Stage 12.1 只建立一个最小闭环：
    .ydtask -> 本地任务工作区 -> 当前项目/批次。

    不创建 EngineeringAsset / SurveyRecord，
    不自动生成调查数据。
    """

    with database.get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                survey_task_workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    task_uid TEXT NOT NULL UNIQUE,
                    source_package_uid TEXT NOT NULL UNIQUE,

                    project_id INTEGER NOT NULL,
                    survey_batch_id INTEGER NOT NULL,
                    organization_unit_id INTEGER NOT NULL,

                    task_name TEXT NOT NULL,
                    notes TEXT,

                    managed_package_relative_path TEXT
                        NOT NULL,
                    source_package_sha256 TEXT
                        NOT NULL,

                    is_current INTEGER NOT NULL
                        DEFAULT 0
                        CHECK (is_current IN (0, 1)),

                    received_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),

                    FOREIGN KEY (project_id)
                        REFERENCES projects(id),

                    FOREIGN KEY (survey_batch_id)
                        REFERENCES survey_batches(id),

                    FOREIGN KEY (organization_unit_id)
                        REFERENCES organization_units(id)
                );

            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_survey_task_workspaces_current
            ON survey_task_workspaces(is_current)
            WHERE is_current = 1;

            CREATE TABLE IF NOT EXISTS
                survey_task_workspace_canals (
                    task_workspace_id INTEGER NOT NULL,
                    canal_unit_id INTEGER NOT NULL,

                    PRIMARY KEY (
                        task_workspace_id,
                        canal_unit_id
                    ),

                    FOREIGN KEY (task_workspace_id)
                        REFERENCES survey_task_workspaces(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (canal_unit_id)
                        REFERENCES canal_units(id)
                );

            CREATE INDEX IF NOT EXISTS
                idx_task_workspace_canals_canal
            ON survey_task_workspace_canals(
                canal_unit_id,
                task_workspace_id
            );
            """
        )


def _sha256_file(
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

            digest.update(
                chunk
            )

    return digest.hexdigest()


def _managed_task_package_path(
    *,
    task_uid,
    package_uid,
):
    relative_path = Path(
        "task_packages",
        task_uid,
        f"{package_uid}.ydtask",
    )

    return (
        relative_path,
        database.DATA_DIR
        / relative_path,
    )


def _copy_package_into_managed_storage(
    source_path,
    *,
    task_uid,
    package_uid,
    expected_sha256,
):
    (
        relative_path,
        destination,
    ) = _managed_task_package_path(
        task_uid=task_uid,
        package_uid=package_uid,
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.exists():
        if (
            _sha256_file(destination)
            != expected_sha256
        ):
            raise ValueError(
                "本地任务包托管文件与待接收包"
                "发生内容冲突。"
            )

        return (
            relative_path,
            destination,
            False,
        )

    temporary = destination.with_name(
        destination.name
        + ".receiving"
    )

    temporary.unlink(
        missing_ok=True
    )

    shutil.copy2(
        source_path,
        temporary,
    )

    actual_hash = (
        _sha256_file(
            temporary
        )
    )

    if actual_hash != expected_sha256:
        temporary.unlink(
            missing_ok=True
        )

        raise ValueError(
            "任务包复制后的 SHA-256 校验失败。"
        )

    os.replace(
        temporary,
        destination,
    )

    return (
        relative_path,
        destination,
        True,
    )


def _ensure_local_project(
    connection,
    project,
):
    project_uid = _require_text(
        project.get(
            "project_uid"
        ),
        "project_uid",
    )

    project_name = _require_text(
        project.get(
            "name"
        ),
        "项目名称",
    )

    existing = connection.execute(
        """
        SELECT
            id,
            project_uid,
            name,
            status
        FROM projects
        WHERE project_uid = ?
        """,
        (
            project_uid,
        ),
    ).fetchone()

    if existing is not None:
        return (
            int(
                existing["id"]
            ),
            False,
        )

    name_conflict = (
        connection.execute(
            """
            SELECT
                id,
                project_uid
            FROM projects
            WHERE name = ?
            LIMIT 1
            """,
            (
                project_name,
            ),
        ).fetchone()
    )

    if name_conflict is not None:
        raise ValueError(
            "本机已存在同名但 UID 不同的项目，"
            "不能自动合并。"
        )

    cursor = connection.execute(
        """
        INSERT INTO projects (
            project_uid,
            name,
            short_name,
            status
        )
        VALUES (?, ?, ?, 'inactive')
        """,
        (
            project_uid,
            project_name,
            (
                _clean_text(
                    project.get(
                        "short_name"
                    )
                )
                or None
            ),
        ),
    )

    return (
        int(
            cursor.lastrowid
        ),
        True,
    )


def _ensure_local_batch(
    connection,
    *,
    project_id,
    survey_batch,
):
    batch_uid = _require_text(
        survey_batch.get(
            "survey_batch_uid"
        ),
        "survey_batch_uid",
    )

    batch_name = _require_text(
        survey_batch.get(
            "batch_name"
        ),
        "调查批次名称",
    )

    batch_code = _require_text(
        survey_batch.get(
            "batch_code"
        ),
        "调查批次代码",
    )

    existing = connection.execute(
        """
        SELECT
            id,
            project_id,
            status
        FROM survey_batches
        WHERE survey_batch_uid = ?
        """,
        (
            batch_uid,
        ),
    ).fetchone()

    if existing is not None:
        if (
            int(
                existing[
                    "project_id"
                ]
            )
            != int(project_id)
        ):
            raise ValueError(
                "调查批次 UID 已存在，"
                "但所属项目不一致。"
            )

        if existing["status"] in (
            "completed",
            "archived",
        ):
            raise ValueError(
                "本机对应调查批次已经结束，"
                "不能接收为当前录入任务。"
            )

        return (
            int(
                existing["id"]
            ),
            False,
        )

    code_conflict = (
        connection.execute(
            """
            SELECT
                id,
                survey_batch_uid
            FROM survey_batches
            WHERE project_id = ?
              AND batch_code = ?
            LIMIT 1
            """,
            (
                project_id,
                batch_code,
            ),
        ).fetchone()
    )

    if code_conflict is not None:
        raise ValueError(
            "本机当前项目下已存在相同批次代码"
            "但 UID 不同的调查批次，不能自动合并。"
        )

    cursor = connection.execute(
        """
        INSERT INTO survey_batches (
            survey_batch_uid,
            project_id,
            batch_name,
            batch_code,
            start_date,
            end_date,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'draft')
        """,
        (
            batch_uid,
            project_id,
            batch_name,
            batch_code,
            (
                _clean_text(
                    survey_batch.get(
                        "start_date"
                    )
                )
                or None
            ),
            (
                _clean_text(
                    survey_batch.get(
                        "end_date"
                    )
                )
                or None
            ),
        ),
    )

    return (
        int(
            cursor.lastrowid
        ),
        True,
    )


def _resolve_local_assignment(
    connection,
    *,
    assignment,
):
    office_uid = _require_text(
        assignment.get(
            "organization_unit_uid"
        ),
        "任务管理单位 UID",
    )

    department_uid = _require_text(
        assignment.get(
            "department_uid"
        ),
        "任务基层处 UID",
    )

    office = connection.execute(
        """
        SELECT
            id,
            parent_id,
            name,
            unit_type,
            status
        FROM organization_units
        WHERE organization_unit_uid = ?
        """,
        (
            office_uid,
        ),
    ).fetchone()

    if office is None:
        raise ValueError(
            "本机正式主数据中找不到任务管理单位。"
            "请先确认软件版本和正式主数据一致。"
        )

    if (
        office["unit_type"]
        != "water_office"
        or office["status"]
        != "active"
    ):
        raise ValueError(
            "任务管理单位在本机不是可用的末级管理单位。"
        )

    department = connection.execute(
        """
        SELECT
            id,
            organization_unit_uid,
            unit_type,
            status
        FROM organization_units
        WHERE id = ?
        """,
        (
            office["parent_id"],
        ),
    ).fetchone()

    if (
        department is None
        or department[
            "unit_type"
        ]
        != "department"
        or department[
            "organization_unit_uid"
        ]
        != department_uid
    ):
        raise ValueError(
            "任务管理单位与所属基层处关系"
            "和本机正式主数据不一致。"
        )

    return int(
        office["id"]
    )


def _resolve_selected_canals(
    connection,
    *,
    selected_management_scope_uids,
    management_scopes,
    organization_unit_id,
):
    """
    Stage 14.4.1 过渡投影：新 .ydtask 已完全以 management scope 快照为任务事实源。
    当前 workspace 表仍暂存 CanalUnit，14.4.2 再升级为 scope snapshot 表。

    这里明确不读取 canal_units.organization_unit_id，也不要求接收端预先存在
    发送端人工创建的 scope；只按包内冻结快照解析物理 CanalUnit。
    """
    if not isinstance(selected_management_scope_uids, list) or not selected_management_scope_uids:
        raise ValueError("任务没有有效的分管范围。")

    office = connection.execute(
        """
        SELECT organization_unit_uid
        FROM organization_units
        WHERE id = ?
        """,
        (int(organization_unit_id),),
    ).fetchone()
    if office is None:
        raise ValueError("本机找不到任务管理单位。")

    office_uid = _require_text(office["organization_unit_uid"], "任务管理单位 UID")

    scope_by_uid = {}
    for item in management_scopes:
        uid = _require_text(item.get("management_scope_uid"), "management_scope_uid")
        if uid in scope_by_uid:
            raise ValueError("任务分管范围快照包含重复 UID。")
        scope_by_uid[uid] = item

    resolved = []
    for raw_uid in selected_management_scope_uids:
        uid = _require_text(raw_uid, "management_scope_uid")
        item = scope_by_uid.get(uid)
        if item is None:
            raise ValueError(f"任务缺少选定分管范围快照：{uid}。")

        item_office_uid = _require_text(
            item.get("organization_unit_uid"),
            "分管范围管理单位 UID",
        )
        if item_office_uid != office_uid:
            raise ValueError("任务分管范围与管理单位不一致。")

        canal_uid = _require_text(item.get("canal_uid"), "分管范围 canal_uid")
        row = connection.execute(
            """
            SELECT id, name, status
            FROM canal_units
            WHERE canal_unit_uid = ?
            """,
            (canal_uid,),
        ).fetchone()
        if row is None:
            raise ValueError(f"本机正式主数据中找不到任务渠系：{canal_uid}。")
        if row["status"] != "active":
            raise ValueError(f"任务包含已停用渠系：{row['name']}。")

        canal_id = int(row["id"])
        if canal_id not in resolved:
            resolved.append(canal_id)

    return tuple(resolved)


def _validate_local_forms(
    connection,
    forms,
):
    if not forms:
        raise ValueError(
            "任务包没有表单参考信息。"
        )

    for item in forms:
        form_code = _require_text(
            item.get(
                "form_code"
            ),
            "form_code",
        )

        version_code = _require_text(
            item.get(
                "version_code"
            ),
            (
                f"{form_code} "
                "version_code"
            ),
        )

        row = connection.execute(
            """
            SELECT
                fd.id,
                fv.id AS form_version_id
            FROM form_definitions AS fd
            JOIN form_versions AS fv
              ON fv.form_definition_id = fd.id
            WHERE fd.form_code = ?
              AND fv.version_code = ?
              AND fd.is_enabled = 1
            LIMIT 1
            """,
            (
                form_code,
                version_code,
            ),
        ).fetchone()

        if row is None:
            raise ValueError(
                "本机缺少任务要求的调查表版本："
                f"{form_code} / {version_code}。"
                "请先更新软件或表单定义。"
            )


def _activate_context(
    connection,
    *,
    project_id,
    survey_batch_id,
):
    connection.execute(
        """
        UPDATE projects
        SET
            status = 'inactive',
            updated_at = datetime(
                'now',
                'localtime'
            )
        WHERE status = 'active'
          AND id != ?
        """,
        (
            project_id,
        ),
    )

    connection.execute(
        """
        UPDATE projects
        SET
            status = 'active',
            updated_at = datetime(
                'now',
                'localtime'
            )
        WHERE id = ?
        """,
        (
            project_id,
        ),
    )

    connection.execute(
        """
        UPDATE survey_batches
        SET
            status = 'draft',
            updated_at = datetime(
                'now',
                'localtime'
            )
        WHERE project_id = ?
          AND status = 'active'
          AND id != ?
        """,
        (
            project_id,
            survey_batch_id,
        ),
    )

    connection.execute(
        """
        UPDATE survey_batches
        SET
            status = 'active',
            updated_at = datetime(
                'now',
                'localtime'
            )
        WHERE id = ?
          AND status IN (
              'draft',
              'active'
          )
        """,
        (
            survey_batch_id,
        ),
    )


def _workspace_row_to_dict(
    row,
):
    if row is None:
        return None

    return {
        key: row[key]
        for key in row.keys()
    }


def get_current_task_workspace():
    ensure_survey_task_workspace_schema()

    with database.get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                stw.id,
                stw.task_uid,
                stw.source_package_uid,
                stw.project_id,
                stw.survey_batch_id,
                stw.organization_unit_id,
                stw.task_name,
                stw.notes,
                stw.managed_package_relative_path,
                stw.source_package_sha256,
                stw.is_current,
                stw.received_at,
                p.name AS project_name,
                sb.batch_name,
                ou.name AS organization_name,
                ou.parent_id AS department_id
            FROM survey_task_workspaces AS stw
            JOIN projects AS p
              ON p.id = stw.project_id
            JOIN survey_batches AS sb
              ON sb.id = stw.survey_batch_id
            JOIN organization_units AS ou
              ON ou.id = stw.organization_unit_id
            WHERE stw.is_current = 1
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            return None

        result = _workspace_row_to_dict(
            row
        )

        canal_rows = (
            connection.execute(
                """
                SELECT
                    cu.id,
                    cu.canal_unit_uid,
                    cu.name,
                    cu.canal_level,
                    cu.sort_order
                FROM survey_task_workspace_canals
                    AS stwc
                JOIN canal_units AS cu
                  ON cu.id = stwc.canal_unit_id
                WHERE stwc.task_workspace_id = ?
                ORDER BY
                    CASE
                        WHEN cu.sort_order > 0
                        THEN cu.sort_order
                        ELSE 1000000 + cu.id
                    END,
                    cu.id
                """,
                (
                    int(
                        row["id"]
                    ),
                ),
            ).fetchall()
        )

    result["canals"] = tuple(
        _workspace_row_to_dict(
            item
        )
        for item in canal_rows
    )

    result[
        "managed_package_path"
    ] = (
        database.DATA_DIR
        / result[
            "managed_package_relative_path"
        ]
    )

    return result


def receive_survey_task_package(
    package_path,
    *,
    make_current=True,
):
    """
    接收一个 .ydtask，并建立本机录入工作区。

    处理顺序：
    1. 使用 Stage 10.2 完整校验任务包；
    2. 复用本机确定性正式主数据匹配管理单位/渠系；
    3. 按包内稳定 UID 建立或复用项目、调查批次；
    4. 保存任务工作区及渠系范围；
    5. 把原 .ydtask 复制到 local_data/task_packages 托管；
    6. 默认切换为当前项目/批次/任务。

    不创建工程对象和调查记录。
    """

    ensure_survey_task_workspace_schema()

    source_path = Path(
        package_path
    ).expanduser()

    if not source_path.exists():
        raise FileNotFoundError(
            "没有找到需要接收的调查任务包。"
        )

    if not source_path.is_file():
        raise ValueError(
            "调查任务包路径必须是文件。"
        )

    contents = (
        load_survey_task_package(
            source_path
        )
    )

    manifest = contents.manifest
    task = contents.task

    task_uid = _require_text(
        task.get(
            "task_uid"
        ),
        "task_uid",
    )

    package_uid = _require_text(
        manifest.get(
            "package_uid"
        ),
        "package_uid",
    )

    project = task.get(
        "project"
    )

    survey_batch = task.get(
        "survey_batch"
    )

    assignment = task.get(
        "assignment"
    )

    scope = task.get(
        "scope"
    )

    if not isinstance(
        project,
        dict,
    ):
        raise ValueError(
            "任务包 project 结构无效。"
        )

    if not isinstance(
        survey_batch,
        dict,
    ):
        raise ValueError(
            "任务包 survey_batch 结构无效。"
        )

    if not isinstance(
        assignment,
        dict,
    ):
        raise ValueError(
            "任务包 assignment 结构无效。"
        )

    if not isinstance(
        scope,
        dict,
    ):
        raise ValueError(
            "任务包 scope 结构无效。"
        )

    package_hash = (
        _sha256_file(
            source_path
        )
    )

    copied_new_file = False
    managed_absolute_path = None

    # 先完成数据库侧全部可验证项，
    # 但暂不写 workspace。
    with database.get_connection() as connection:
        (
            project_id,
            created_project,
        ) = _ensure_local_project(
            connection,
            project,
        )

        (
            survey_batch_id,
            created_batch,
        ) = _ensure_local_batch(
            connection,
            project_id=project_id,
            survey_batch=(
                survey_batch
            ),
        )

        organization_unit_id = (
            _resolve_local_assignment(
                connection,
                assignment=assignment,
            )
        )

        canal_ids = (
            _resolve_selected_canals(connection, selected_management_scope_uids=scope.get('selected_management_scope_uids'), management_scopes=contents.management_scopes, organization_unit_id=organization_unit_id)
        )

        _validate_local_forms(
            connection,
            contents.forms,
        )

        existing = connection.execute(
            """
            SELECT
                id,
                task_uid,
                source_package_uid,
                project_id,
                survey_batch_id,
                organization_unit_id,
                task_name,
                managed_package_relative_path,
                source_package_sha256
            FROM survey_task_workspaces
            WHERE task_uid = ?
            """,
            (
                task_uid,
            ),
        ).fetchone()

        if existing is not None:
            existing_canal_ids = {
                int(
                    row[
                        "canal_unit_id"
                    ]
                )
                for row in (
                    connection.execute(
                        """
                        SELECT canal_unit_id
                        FROM survey_task_workspace_canals
                        WHERE task_workspace_id = ?
                        """,
                        (
                            int(
                                existing["id"]
                            ),
                        ),
                    ).fetchall()
                )
            }

            if (
                int(
                    existing[
                        "project_id"
                    ]
                )
                != project_id
                or int(
                    existing[
                        "survey_batch_id"
                    ]
                )
                != survey_batch_id
                or int(
                    existing[
                        "organization_unit_id"
                    ]
                )
                != organization_unit_id
                or existing_canal_ids
                != set(canal_ids)
            ):
                raise ValueError(
                    "本机已存在同 task_uid 的任务，"
                    "但任务上下文不同，不能覆盖。"
                )

            workspace_id = int(
                existing["id"]
            )

            existing_relative_path = Path(
                existing[
                    "managed_package_relative_path"
                ]
            )

            managed_absolute_path = (
                database.DATA_DIR
                / existing_relative_path
            )

            if (
                existing[
                    "source_package_sha256"
                ]
                != package_hash
            ):
                raise ValueError(
                    "本机已接收同 task_uid，"
                    "但任务包文件内容不同。"
                )

            if not managed_absolute_path.exists():
                (
                    _,
                    managed_absolute_path,
                    copied_new_file,
                ) = _copy_package_into_managed_storage(
                    source_path,
                    task_uid=task_uid,
                    package_uid=(
                        existing[
                            "source_package_uid"
                        ]
                    ),
                    expected_sha256=(
                        package_hash
                    ),
                )

            if make_current:
                connection.execute(
                    """
                    UPDATE survey_task_workspaces
                    SET is_current = 0
                    WHERE is_current = 1
                      AND id != ?
                    """,
                    (
                        workspace_id,
                    ),
                )

                connection.execute(
                    """
                    UPDATE survey_task_workspaces
                    SET is_current = 1
                    WHERE id = ?
                    """,
                    (
                        workspace_id,
                    ),
                )

                _activate_context(
                    connection,
                    project_id=project_id,
                    survey_batch_id=(
                        survey_batch_id
                    ),
                )

            return SurveyTaskReceiveResult(
                task_workspace_id=(
                    workspace_id
                ),
                task_uid=task_uid,
                package_uid=(
                    existing[
                        "source_package_uid"
                    ]
                ),
                project_id=project_id,
                survey_batch_id=(
                    survey_batch_id
                ),
                organization_unit_id=(
                    organization_unit_id
                ),
                task_name=(
                    existing[
                        "task_name"
                    ]
                ),
                selected_management_scope_count=(
                    len(
                    scope.get(
                        "selected_management_scope_uids"
                    )
                    or []
                )
                ),
                managed_package_path=(
                    managed_absolute_path
                ),
                created_project=(
                    created_project
                ),
                created_batch=(
                    created_batch
                ),
                already_received=True,
            )

    # 在事务之外把来源任务包复制入托管目录。
    # 如果随后数据库写入失败，会删除本次新复制的文件。
    (
        managed_relative_path,
        managed_absolute_path,
        copied_new_file,
    ) = _copy_package_into_managed_storage(
        source_path,
        task_uid=task_uid,
        package_uid=package_uid,
        expected_sha256=(
            package_hash
        ),
    )

    try:
        with database.get_connection() as connection:
            # 上一个验证事务可能新建了 project/batch，
            # 再按 UID 读取，避免依赖临时整数。
            project_row = connection.execute(
                """
                SELECT id
                FROM projects
                WHERE project_uid = ?
                """,
                (
                    project[
                        "project_uid"
                    ],
                ),
            ).fetchone()

            batch_row = connection.execute(
                """
                SELECT id
                FROM survey_batches
                WHERE survey_batch_uid = ?
                """,
                (
                    survey_batch[
                        "survey_batch_uid"
                    ],
                ),
            ).fetchone()

            office_row = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE organization_unit_uid = ?
                """,
                (
                    assignment[
                        "organization_unit_uid"
                    ],
                ),
            ).fetchone()

            if (
                project_row is None
                or batch_row is None
                or office_row is None
            ):
                raise RuntimeError(
                    "接收任务时本地上下文解析失败。"
                )

            project_id = int(
                project_row["id"]
            )
            survey_batch_id = int(
                batch_row["id"]
            )
            organization_unit_id = int(
                office_row["id"]
            )

            canal_ids = (
                _resolve_selected_canals(connection, selected_management_scope_uids=scope.get('selected_management_scope_uids'), management_scopes=contents.management_scopes, organization_unit_id=organization_unit_id)
            )

            if make_current:
                connection.execute(
                    """
                    UPDATE survey_task_workspaces
                    SET is_current = 0
                    WHERE is_current = 1
                    """
                )

            cursor = connection.execute(
                """
                INSERT INTO survey_task_workspaces (
                    task_uid,
                    source_package_uid,
                    project_id,
                    survey_batch_id,
                    organization_unit_id,
                    task_name,
                    notes,
                    managed_package_relative_path,
                    source_package_sha256,
                    is_current
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_uid,
                    package_uid,
                    project_id,
                    survey_batch_id,
                    organization_unit_id,
                    _require_text(
                        task.get(
                            "task_name"
                        ),
                        "任务名称",
                    ),
                    (
                        _clean_text(
                            task.get(
                                "notes"
                            )
                        )
                        or None
                    ),
                    managed_relative_path.as_posix(),
                    package_hash,
                    (
                        1
                        if make_current
                        else 0
                    ),
                ),
            )

            workspace_id = int(
                cursor.lastrowid
            )

            for canal_id in canal_ids:
                connection.execute(
                    """
                    INSERT INTO
                        survey_task_workspace_canals (
                            task_workspace_id,
                            canal_unit_id
                        )
                    VALUES (?, ?)
                    """,
                    (
                        workspace_id,
                        canal_id,
                    ),
                )

            if make_current:
                _activate_context(
                    connection,
                    project_id=project_id,
                    survey_batch_id=(
                        survey_batch_id
                    ),
                )

    except Exception:
        if copied_new_file:
            try:
                managed_absolute_path.unlink(
                    missing_ok=True
                )
            except Exception:
                pass

        raise

    return SurveyTaskReceiveResult(
        task_workspace_id=(
            workspace_id
        ),
        task_uid=task_uid,
        package_uid=package_uid,
        project_id=project_id,
        survey_batch_id=(
            survey_batch_id
        ),
        organization_unit_id=(
            organization_unit_id
        ),
        task_name=_require_text(
            task.get(
                "task_name"
            ),
            "任务名称",
        ),
        selected_management_scope_count=(
            len(
                    scope.get(
                        "selected_management_scope_uids"
                    )
                    or []
                )
        ),
        managed_package_path=(
            managed_absolute_path
        ),
        created_project=(
            created_project
        ),
        created_batch=(
            created_batch
        ),
        already_received=False,
    )
