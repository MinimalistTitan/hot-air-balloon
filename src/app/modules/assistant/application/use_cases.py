from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.assistant.application.commands import AssistantQueryCommand
from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    AssistantTelemetryPort,
    ConversationStorePort,
    ConversationTurn,
    ToolInvoker,
    ToolRuntimePort,
)
from app.modules.assistant.contracts.messages import (
    AssistantQueryResponseV1,
    AssistantToolCallTraceV1,
)
from app.modules.assistant.domain.errors import AssistantOrchestrationFailedError
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.user.domain.authorization import AuthorizationContext


@dataclass(slots=True)
class OrchestrateAssistantQuery:
    tool_runtime: ToolRuntimePort
    agent_orchestrator: AgentOrchestratorPort
    conversation_store: ConversationStorePort
    telemetry: AssistantTelemetryPort
    tool_policy: ToolCallPolicy

    async def execute(self, command: AssistantQueryCommand) -> AssistantQueryResponseV1:
        self.telemetry.query_started(command.query)
        conversation_id = command.conversation_id or uuid4()
        history = await self.conversation_store.read_recent(conversation_id, limit=12)

        try:
            tools = await self.tool_runtime.list_tools()
            
            run = await self.agent_orchestrator.run(
                conversation_id=conversation_id,
                user_query=command.query,
                available_tools=tools,
                tool_invoker=self._tool_invoker(command.authorization_context),
                conversation_history=history,
                tool_policy=self.tool_policy,
                max_tool_calls=command.max_tool_calls,
                allow_tool_calls=command.allow_tool_calls,
            )
        except Exception as ex:
            raise AssistantOrchestrationFailedError(str(ex)) from ex
        
        await self.conversation_store.append(
            conversation_id,
            ConversationTurn(
                role="user",
                content=command.query,
                created_at_utc=datetime.now(UTC),
            ),
        )
        
        await self.conversation_store.append(
            conversation_id,
            ConversationTurn(
                role="assistant",
                content=run.answer,
                created_at_utc=datetime.now(UTC),
            ),
        )

        for item in run.tool_calls:
            self.telemetry.tool_called(item.tool_name)

        self.telemetry.query_completed(len(run.tool_calls))

        return AssistantQueryResponseV1(
            answer=run.answer,
            conversation_id=conversation_id,
            agent_name=run.agent_name,
            model_name=run.model_name,
            finish_reason=run.finish_reason.value,
            tool_calls=[
                AssistantToolCallTraceV1(
                    tool_name=item.tool_name,
                    payload=item.payload,
                    result=item.result,
                )
                for item in run.tool_calls
            ],
        )

    def _tool_invoker(self, authorization_context: AuthorizationContext) -> ToolInvoker:
        async def invoke(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
            return await self.tool_runtime.invoke(
                tool_name,
                payload,
                authorization_context,
            )

        return invoke