from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.assistant.application.reference_resolution.formatting import (
    FieldValueFormatter,
    FieldValueFormatterRegistry,
    TemplateFieldValueFormatter,
)
from app.modules.assistant.application.reference_resolution.parser import (
    RegexReferenceQueryParser,
)
from app.modules.assistant.application.reference_resolution.resolver import (
    MappingValueRanker,
    ReferenceResolver,
    ReferenceValueRanker,
)


@dataclass(frozen=True, slots=True)
class ReferenceFieldPolicy:
    field_name: str
    query_patterns: tuple[str, ...]
    formatter: FieldValueFormatter = field(default_factory=TemplateFieldValueFormatter)
    ranker: ReferenceValueRanker | None = None


@dataclass(frozen=True, slots=True)
class ReferenceResolutionPolicy:
    fields: tuple[ReferenceFieldPolicy, ...]
    maximum_patterns: tuple[str, ...] = ()
    minimum_patterns: tuple[str, ...] = ()

    def build_resolver(self) -> ReferenceResolver:
        return ReferenceResolver(
            parser=RegexReferenceQueryParser(
                field_patterns=tuple(
                    (pattern, field.field_name)
                    for field in self.fields
                    for pattern in field.query_patterns
                ),
                maximum_patterns=self.maximum_patterns,
                minimum_patterns=self.minimum_patterns,
            ),
            rankers={
                field.field_name: field.ranker
                for field in self.fields
                if field.ranker is not None
            },
        )

    def build_formatter_registry(self) -> FieldValueFormatterRegistry:
        return FieldValueFormatterRegistry(
            formatters={field.field_name: field.formatter for field in self.fields}
        )


def build_default_reference_resolution_policy() -> ReferenceResolutionPolicy:
    return ReferenceResolutionPolicy(
        fields=(
            ReferenceFieldPolicy(
                field_name="due_at",
                query_patterns=(r"\b(?:due|deadline|date)\b",),
                formatter=TemplateFieldValueFormatter("{entity_id} is due on {value}."),
            ),
            ReferenceFieldPolicy(
                field_name="priority",
                query_patterns=(r"\bpriority\b",),
                ranker=MappingValueRanker(
                    {"low": 1, "medium": 2, "high": 3, "critical": 4}
                ),
            ),
        ),
        maximum_patterns=(
            r"\bhighest\b",
            r"\bmost\s+urgent\b",
            r"\bmost\s+critical\b",
        ),
        minimum_patterns=(
            r"\blowest\b",
            r"\bleast\s+urgent\b",
            r"\bleast\s+critical\b",
        ),
    )
