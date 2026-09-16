from typing import (
    Callable,
)

from PySide6.QtCore import (
    Qt,
)

from forms.engineering.models import (
    EngineeringFormDefinition,
)

from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)


OriginalFormExporter = Callable[..., dict]


class GenericEngineeringListPage(
    EngineeringSurveyListPage,
):
    """
    基于 EngineeringFormDefinition.list_definition
    驱动的附表2当前批次通用列表页。

    EngineeringSurveyListPage 继续负责：
    - 当前批次加载；
    - 筛选；
    - 统计；
    - 删除；
    - 双击打开；
    - 正式原表导出的交互流程。

    本类负责把声明式 ListDefinition
    转换为基类需要的页面配置和行数据。
    """

    DEFINITION: (
        EngineeringFormDefinition | None
    ) = None

    # R1-13D 正式原表引擎迁移前，
    # 暂由极薄表级 wrapper 提供现有 exporter。
    ORIGINAL_EXPORTER: (
        OriginalFormExporter | None
    ) = None

    def __init__(
        self,
    ):
        definition = self.DEFINITION

        if definition is None:
            raise ValueError(
                "GenericEngineeringListPage "
                "必须配置 DEFINITION。"
            )

        list_definition = (
            definition.list_definition
        )

        if list_definition is None:
            raise ValueError(
                f"{definition.form_code} "
                "尚未配置 ListDefinition。"
            )

        self.definition = definition
        self.list_definition = (
            list_definition
        )

        # =====================================================
        # 将声明式配置适配给现有公共列表基类
        # =====================================================

        self.FORM_CODE = (
            definition.form_code
        )

        self.PAGE_TITLE = (
            f"{definition.display_name.removesuffix('表')}"
            "记录"
        )

        self.NEW_BUTTON_TEXT = (
            list_definition.new_button_text
        )

        self.KEYWORD_PLACEHOLDER = (
            list_definition.keyword_placeholder
        )

        self.POSITION_LABEL = (
            list_definition.position_label
        )

        self.TABLE_HEADERS = tuple(
            column.header
            for column
            in list_definition.columns
        )

        self.TABLE_WIDTHS = tuple(
            column.width
            for column
            in list_definition.columns
        )

        self.GRADE_OPTIONS = (
            definition.grade_options
        )

        self.SHOW_GRADE_STATISTICS = (
            list_definition
            .show_grade_statistics
        )

        super().__init__()

    # =========================================================
    # 配置合同
    # =========================================================

    def _validate_configuration(
        self,
    ):
        if self.DEFINITION is None:
            raise ValueError(
                "GenericEngineeringListPage "
                "必须配置 DEFINITION。"
            )

        if (
            self.DEFINITION.list_definition
            is None
        ):
            raise ValueError(
                f"{self.DEFINITION.form_code} "
                "尚未配置 ListDefinition。"
            )

        if self.ORIGINAL_EXPORTER is None:
            raise ValueError(
                f"{self.DEFINITION.form_code} "
                "尚未配置正式原表 exporter。"
            )

        super()._validate_configuration()

    # =========================================================
    # 声明式值绑定
    # =========================================================

    def _resolve_binding(
        self,
        record,
        binding,
    ):
        if binding.source == "query_record":
            values = [
                record[key]
                for key in binding.keys
            ]

        elif binding.source == "record_data":
            record_data = (
                record["record_data"]
                or {}
            )

            values = [
                record_data.get(key)
                for key in binding.keys
            ]

        else:
            raise ValueError(
                "工程调查列表不支持的数据源："
                f"{binding.source}"
            )

        if binding.formatter is not None:
            return binding.formatter(
                *values
            )

        return values[0]

    # =========================================================
    # 关键词
    # =========================================================

    def _keyword_values(
        self,
        record,
    ):
        return [
            self._resolve_binding(
                record,
                binding,
            )
            for binding
            in self.list_definition
            .keyword_bindings
        ]

    # =========================================================
    # 表格行
    # =========================================================

    def _build_table_values(
        self,
        record,
    ):
        return [
            self._resolve_binding(
                record,
                column.binding,
            )
            for column
            in self.list_definition.columns
        ]

    def _render_records(
        self,
        records,
    ):
        # 记录 ID 存储和基础单元格创建继续复用公共基类。
        super()._render_records(
            records
        )

        alignment_map = {
            "left": (
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            ),
            "center": (
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignVCenter
            ),
            "right": (
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
        }

        for row_index in range(
            self.table.rowCount()
        ):
            for (
                column_index,
                column_definition,
            ) in enumerate(
                self.list_definition.columns
            ):
                item = self.table.item(
                    row_index,
                    column_index,
                )

                if item is None:
                    continue

                item.setTextAlignment(
                    alignment_map[
                        column_definition.alignment
                    ]
                )

    # =========================================================
    # 正式原表
    # =========================================================

    def _export_original_form(
        self,
        survey_record_id,
        file_path,
    ):
        exporter = self.ORIGINAL_EXPORTER

        if exporter is None:
            raise ValueError(
                "当前调查表尚未配置"
                "正式原表 exporter。"
            )

        return exporter(
            survey_record_id=(
                survey_record_id
            ),
            file_path=file_path,
        )
