from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.modules.assistant.application.context.assembler import DefaultContextAssembler
from app.modules.assistant.application.context.budget import TokenBudgetAllocator
from app.modules.assistant.application.context.providers import ContextProviderPort, ContextRequest
from app.modules.assistant.application.context.recent_turns_provider import RecentTurnsProvider
from app.modules.assistant.application.ports import ConversationTurn
from app.modules.assistant.domain.context import AssembledContext, ContextBlock, ContextKind
from app.modules.assistant.infrastructure.context.tiktoken_counter import TiktokenCounter
from app.modules.user.domain.authorization import AuthorizationContext, RoleName


class FailingProvider(ContextProviderPort):
    async def get_blocks(self, request: ContextRequest) -> list[ContextBlock]:
        raise RuntimeError("boom")


class EchoProvider(ContextProviderPort):
    async def get_blocks(self, request: ContextRequest) -> list[ContextBlock]:
        return [
            ContextBlock(
                kind=ContextKind.SYSTEM_DIRECTIVE,
                content="You are a helpful assistant.",
                source="system",
            ),
            ContextBlock(
                kind=ContextKind.TOOL_RESULT,
                content="final status: ok",
                source="tool",
            ),
        ]


def test_token_budget_allocator_keeps_total_tokens_under_budget() -> None:
    allocator = TokenBudgetAllocator()
    blocks = [
        ContextBlock(kind=ContextKind.RECENT_TURN, content="a " * 200, source="history"),
        ContextBlock(kind=ContextKind.USER_MEMORY, content="b " * 200, source="memory"),
        ContextBlock(kind=ContextKind.TOOL_RESULT, content="c " * 200, source="tool"),
    ]

    allocated, dropped = allocator.allocate(blocks, total_budget=250, counter=TiktokenCounter())

    assert sum(block.token_count for block in allocated) <= 250
    assert dropped >= 0
    assert allocated[0].kind in {ContextKind.RECENT_TURN, ContextKind.USER_MEMORY, ContextKind.TOOL_RESULT}


@pytest.mark.asyncio
async def test_assembler_ignores_provider_failures_and_keeps_recent_turns() -> None:
    counter = TiktokenCounter()
    assembler = DefaultContextAssembler(
        providers=(
            FailingProvider(),
            RecentTurnsProvider(counter=counter),
            EchoProvider(),
        ),
        allocator=TokenBudgetAllocator(),
        token_counter=counter,
        total_budget=2000,
    )

    request = ContextRequest(
        conversation_id=UUID("11111111-1111-1111-1111-111111111111"),
        user_query="What happened?",
        authorization_context=AuthorizationContext(
            user_id=UUID("22222222-2222-2222-2222-222222222222"),
            roles=frozenset({RoleName.READ_ONLY_ANALYST}),
        ),
        recent_turns=[
            ConversationTurn(
                role="user",
                content="What happened?",
                created_at_utc=datetime.now(UTC),
            ),
            ConversationTurn(
                role="assistant",
                content="We are checking the status.",
                created_at_utc=datetime.now(UTC),
            ),
        ],
    )

    result = await assembler.assemble(request)

    assert isinstance(result, AssembledContext)
    assert result.total_tokens <= 2000
    assert any(block.kind is ContextKind.RECENT_TURN for block in result.blocks)
    assert result.render()
