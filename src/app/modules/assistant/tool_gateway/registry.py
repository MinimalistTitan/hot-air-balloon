from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.modules.assistant.tool_gateway.domain import AssistantToolRegistration


# class ToolRegistry:
#     def __init__(self) -> None:
#         self._tools: dict[str, ToolDefinition] = {}
#         self._registrations: dict[str, AssistantToolRegistration] = {}

#     def register(self, tool: ToolDefinition) -> None:
#         if tool.name in self._tools:
#             raise ValueError(f"tool already registered: {tool.name}")
#         self._tools[tool.name] = tool

#     def get(self, tool_name: str) -> ToolDefinition | None:
#         return self._tools.get(tool_name)

#     def list_names(self) -> list[str]:
#         return sorted(self._tools.keys())

#     def list_tools(self) -> list[ToolDefinition]:
#         return [self._tools[name] for name in self.list_names()]

#     def list_registrations(self) -> list[AssistantToolRegistration]:
#         return [
#             self._registrations[name]
#             for name in sorted(self._registrations)
#         ]


class ToolRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, AssistantToolRegistration] = {}

    def register(self, registration: AssistantToolRegistration) -> None:
        name = registration.definition.name
        if name in self._registrations:
            raise ValueError(f"tool already registered: {name}")
        self._registrations[name] = registration

    def get(self, tool_name: str) -> AssistantToolRegistration | None:
        return self._registrations.get(tool_name)

    def list_registrations(self) -> list[AssistantToolRegistration]:
        return [
            self._registrations[name]
            for name in sorted(self._registrations)
        ]

def validate_strict_input(model: type[BaseModel], payload: dict[str, Any]) -> BaseModel:
    config = getattr(model, "model_config", {})
    if config.get("extra") != "forbid":
        raise TypeError(
            f"{model.__name__} must set model_config = ConfigDict(extra='forbid') "
            "so unknown args are rejected before handler execution"
        )

    return model.model_validate(payload)
