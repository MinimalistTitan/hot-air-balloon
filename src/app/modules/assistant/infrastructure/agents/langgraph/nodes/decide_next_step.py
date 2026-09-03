from typing import Literal

from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.runtime import Runtime
from langgraph.types import Command


async def decide_next_step(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> Command[Literal["plan_action", "respond"]]:
    del state
    destination: Literal["plan_action", "respond"] = (
        "plan_action" if runtime.context.call_budget.remaining_calls > 0 else "respond"
    )
    return Command(goto=destination)
