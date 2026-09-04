from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.modules.assistant.application.commands import AssistantQueryCommand
from app.modules.assistant.application.context.providers import ContextRequest
from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    AssistantTelemetryPort,
    ContextAssemblerPort,
    ConversationStorePort,
    ConversationTurn,
    EraseUserMemoryResult,
    ToolInvoker,
    ToolRuntimePort,
    UserMemoryErasePort,
)
from app.modules.assistant.application.reference_resolution.field_query import FieldQueryExecutor
from app.modules.assistant.application.reference_resolution.formatting import (
    FieldValueFormatterRegistry,
)
from app.modules.assistant.application.reference_resolution.resolver import (
    ReferenceResolver,
)
from app.modules.assistant.contracts.messages import (
    AssistantQueryResponseV1,
    AssistantToolCallTraceV1,
)
from app.modules.assistant.domain.conversation_evidence import ConversationEvidenceSnapshot
from app.modules.assistant.domain.entities import ToolCallRecord
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
    context_assembler: ContextAssemblerPort
    evidence_retention_days: int = 90
    reference_resolver: ReferenceResolver | None = None
    field_query_executor: FieldQueryExecutor | None = None
    field_value_formatters: FieldValueFormatterRegistry | None = None

    async def execute(self, command: AssistantQueryCommand) -> AssistantQueryResponseV1:
        self.telemetry.query_started(command.query)
        conversation_id = command.conversation_id or uuid4()
        owner_user_id = command.authorization_context.user_id
        user_turn_created_at = datetime.now(UTC)
        await self.conversation_store.claim_or_validate(
            conversation_id=conversation_id,
            owner_user_id=owner_user_id,
            observed_at_utc=user_turn_created_at,
        )

        history = await self.conversation_store.read_recent(
            conversation_id,
            owner_user_id=owner_user_id,
            limit=12,
        )

        recent_evidence = await self.conversation_store.read_recent_evidence(
            conversation_id,
            owner_user_id=owner_user_id,
            limit=12,
        )

        resolution = (
            self.reference_resolver.resolve(command.query, recent_evidence)
            if self.reference_resolver is not None
            else None
        )

        if (
            resolution is not None
            and resolution.reference is not None
            and self.field_query_executor is not None
            and self.field_value_formatters is not None
        ):
            field_result = self.field_query_executor.execute(resolution.reference)
            answer = self.field_value_formatters.format(field_result)

            await self.conversation_store.append_completed_exchange(
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
                user_turn=ConversationTurn(
                    role="user",
                    content=command.query,
                    created_at_utc=user_turn_created_at,
                ),
                assistant_turn=ConversationTurn(
                    role="assistant",
                    content=answer,
                    created_at_utc=datetime.now(UTC),
                ),
            )
            self.telemetry.query_completed(0)
            return AssistantQueryResponseV1(
                answer=answer,
                conversation_id=conversation_id,
                agent_name="assistant.reference-resolver",
                model_name="deterministic",
                finish_reason="completed",
                tool_calls=[],
            )
        context = await self.context_assembler.assemble(
            ContextRequest(
                conversation_id=conversation_id,
                user_query=command.query,
                authorization_context=command.authorization_context,
                recent_turns=history,
                recent_evidence=recent_evidence,
            )
        )

        try:
            tools = await self.tool_runtime.list_tools(command.authorization_context)

            run = await self.agent_orchestrator.run(
                conversation_id=conversation_id,
                authorization_context=command.authorization_context,
                user_query=command.query,
                available_tools=tools,
                tool_invoker=self._tool_invoker(command.authorization_context, conversation_id),
                context=context,
                tool_policy=self.tool_policy,
                max_tool_calls=command.max_tool_calls,
                allow_tool_calls=command.allow_tool_calls,
            )
        except Exception as ex:
            raise AssistantOrchestrationFailedError(str(ex)) from ex

        await self.conversation_store.append_completed_exchange(
            conversation_id=conversation_id,
            owner_user_id=owner_user_id,
            user_turn=ConversationTurn(
                role="user",
                content=command.query,
                created_at_utc=user_turn_created_at,
            ),
            assistant_turn=ConversationTurn(
                role="assistant",
                content=run.answer,
                created_at_utc=datetime.now(UTC),
            ),
            evidence=(
                ConversationEvidenceSnapshot(
                    conversation_id=conversation_id,
                    owner_user_id=owner_user_id,
                    exchange_id=uuid4(),
                    tool_name="assistant.run",
                    evidence=run.evidence,
                    created_at_utc=user_turn_created_at,
                    expires_at_utc=user_turn_created_at
                    + timedelta(days=self.evidence_retention_days),
                )
                if run.evidence
                else None
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

    def _tool_invoker(
        self,
        authorization_context: AuthorizationContext,
        conversation_id: UUID,
    ) -> ToolInvoker:
        async def invoke(tool_name: str, payload: dict[str, object]) -> ToolCallRecord:
            return await self.tool_runtime.invoke(
                tool_name,
                payload,
                authorization_context,
                conversation_id,
            )

        return invoke


@dataclass(slots=True)
class EraseUserMemory:
    eraser: UserMemoryErasePort

    async def execute(self, owner_user_id: UUID) -> EraseUserMemoryResult:
        return await self.eraser.erase_user_memory(owner_user_id)
