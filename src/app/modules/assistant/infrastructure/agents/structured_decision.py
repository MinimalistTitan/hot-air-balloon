from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

_TOOL_PAYLOAD_ADAPTER = TypeAdapter(dict[str, object])
MIN_TOOL_DECISION_CONFIDENCE = 0.8


class AgentDecision(BaseModel):
    """Invariant-checked decision returned by the planning model."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["respond", "tool_call"]
    intent: str = Field(
        min_length=2,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Concise snake_case interpretation of the user's requested outcome.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that the action and selected tool match the request.",
    )
    rationale: str = Field(
        min_length=1,
        max_length=500,
        description="Brief internal reason grounded in the request and tool contract.",
    )
    final_answer: str | None = Field(
        description="Non-empty answer for action=respond; null for action=tool_call.",
    )
    tool_name: str | None = Field(
        description="Exact callable tool name for action=tool_call; null when responding.",
    )
    tool_payload_json: str | None = Field(
        description="JSON object string for action=tool_call; null when responding.",
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if self.action == "respond":
            if self.final_answer is None or not self.final_answer.strip():
                raise ValueError("respond decisions require a non-empty final_answer")
            if self.tool_name is not None or self.tool_payload_json is not None:
                raise ValueError("respond decisions cannot include tool fields")
            return self

        if self.final_answer is not None:
            raise ValueError("tool_call decisions require final_answer=null")
        if self.tool_name is None or not self.tool_name.strip():
            raise ValueError("tool_call decisions require a non-empty tool_name")
        if self.tool_payload_json is None:
            raise ValueError("tool_call decisions require tool_payload_json")
        self.parse_tool_payload()
        return self

    def parse_tool_payload(self) -> dict[str, object]:
        if self.tool_payload_json is None:
            return {}
        return _TOOL_PAYLOAD_ADAPTER.validate_json(self.tool_payload_json)

    def response_text(self) -> str:
        if self.action != "respond" or self.final_answer is None:
            raise ValueError("decision is not a direct response")
        return self.final_answer

    def tool_call(self) -> tuple[str, dict[str, object]]:
        if self.action != "tool_call" or self.tool_name is None:
            raise ValueError("decision is not a tool call")
        return self.tool_name, self.parse_tool_payload()


class AgentFinalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_answer: str = Field(
        min_length=1,
        description=(
            "Concise answer to the user's requested outcome, grounded only in supplied tool "
            "results and conversation context."
        ),
    )
