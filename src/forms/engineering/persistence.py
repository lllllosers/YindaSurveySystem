from database import (
    create_engineering_survey,
    create_range_engineering_survey,
    get_inspection_results,
    get_point_engineering_record,
    get_range_engineering_record,
    update_point_engineering_survey,
    update_range_engineering_survey,
    complete_engineering_survey_record,
)

from forms.engineering.models import (
    EngineeringFormDefinition,
)

from forms.engineering.validation import (
    validate_completion,
)


def create_engineering_record(
    definition: EngineeringFormDefinition,
    *,
    project_id: int,
    survey_batch_id: int,
    form_version_id: int,
    organization_unit_id: int,
    canal_unit_id: int,
    business_code: str,
    payload: dict,
    source_management_scope_uid: str | None = None,
) -> dict:
    """
    根据 EngineeringFormDefinition
    创建一条工程调查草稿。
    """

    asset_name = payload.get(
        "asset_name"
    )
    record_data = (
        payload.get("record_data")
        or {}
    )
    position = (
        payload.get("position")
        or {}
    )
    inspection_results = (
        payload.get(
            "inspection_results"
        )
        or []
    )

    survey_date = payload.get(
        "survey_date"
    )
    overall_grade = payload.get(
        "overall_grade"
    )
    survey_comment = payload.get(
        "survey_comment"
    )

    if (
        definition.position.kind
        == "point"
    ):
        return create_engineering_survey(
            project_id=project_id,
            survey_batch_id=(
                survey_batch_id
            ),
            form_version_id=(
                form_version_id
            ),
            asset_name=asset_name,
            asset_type=(
                definition.asset_type
            ),
            organization_unit_id=(
                organization_unit_id
            ),
            canal_unit_id=(
                canal_unit_id
            ),
            business_code=(
                business_code
            ),
            record_data=record_data,
            single_stake_text=(
                position.get(
                    "single_stake_text"
                )
            ),
            single_stake_value=(
                position.get(
                    "single_stake_value"
                )
            ),
            inspection_results=(
                inspection_results
            ),
            survey_date=survey_date,
            overall_grade=overall_grade,
            survey_comment=(
                survey_comment
            ),
            source_management_scope_uid=(
                source_management_scope_uid
            ),
        )

    if (
        definition.position.kind
        == "range"
    ):
        return create_range_engineering_survey(
            project_id=project_id,
            survey_batch_id=(
                survey_batch_id
            ),
            form_version_id=(
                form_version_id
            ),
            asset_name=asset_name,
            asset_type=(
                definition.asset_type
            ),
            organization_unit_id=(
                organization_unit_id
            ),
            canal_unit_id=(
                canal_unit_id
            ),
            business_code=(
                business_code
            ),
            record_data=record_data,
            start_stake_text=(
                position.get(
                    "start_stake_text"
                )
            ),
            start_stake_value=(
                position.get(
                    "start_stake_value"
                )
            ),
            end_stake_text=(
                position.get(
                    "end_stake_text"
                )
            ),
            end_stake_value=(
                position.get(
                    "end_stake_value"
                )
            ),
            inspection_results=(
                inspection_results
            ),
            survey_date=survey_date,
            overall_grade=overall_grade,
            survey_comment=(
                survey_comment
            ),
            source_management_scope_uid=(
                source_management_scope_uid
            ),
        )

    raise ValueError(
        "暂不支持的工程位置类型："
        f"{definition.position.kind}"
    )


def update_engineering_record(
    definition: EngineeringFormDefinition,
    *,
    survey_record_id: int,
    payload: dict,
):
    """
    更新已有工程调查记录。

    已存在的 EngineeringAsset：
    - 归属不在这里修改；
    - 业务编号不在这里修改；
    - point / range 根据 definition 自动路由。
    """

    asset_name = payload.get("asset_name")
    record_data = payload.get("record_data") or {}
    position = payload.get("position") or {}

    inspection_results = payload.get("inspection_results") or []

    survey_date = payload.get("survey_date")
    overall_grade = payload.get("overall_grade")
    survey_comment = payload.get("survey_comment")

    if definition.position.kind == "point":
        return update_point_engineering_survey(
            survey_record_id=survey_record_id,
            form_code=definition.form_code,
            asset_name=asset_name,
            record_data=record_data,
            single_stake_text=position.get("single_stake_text"),
            single_stake_value=position.get("single_stake_value"),
            inspection_results=inspection_results,
            survey_date=survey_date,
            overall_grade=overall_grade,
            survey_comment=survey_comment,
        )

    if definition.position.kind == "range":
        return update_range_engineering_survey(
            survey_record_id=survey_record_id,
            form_code=definition.form_code,
            asset_name=asset_name,
            record_data=record_data,
            start_stake_text=position.get("start_stake_text"),
            start_stake_value=position.get("start_stake_value"),
            end_stake_text=position.get("end_stake_text"),
            end_stake_value=position.get("end_stake_value"),
            inspection_results=inspection_results,
            survey_date=survey_date,
            overall_grade=overall_grade,
            survey_comment=survey_comment,
        )

    raise ValueError("暂不支持的工程位置类型：" f"{definition.position.kind}")


def get_engineering_record(
    definition: EngineeringFormDefinition,
    *,
    survey_record_id: int,
):
    """
    根据表单位置类型读取一条工程调查记录。
    """

    if definition.position.kind == "point":
        return get_point_engineering_record(
            survey_record_id=survey_record_id,
            form_code=definition.form_code,
        )

    if definition.position.kind == "range":
        return get_range_engineering_record(
            survey_record_id=survey_record_id,
            form_code=definition.form_code,
        )

    raise ValueError("暂不支持的工程位置类型：" f"{definition.position.kind}")


def load_engineering_record_bundle(
    definition: EngineeringFormDefinition,
    *,
    survey_record_id: int,
):
    """
    一次取得页面恢复所需要的数据。

    返回：
    {
        "record": ...,
        "inspection_results": ...
    }
    """

    record = get_engineering_record(
        definition,
        survey_record_id=survey_record_id,
    )

    if record is None:
        return None

    inspection_results = get_inspection_results(survey_record_id)

    return {
        "record": record,
        "inspection_results": inspection_results,
    }


def complete_engineering_record(
    definition: EngineeringFormDefinition,
    *,
    survey_record_id: int,
    payload: dict,
) -> dict:
    """
    保存当前最新页面内容，
    再将工程调查正式推进为 completed。

    流程：
    1. 确认记录存在且仍为 draft；
    2. 使用 definition 做表单级完整性校验；
    3. 将最新 payload 保存到数据库；
    4. 调用数据库公共完成事务；
    5. 返回完成结果。

    completed记录不会再次进入此流程。
    """

    current_record = get_engineering_record(
        definition,
        survey_record_id=(survey_record_id),
    )

    if current_record is None:
        raise ValueError("没有找到该调查记录。")

    if current_record["record_status"] != "draft":
        raise ValueError("只有草稿记录可以" "执行完成调查。")

    errors = validate_completion(
        definition,
        payload,
    )

    if errors:
        error_text = "\n".join(f"• {error}" for error in errors)

        raise ValueError("完成调查前请修正" "以下内容：\n\n" f"{error_text}")

    # =========================================================
    # 先保存最新页面状态
    # =========================================================

    update_engineering_record(
        definition,
        survey_record_id=(survey_record_id),
        payload=payload,
    )

    # =========================================================
    # 再由数据库执行正式状态转换
    # =========================================================

    expected_item_codes = tuple(
        item["item_code"] for item in definition.evaluation_items
    )

    return complete_engineering_survey_record(
        survey_record_id=(survey_record_id),
        form_code=(definition.form_code),
        position_kind=(definition.position.kind),
        expected_item_codes=(expected_item_codes),
        grade_options=(definition.grade_options),
    )
