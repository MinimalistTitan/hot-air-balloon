import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ResultRejectionReason(StrEnum):
    TOOL_IDENTITY_MISMATCH = "tool_identity_mismatch"
    MALFORMED_RESULT = "malformed_result"
    APPLIED_PAYLOAD_MISMATCH = "applied_payload_mismatch"
    COLLECTION_TOO_LARGE = "collection_too_large"
    RESULT_ENTITY_MISSING = "result_entity_missing"
    RESULT_ENTITY_MISMATCH = "result_entity_mismatch"
    RESULT_ORDER_MISMATCH = "result_order_mismatch"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    allowed: bool
    reason: ResultRejectionReason | None = None
    detail: str | None = None


_EXECUTION_STATUSES = {
    "success",
    "rejected",
    "approval_required",
    "rate_limited",
    "failed",
}
_COLLECTION_KEYS = {
    "get_work_orders": "work_orders",
    "get_asset_status": "assets",
    "get_maintenance_tickets": "tickets",
    "get_spare_parts_availability": "spare_parts",
    "get_production_schedule": "schedule",
}
_LIMITED_TOOLS = frozenset(
    {
        "get_work_orders",
        "get_maintenance_tickets",
        "get_spare_parts_availability",
        "get_production_schedule",
    }
)
_MAINTENANCE_STATUSES = frozenset({"open", "in_progress", "pending"})
_WORK_ORDER_CODE_PATTERN = re.compile(r"\bWO-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)


def validate_tool_result(
    *,
    query: str,
    tool_name: str,
    payload: dict[str, object],
    result: dict[str, object],
) -> ValidationResult:
    """Validate trusted result structure and request-constrained business records."""

    if result.get("tool_name") != tool_name:
        return _reject(
            ResultRejectionReason.TOOL_IDENTITY_MISMATCH,
            "the result tool identity does not match the invoked tool",
        )

    business_result = result
    effective_payload = dict(payload)
    execution_status = result.get("status")
    if isinstance(execution_status, str) and execution_status in _EXECUTION_STATUSES:
        if execution_status != "success":
            return ValidationResult(allowed=True)

        applied_payload = result.get("applied_payload")
        if not isinstance(applied_payload, dict):
            return _reject(
                ResultRejectionReason.MALFORMED_RESULT,
                "a successful gateway result lacks its applied payload",
            )
        applied_result = _validate_applied_payload(payload, applied_payload)
        if not applied_result.allowed:
            return applied_result
        effective_payload.update(applied_payload)

        nested_result = result.get("result")
        if not isinstance(nested_result, dict):
            return _reject(
                ResultRejectionReason.MALFORMED_RESULT,
                "a successful gateway result lacks a business result object",
            )
        if nested_result.get("tool_name") != tool_name:
            return _reject(
                ResultRejectionReason.TOOL_IDENTITY_MISMATCH,
                "the nested result tool identity does not match the invoked tool",
            )
        business_result = nested_result

    collection_key = _COLLECTION_KEYS.get(tool_name)
    if collection_key is not None:
        return _validate_collection_result(
            query=query,
            tool_name=tool_name,
            collection_key=collection_key,
            payload=effective_payload,
            result=business_result,
        )
    if tool_name == "write_work_order_status":
        return _validate_work_order_write_result(effective_payload, business_result)
    return ValidationResult(allowed=True)


def _validate_applied_payload(
    requested: dict[str, object],
    applied: dict[object, object],
) -> ValidationResult:
    for field, requested_value in requested.items():
        if field not in applied:
            return _reject(
                ResultRejectionReason.APPLIED_PAYLOAD_MISMATCH,
                f"the applied payload omits {field}",
            )
        if _canonical(field, applied[field]) != _canonical(field, requested_value):
            return _reject(
                ResultRejectionReason.APPLIED_PAYLOAD_MISMATCH,
                f"the applied {field} does not match the planned call",
            )
    return ValidationResult(allowed=True)


def _validate_collection_result(
    *,
    query: str,
    tool_name: str,
    collection_key: str,
    payload: dict[str, object],
    result: dict[str, object],
) -> ValidationResult:
    records = result.get(collection_key)
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        return _reject(
            ResultRejectionReason.MALFORMED_RESULT,
            f"{collection_key} must be a list of objects",
        )

    if tool_name in _LIMITED_TOOLS:
        limit = payload.get("limit", 10)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            return _reject(
                ResultRejectionReason.MALFORMED_RESULT,
                "the applied limit is invalid",
            )
        if len(records) > limit:
            return _reject(
                ResultRejectionReason.COLLECTION_TOO_LARGE,
                f"{collection_key} exceeds the applied limit",
            )

    site_code = payload.get("site_code")
    if site_code is not None:
        for record in records:
            site_result = _require_record_entity(record, "site_code", site_code)
            if not site_result.allowed:
                return site_result

    if tool_name == "get_work_orders":
        expected_status = payload.get("status")
        if expected_status is not None:
            for record in records:
                status_result = _require_record_entity(record, "status", expected_status)
                if not status_result.allowed:
                    return status_result

        requested_code = _WORK_ORDER_CODE_PATTERN.search(query)
        if records and requested_code is not None:
            expected_code = requested_code.group(0).upper()
            if not any(
                _canonical("code", record.get("code")) == expected_code for record in records
            ):
                return _reject(
                    ResultRejectionReason.RESULT_ENTITY_MISMATCH,
                    "the requested work order is absent from the non-empty result",
                )

    if tool_name == "get_maintenance_tickets":
        for record in records:
            if _canonical("status", record.get("status")) not in _MAINTENANCE_STATUSES:
                return _reject(
                    ResultRejectionReason.RESULT_ENTITY_MISMATCH,
                    "a maintenance ticket has an unsupported status",
                )

    if tool_name == "get_production_schedule":
        due_values: list[str] = []
        for record in records:
            due_at = record.get("due_at")
            if not isinstance(due_at, str) or not due_at.strip():
                return _reject(
                    ResultRejectionReason.RESULT_ENTITY_MISSING,
                    "a production schedule record lacks due_at",
                )
            due_values.append(due_at)
        if due_values != sorted(due_values):
            return _reject(
                ResultRejectionReason.RESULT_ORDER_MISMATCH,
                "the production schedule is not ordered by due_at",
            )

    return ValidationResult(allowed=True)


def _validate_work_order_write_result(
    payload: dict[str, object],
    result: dict[str, object],
) -> ValidationResult:
    succeeded = result.get("succeeded")
    if not isinstance(succeeded, bool):
        return _reject(
            ResultRejectionReason.MALFORMED_RESULT,
            "the write result lacks a succeeded flag",
        )

    for field in ("work_order_code", "work_order_id"):
        expected = payload.get(field)
        if expected is not None:
            identifier_result = _require_record_entity(result, field, expected)
            if not identifier_result.allowed:
                return identifier_result

    if succeeded:
        return _require_record_entity(result, "current_status", payload.get("target_status"))
    return ValidationResult(allowed=True)


def _require_record_entity(
    record: Mapping[str, object],
    field: str,
    expected: object,
) -> ValidationResult:
    if field not in record or record[field] is None:
        return _reject(
            ResultRejectionReason.RESULT_ENTITY_MISSING,
            f"a result record lacks {field}",
        )
    if _canonical(field, record[field]) != _canonical(field, expected):
        return _reject(
            ResultRejectionReason.RESULT_ENTITY_MISMATCH,
            f"a result record has a conflicting {field}",
        )
    return ValidationResult(allowed=True)


def _canonical(field: str, value: object) -> object:
    if field in {"site_code", "code", "work_order_code"} and isinstance(value, str):
        return value.strip().upper()
    if field in {"status", "target_status", "current_status"} and isinstance(value, str):
        normalized = re.sub(r"[\s-]+", "_", value.strip().lower())
        if normalized == "complete":
            return "completed"
        if normalized in {"cancelled", "canceled"}:
            return "cancelled"
        return normalized
    return value


def _reject(reason: ResultRejectionReason, detail: str) -> ValidationResult:
    return ValidationResult(allowed=False, reason=reason, detail=detail)
