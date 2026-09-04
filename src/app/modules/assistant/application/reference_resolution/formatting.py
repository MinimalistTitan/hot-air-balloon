from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from app.modules.assistant.application.reference_resolution.contracts import FieldQueryResult


class FieldValueFormatter(Protocol):
    def format(self, result: FieldQueryResult) -> str: ...


@dataclass(frozen=True, slots=True)
class TemplateFieldValueFormatter:
    template: str = "{entity_id}: {value}"

    def format(self, result: FieldQueryResult) -> str:
        lines = [
            self.template.format(entity_id=value.entity_id, label=value.label, value=value.value)
            for value in result.values
            if value.value is not None
        ]
        if lines:
            return "\n".join(lines)
        return f"The referenced {result.entity_label} items do not contain {result.field_name}."


@dataclass(frozen=True, slots=True)
class FieldValueFormatterRegistry:
    formatters: Mapping[str, FieldValueFormatter]
    default_formatter: FieldValueFormatter = field(default_factory=TemplateFieldValueFormatter)

    def format(self, result: FieldQueryResult) -> str:
        return self.formatters.get(result.field_name, self.default_formatter).format(result)
