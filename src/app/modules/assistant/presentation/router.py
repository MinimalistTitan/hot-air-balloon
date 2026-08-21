from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.container import get_container
from app.modules.assistant.application.commands import AssistantQueryCommand
from app.modules.assistant.contracts.messages import (
    AssistantMemoryEraseResponseV1,
    AssistantQueryRequestV1,
    AssistantQueryResponseV1,
)
from app.modules.assistant.wiring import AssistantModule
from app.modules.user.domain.authorization import AuthorizationContext, Permission

router = APIRouter(prefix="/assistant", tags=["assistant"])


def get_assistant_module(request: Request) -> AssistantModule:
    module = get_container(request).assistant

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant is not configured",
        )

    return module


def get_authorization_context(request: Request) -> AuthorizationContext:
    authorization_context = getattr(request.state, "authorization_context", None)
    if not isinstance(authorization_context, AuthorizationContext):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required to invoke assistant tools",
        )

    return authorization_context


@router.post("/query", response_model=AssistantQueryResponseV1)
async def query_assistant(
    payload: AssistantQueryRequestV1,
    module: Annotated[
        AssistantModule,
        Depends(get_assistant_module),
    ],
    authorization_context: Annotated[
        AuthorizationContext,
        Depends(get_authorization_context),
    ],
) -> AssistantQueryResponseV1:
    return await module.query.execute(
        AssistantQueryCommand(
            query=payload.query,
            authorization_context=authorization_context,
            conversation_id=payload.conversation_id,
            max_tool_calls=payload.max_tool_calls,
            allow_tool_calls=payload.allow_tool_calls,
        )
    )


@router.post("/memory/erase-self", response_model=AssistantMemoryEraseResponseV1)
async def erase_own_memory(
    module: Annotated[
        AssistantModule,
        Depends(get_assistant_module),
    ],
    authorization_context: Annotated[
        AuthorizationContext,
        Depends(get_authorization_context),
    ],
) -> AssistantMemoryEraseResponseV1:
    if module.erase_user_memory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Long-term memory erasure is not configured",
        )

    result = await module.erase_user_memory.execute(authorization_context.user_id)
    return AssistantMemoryEraseResponseV1(
        user_id=authorization_context.user_id,
        deleted_memory_records=result.deleted_memory_records,
        deleted_vectors=result.deleted_vectors,
        deleted_turns=result.deleted_turns,
        deleted_conversations=result.deleted_conversations,
    )


@router.post("/memory/erase-user/{user_id}", response_model=AssistantMemoryEraseResponseV1)
async def erase_user_memory_admin(
    user_id: UUID,
    module: Annotated[
        AssistantModule,
        Depends(get_assistant_module),
    ],
    authorization_context: Annotated[
        AuthorizationContext,
        Depends(get_authorization_context),
    ],
) -> AssistantMemoryEraseResponseV1:
    if not authorization_context.can(Permission.USERS_MANAGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="users:manage permission is required",
        )

    if module.erase_user_memory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Long-term memory erasure is not configured",
        )

    result = await module.erase_user_memory.execute(user_id)
    return AssistantMemoryEraseResponseV1(
        user_id=user_id,
        deleted_memory_records=result.deleted_memory_records,
        deleted_vectors=result.deleted_vectors,
        deleted_turns=result.deleted_turns,
        deleted_conversations=result.deleted_conversations,
    )
