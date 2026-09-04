from dataclasses import dataclass

from app.modules.assistant.application.reference_resolution.contracts import (
    FieldQueryResult,
    FieldQueryStatus,
    FieldValue,
    ResolvedReference,
)


@dataclass(frozen=True, slots=True)
class FieldQueryExecutor:
    def execute(self, reference: ResolvedReference) -> FieldQueryResult:
        values = tuple(
            FieldValue(
                entity_id=item.entity_id,
                label=item.label,
                field_name=reference.request.field_name,
                value=next(
                    (
                        field.value
                        for field in item.fields
                        if field.name == reference.request.field_name
                    ),
                    None,
                ),
            )
            for item in reference.items
        )
        present = sum(value.value is not None for value in values)
        status = (
            FieldQueryStatus.COMPLETE
            if present == len(values)
            else FieldQueryStatus.PARTIAL
            if present
            else FieldQueryStatus.EMPTY
        )
        return FieldQueryResult(
            entity_label=reference.entity_label,
            field_name=reference.request.field_name,
            values=values,
            status=status,
        )
