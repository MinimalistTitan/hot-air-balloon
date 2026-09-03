import pytest
from pydantic import ValidationError

from app.modules.assistant.infrastructure.agents.langgraph.agent_brain import (
    planned_action_from_decision,
)
from app.modules.assistant.infrastructure.agents.structured_decision import AgentDecision


def test_structured_respond_decision_has_mutually_exclusive_fields() -> None:
    decision = AgentDecision.model_validate(
        {
            "action": "respond",
            "intent": "explain_work_order",
            "confidence": 0.97,
            "rationale": "The request asks for a definition, not ERP data.",
            "final_answer": "A maintenance work order records planned maintenance work.",
            "tool_name": None,
            "tool_payload_json": None,
        }
    )

    assert decision.response_text().startswith("A maintenance")
    assert planned_action_from_decision(decision) == {
        "action": "respond",
        "tool_name": "",
        "payload": {},
        "answer": "A maintenance work order records planned maintenance work.",
        "intent": "explain_work_order",
        "confidence": 0.97,
        "rationale": "The request asks for a definition, not ERP data.",
    }


def test_structured_tool_decision_parses_object_payload() -> None:
    decision = AgentDecision.model_validate(
        {
            "action": "tool_call",
            "intent": "list_open_work_orders",
            "confidence": 0.95,
            "rationale": "The work-order listing tool supports site and status filters.",
            "final_answer": None,
            "tool_name": "get_work_orders",
            "tool_payload_json": '{"site_code":"PLANT-HCM","status":"open"}',
        }
    )

    assert decision.tool_call() == (
        "get_work_orders",
        {"site_code": "PLANT-HCM", "status": "open"},
    )
    assert planned_action_from_decision(decision)["action"] == "tool_call"


@pytest.mark.parametrize(
    "overrides",
    [
        {"tool_name": "get_work_orders"},
        {"tool_payload_json": "{}"},
        {"final_answer": "", "tool_name": None, "tool_payload_json": None},
        {"confidence": 1.1},
        {"intent": "List Work Orders"},
    ],
)
def test_structured_respond_decision_rejects_invalid_combinations(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "action": "respond",
        "intent": "explain_work_order",
        "confidence": 0.9,
        "rationale": "No tool is required.",
        "final_answer": "Explanation",
        "tool_name": None,
        "tool_payload_json": None,
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        AgentDecision.model_validate(values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_answer": "I already answered."},
        {"tool_name": None},
        {"tool_payload_json": None},
        {"tool_payload_json": "[]"},
        {"tool_payload_json": "not-json"},
    ],
)
def test_structured_tool_decision_rejects_invalid_combinations(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "action": "tool_call",
        "intent": "list_work_orders",
        "confidence": 0.9,
        "rationale": "The request matches the tool contract.",
        "final_answer": None,
        "tool_name": "get_work_orders",
        "tool_payload_json": "{}",
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        AgentDecision.model_validate(values)


def test_low_confidence_tool_decision_is_downgraded_to_response() -> None:
    decision = AgentDecision.model_validate(
        {
            "action": "tool_call",
            "intent": "uncertain_operation",
            "confidence": 0.79,
            "rationale": "The request does not clearly select one tool contract.",
            "final_answer": None,
            "tool_name": "get_work_orders",
            "tool_payload_json": "{}",
        }
    )

    action = planned_action_from_decision(decision)

    assert action["action"] == "respond"
    assert action["confidence"] == 0.79
