from dataclasses import dataclass

from app.modules.assistant.tool_gateway.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class RederivableFieldSet:
    terms: frozenset[str]


def collect_rederivable_fields(registry: ToolRegistry) -> RederivableFieldSet:
    fields = {
        field_name.replace("_", " ").lower()
        for tool in registry.list_registrations()
        for field_name in tool.definition.output_model.model_fields
    }
    return RederivableFieldSet(terms=frozenset(fields))
