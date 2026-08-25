from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.modules.assistant.tool_gateway.domain import (
    SideEffectType,
    ToolDefinition,
    ToolRateLimit,
)
from app.modules.operations.application.change_work_order_status import (
    ChangeWorkOrderStatus,
    ChangeWorkOrderStatusCommand,
)
from app.modules.operations.application.ports import WorkOrderStatusStore
from app.modules.operations.domain.errors import (
    InvalidWorkOrderStatusTransitionError,
    WorkOrderNotFoundError,
    WorkOrderTerminalStatusError,
)
from app.modules.operations.domain.manufacturing_maintenance.work_order_status import (
    WorkOrderStatus,
    allowed_next_statuses,
)
from app.modules.user.domain.authorization import Permission
from app.shared.domain.errors import DomainError

TOOL_NAME = "write_work_order_status"

TOOL_DESCRIPTION = (
    "Change the status of an existing work order. Mutating and approval-gated. "
    "Only these transitions are legal: pending -> open|cancelled, open -> in_progress|cancelled, "
    "in_progress -> open|completed|cancelled. completed and cancelled are terminal. "
    "A reason is mandatory when moving to completed or cancelled. "
    "Setting the status the work order already has is a no-op, not an error. "
    "Read the work order first with get_work_orders if the current status is unknown."
)


class WriteWorkOrderStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    work_order_id: UUID | None = Field(
        default=None,
        description="Unique UUID of the work order",
    )

    work_order_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Business code of the work order, not its UUID",
    )

    target_status: WorkOrderStatus = Field(
        validation_alias=AliasChoices("target_status", "status"),
        description="Status to move the work order to"
    )

    site_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Used to disambiguate duplicate work-order codes",
    )

    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Required when target_status is completed or cancelled",
    )


class WriteWorkOrderStatusOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = TOOL_NAME
    succeeded: bool
    work_order_id: UUID | None = None
    work_order_code: str | None = None
    previous_status: str | None = None
    current_status: str | None = None
    changed: bool = False
    updated_at: str | None = None
    allowed_next_statuses: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


def _rejection(
    *,
    work_order_code: str | None = None,
    error: DomainError,
    current: WorkOrderStatus | None,
) -> WriteWorkOrderStatusOutput:
    return WriteWorkOrderStatusOutput(
        succeeded=False,
        work_order_code=work_order_code,
        current_status=current.value if current is not None else None,
        allowed_next_statuses=(
            [status.value for status in allowed_next_statuses(current)]
            if current is not None
            else []
        ),
        error_code=error.code,
        error_message=str(error),
    )


def build_write_work_order_status_tool(
    store_factory: Callable[[], WorkOrderStatusStore],
) -> ToolDefinition:
    async def handler(payload: dict[str, Any]) -> dict[str, Any]:
        data = WriteWorkOrderStatusInput.model_validate(payload)
        use_case = ChangeWorkOrderStatus(store=store_factory())

        try:
            result = await use_case.execute(
                ChangeWorkOrderStatusCommand(
                    work_order_id=data.work_order_id,
                    work_order_code=data.work_order_code,
                    target_status=data.target_status,
                    reason=data.reason,
                )
            )
        except WorkOrderNotFoundError as error:
            return _rejection(
                work_order_code=data.work_order_code, error=error, current=None
            ).model_dump(mode="json")
        except (InvalidWorkOrderStatusTransitionError, WorkOrderTerminalStatusError) as error:
            return _rejection(
                work_order_code=data.work_order_code, error=error, current=error.current
            ).model_dump(mode="json")
        except DomainError as error:
            return _rejection(
                work_order_code=data.work_order_code, error=error, current=None
            ).model_dump(mode="json")

        output = WriteWorkOrderStatusOutput(
            succeeded=True,
            work_order_code=result.work_order_code,
            previous_status=result.previous_status.value,
            current_status=result.current_status.value,
            changed=result.changed,
            updated_at=result.updated_at.isoformat() if result.updated_at else None,
            allowed_next_statuses=[
                status.value for status in allowed_next_statuses(result.current_status)
            ],
        )
        return output.model_dump(mode="json")

    return ToolDefinition(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        input_model=WriteWorkOrderStatusInput,
        output_model=WriteWorkOrderStatusOutput,
        handler=handler,
        required_permission=Permission.WORK_ORDERS_CHANGE_STATUS,
        requires_approval=True,
        approval_scope="write",
        max_retries=0,
        rate_limit=ToolRateLimit(max_calls=3, window_seconds=60),
        side_effect_type=SideEffectType.WRITE,
    )
