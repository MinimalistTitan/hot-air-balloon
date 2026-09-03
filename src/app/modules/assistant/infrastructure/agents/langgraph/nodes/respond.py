from langchain_core.messages import AIMessage, HumanMessage

from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.runtime import Runtime


async def respond(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> dict[str, object]:
    # A terminal answer already set upstream (e.g. a policy block) is
    # authoritative; keep it instead of generating a new one.
    if state["finish_reason"] is not None and state["answer"]:
        return {}

    if state["tool_calls"]:
        evidence = tuple(block for call in state["tool_calls"] for block in call.evidence)
        answer = runtime.context.response_composer.compose(
            runtime.context.user_query,
            evidence,
        ).answer
    else:
        answer = await runtime.context.brain.respond(runtime.context.agent_state(state))

    normalized_answer = answer.strip() or "No answer generated."
    update: dict[str, object] = {
        "answer": normalized_answer,
        "messages": [
            HumanMessage(content=runtime.context.user_query),
            AIMessage(content=normalized_answer),
        ],
    }

    # Preserve an existing terminal reason instead of masking it as completed.
    if state["finish_reason"] is None:
        update["finish_reason"] = OrchestrationFinishReason.COMPLETED
    return update
