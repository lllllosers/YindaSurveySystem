from PySide6.QtCore import (
    Qt,
)

from forms.engineering.models import (
    EngineeringFormDefinition,
)

from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)

from services.engineering_original_form_export import (
    export_engineering_original_form,
)


class GenericEngineeringListPage(
    EngineeringSurveyListPage,
):
    """
    基于 EngineeringFormDefinition
    驱动的附表2当前批次通用列表页。

    EngineeringSurveyListPage 负责公共列表交互；
    本类只把声明式 ListDefinition /
    OriginalFormExportDefinition
    适配为运行时配置。
    """

    def __init__(
        self,
        definition: EngineeringFormDefinition,
    ):
        list_definition = (
            definition.list_definition
        )

        if list_definition is None:
            raise ValueError(
                f"{definition.form_code} "
                "尚未配置 ListDefinition。"
            )

        original_form_definition = (
            definition
            .original_form_export_definition
        )

        if (
            original_form_definition
            is None
        ):
            raise ValueError(
                f"{definition.form_code} "
                "尚未配置 "
                "OriginalFormExportDefinition。"
            )

        self.definition = definition
        self.list_definition = (
            list_definition
        )
        self.original_form_definition = (
            original_form_definition
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

        self.EXPORT_FILENAME_PREFIX = (
            original_form_definition
            .output_filename_prefix
        )

        self.EXPORT_FALLBACK_ASSET_NAME = (
            original_form_definition
            .fallback_asset_name
        )

        super().__init__()

    # =========================================================
    # 配置合同
    # =========================================================

    def _validate_configuration(
        self,
    ):
        if (
            self.definition.list_definition
            is None
        ):
            raise ValueError(
                f"{self.definition.form_code} "
                "尚未配置 ListDefinition。"
            )

        if (
            self.definition
            .original_form_export_definition
            is None
        ):
            raise ValueError(
                f"{self.definition.form_code} "
                "尚未配置 "
                "OriginalFormExportDefinition。"
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
        if (
            binding.source
            == "query_record"
        ):
            values = [
                record[key]
                for key in binding.keys
            ]

        elif (
            binding.source
            == "record_data"
        ):
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
        return export_engineering_original_form(
            self.definition,
            survey_record_id=(
                survey_record_id
            ),
            file_path=file_path,
        )
