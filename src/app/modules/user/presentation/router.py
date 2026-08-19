from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.container import get_container
from app.modules.user.application.use_cases import (
    GetUser,
    RegisterUser,
    RegisterUserCommand,
    UserConsistencyAuditCommand,
)
from app.modules.user.contracts.consistency_auditor import (
    UserConsistencyAuditorInputV1,
    UserConsistencyAuditorOutputV1,
)
from app.modules.user.presentation.schemas import RegisterUserRequest, UserResponse
from app.modules.user.presentation.user_auditor_tools import (
    to_user_consistency_auditor_output,
)
from app.modules.user.wiring import UsersModule

router = APIRouter(prefix="/users", tags=["users"])
def get_users_module(request: Request) -> UsersModule:
    return get_container(request).users

def get_register_user(request: Request) -> RegisterUser:
    return get_container(request).users.register_user

def get_user_query(request: Request) -> GetUser:
    return get_container(request).users.get_user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: RegisterUserRequest,
    use_case: Annotated[RegisterUser, Depends(get_register_user)],
) -> UserResponse:
    result = await use_case.execute(
        RegisterUserCommand(email=str(payload.email), display_name=payload.display_name)
    )
    return UserResponse.model_validate(result)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    use_case: Annotated[GetUser, Depends(get_user_query)],
) -> UserResponse:
    result = await use_case.execute(user_id)
    return UserResponse.model_validate(result)


@router.post(
    "/_ops/consistency-audit",
    response_model=UserConsistencyAuditorOutputV1,
)
async def run_consistency_audit(
    payload: UserConsistencyAuditorInputV1,
    module: Annotated[UsersModule, Depends(get_users_module)]
) -> UserConsistencyAuditorOutputV1:
    if not module.audit_endpoint_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    report = await module.consistency_audit.execute(
        UserConsistencyAuditCommand(
            checks=tuple(check.value for check in payload.checks) if payload.checks else None,
            limit_per_check=payload.limit_per_check,
            run_id=payload.run_id,
            now_utc=payload.now_utc,
        )
    )

    return to_user_consistency_auditor_output(report)
