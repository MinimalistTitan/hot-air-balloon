from app.modules.assistant.domain.entities import ToolCallRecord
from app.modules.assistant.infrastructure.agents.langgraph.final_response import (
    render_grounded_tool_answer,
)


def test_work_order_results_are_rendered_without_llm_synthesis() -> None:
    answer = render_grounded_tool_answer(
        [
            ToolCallRecord(
                tool_name="get_work_orders",
                payload={"site_code": "PLANT-HCM", "status": "open", "limit": 3},
                result={
                    "status": "success",
                    "applied_payload": {
                        "site_code": "PLANT-HCM",
                        "status": "open",
                        "limit": 3,
                    },
                    "result": {
                        "tool_name": "get_work_orders",
                        "work_orders": [
                            {
                                "code": "WO-HCM-0101",
                                "title": "Inspect stamping press hydraulic circuit",
                            },
                            {
                                "code": "WO-HCM-0001",
                                "title": "Replace CNC spindle bearing",
                            },
                        ],
                    },
                },
            )
        ]
    )

    assert answer == (
        "I found 2 open work orders at PLANT-HCM (fewer than the 3 requested):\n\n"
        "1. WO-HCM-0101 - Inspect stamping press hydraulic circuit\n"
        "2. WO-HCM-0001 - Replace CNC spindle bearing"
    )


def test_empty_work_order_result_is_rendered_as_no_matches() -> None:
    answer = render_grounded_tool_answer(
        [
            ToolCallRecord(
                tool_name="get_work_orders",
                payload={"site_code": "PLANT-HCM", "status": "open", "limit": 3},
                result={
                    "status": "success",
                    "applied_payload": {
                        "site_code": "PLANT-HCM",
                        "status": "open",
                        "limit": 3,
                    },
                    "result": {
                        "tool_name": "get_work_orders",
                        "work_orders": [],
                    },
                },
            )
        ]
    )

    assert answer == "No open work orders at PLANT-HCM were found."


def test_unhandled_tool_result_uses_normal_synthesis_path() -> None:
    answer = render_grounded_tool_answer(
        [
            ToolCallRecord(
                tool_name="get_asset_status",
                payload={"site_code": "PLANT-HCM"},
                result={"status": "success"},
            )
        ]
    )

    assert answer is None
