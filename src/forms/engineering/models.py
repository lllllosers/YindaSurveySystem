"""Desktop presentation extensions of the shared official form contract."""
from dataclasses import dataclass
from shared.forms.engineering.models import (
    EngineeringFormDefinition as CoreEngineeringFormDefinition,
    FieldDefinition, FieldRowDefinition, FormSectionDefinition, PositionDefinition,
    FieldType, PositionType,
)
from forms.engineering.extension_models import ListDefinition, SummaryExportDefinition

@dataclass(frozen=True)
class EngineeringFormDefinition(CoreEngineeringFormDefinition):
    list_definition: ListDefinition | None = None
    summary_export_definition: SummaryExportDefinition | None = None

    def __post_init__(self):
        super().__post_init__()
        bindings = []
        if self.list_definition is not None:
            bindings.extend(column.binding for column in self.list_definition.columns)
            bindings.extend(self.list_definition.keyword_bindings)
        if self.summary_export_definition is not None:
            bindings.extend(column.binding for column in self.summary_export_definition.columns)
        for binding in bindings:
            if binding.source == "record_data":
                for key in binding.keys:
                    if key not in self.field_map:
                        raise ValueError("扩展定义引用了不存在的 record_data 字段：" + key)
