import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.modules.assistant.domain.entities import ToolDescriptor
from app.modules.assistant.infrastructure.agents.langgraph.deterministic_intent import (
    extract_site_code,
    resolve_intent,
)


class SemanticRejectionReason(StrEnum):
    TOOL_NOT_REQUESTED = "tool_not_requested"
    TOOL_MISMATCH = "tool_mismatch"
    ENTITY_MISSING = "entity_missing"
    ENTITY_MISMATCH = "entity_mismatch"
    UNEXPECTED_ENTITY = "unexpected_entity"
    MUTATION_NOT_EXPLICIT = "mutation_not_explicit"
    MUTATION_NOT_SUPPORTED = "mutation_not_supported"


@dataclass(frozen=True, slots=True)
class SemanticValidationResult:
    allowed: bool
    reason: SemanticRejectionReason | None = None
    detail: str | None = None


_SEMANTIC_FIELDS_BY_TOOL: dict[str, frozenset[str]] = {
    "get_work_orders": frozenset({"site_code", "status", "limit"}),
    "get_asset_status": frozenset({"site_code"}),
    "get_maintenance_tickets": frozenset({"site_code", "limit"}),
    "get_spare_parts_availability": frozenset({"site_code", "limit"}),
    "get_production_schedule": frozenset({"site_code", "limit"}),
}
_DEFAULT_SEMANTIC_VALUES: dict[str, object] = {"limit": 10}
_WORK_ORDER_CODE_PATTERN = re.compile(r"\bWO-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)
_UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_WORK_ORDER_MUTATION_PATTERN = re.compile(
    r"\b(?:change|set|update|move|mark|complete|cancel|reopen|start)\b"
    r".{0,100}\b(?:work\s+order|WO-[A-Z0-9][A-Z0-9-]*)\b"
    r"|\b(?:work\s+order|WO-[A-Z0-9][A-Z0-9-]*)\b"
    r".{0,100}\b(?:change|set|update|move|mark|complete|cancel|reopen|start)\b",
    re.IGNORECASE,
)
_TARGET_STATUS_PATTERN = re.compile(
    r"\b(?:to|as)\s+(pending|open|in[\s_-]+progress|completed?|cancelled|canceled)\b",
    re.IGNORECASE,
)
_IMPERATIVE_TARGETS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcomplet(?:e|ed)\b", re.IGNORECASE), "completed"),
    (re.compile(r"\bcancel(?:led|ed)?\b", re.IGNORECASE), "cancelled"),
    (re.compile(r"\breopen\b", re.IGNORECASE), "open"),
    (re.compile(r"\bstart\b", re.IGNORECASE), "in_progress"),
)


def validate_tool_call_semantics(
    *,
    query: str,
    descriptor: ToolDescriptor,
    payload: dict[str, object],
) -> SemanticValidationResult:
    """Fail closed when a planned call contradicts explicit request semantics."""

    resolution = resolve_intent(query)
    if resolution is not None:
        if resolution.tool_name is None:
            return _reject(
                SemanticRejectionReason.TOOL_NOT_REQUESTED,
                "the request requires a direct response",
            )
        if descriptor.name != resolution.tool_name:
            return _reject(
                SemanticRejectionReason.TOOL_MISMATCH,
                f"expected {resolution.tool_name}, got {descriptor.name}",
            )
        entity_result = _validate_resolved_entities(
            descriptor.name,
            expected=resolution.payload,
            actual=payload,
        )
        if not entity_result.allowed:
            return entity_result

    explicit_site = extract_site_code(query)
    if resolution is None and explicit_site is not None and descriptor.site_code_field is not None:
        site_result = _require_matching_entity(
            field=descriptor.site_code_field,
            expected=explicit_site,
            actual=payload,
        )
        if not site_result.allowed:
            return site_result

    if descriptor.is_mutating:
        if descriptor.name != "write_work_order_status":
            return _reject(
                SemanticRejectionReason.MUTATION_NOT_SUPPORTED,
                f"no semantic validator is registered for {descriptor.name}",
            )
        return _validate_work_order_status_mutation(query, payload)

    return SemanticValidationResult(allowed=True)


def _validate_resolved_entities(
    tool_name: str,
    *,
    expected: dict[str, object],
    actual: dict[str, object],
) -> SemanticValidationResult:
    for field in _SEMANTIC_FIELDS_BY_TOOL.get(tool_name, frozenset()):
        if field in expected:
            result = _require_matching_entity(
                field=field,
                expected=expected[field],
                actual=actual,
            )
            if not result.allowed:
                return result
            continue

        actual_value = actual.get(field)
        if actual_value is None or actual_value == _DEFAULT_SEMANTIC_VALUES.get(field):
            continue
        return _reject(
            SemanticRejectionReason.UNEXPECTED_ENTITY,
            f"{field} was not present in the request",
        )

    return SemanticValidationResult(allowed=True)


def _require_matching_entity(
    *,
    field: str,
    expected: object,
    actual: dict[str, object],
) -> SemanticValidationResult:
    if field not in actual or actual[field] is None:
        return _reject(
            SemanticRejectionReason.ENTITY_MISSING,
            f"required entity {field} is missing",
        )
    if _canonical_entity(field, actual[field]) != _canonical_entity(field, expected):
        return _reject(
            SemanticRejectionReason.ENTITY_MISMATCH,
            f"{field} does not match the request",
        )
    return SemanticValidationResult(allowed=True)


def _validate_work_order_status_mutation(
    query: str,
    payload: dict[str, object],
) -> SemanticValidationResult:
    if not _WORK_ORDER_MUTATION_PATTERN.search(query):
        return _reject(
            SemanticRejectionReason.MUTATION_NOT_EXPLICIT,
            "the request does not explicitly ask to mutate a work order",
        )

    expected_status = _extract_target_status(query)
    if expected_status is None:
        return _reject(
            SemanticRejectionReason.MUTATION_NOT_EXPLICIT,
            "the requested target status is not explicit",
        )
    status_result = _require_matching_entity(
        field="target_status",
        expected=expected_status,
        actual=payload,
    )
    if not status_result.allowed:
        return status_result

    code_match = _WORK_ORDER_CODE_PATTERN.search(query)
    id_match = _UUID_PATTERN.search(query)
    if code_match is None and id_match is None:
        return _reject(
            SemanticRejectionReason.MUTATION_NOT_EXPLICIT,
            "the work order identifier is not explicit",
        )
    if code_match is not None:
        code_result = _require_matching_entity(
            field="work_order_code",
            expected=code_match.group(0).upper(),
            actual=payload,
        )
        if not code_result.allowed:
            return code_result
        if payload.get("work_order_id") is not None:
            return _reject(
                SemanticRejectionReason.UNEXPECTED_ENTITY,
                "work_order_id was not present in the request",
            )
    elif id_match is not None:
        id_result = _require_matching_entity(
            field="work_order_id",
            expected=str(UUID(id_match.group(0))),
            actual=payload,
        )
        if not id_result.allowed:
            return id_result
        if payload.get("work_order_code") is not None:
            return _reject(
                SemanticRejectionReason.UNEXPECTED_ENTITY,
                "work_order_code was not present in the request",
            )

    explicit_site = extract_site_code(query)
    payload_site = payload.get("site_code")
    if explicit_site is not None:
        return _require_matching_entity(
            field="site_code",
            expected=explicit_site,
            actual=payload,
        )
    if payload_site is not None:
        return _reject(
            SemanticRejectionReason.UNEXPECTED_ENTITY,
            "site_code was not present in the request",
        )

    return SemanticValidationResult(allowed=True)


def _extract_target_status(query: str) -> str | None:
    target_match = _TARGET_STATUS_PATTERN.search(query)
    if target_match is not None:
        return _canonical_status(target_match.group(1))
    for pattern, status in _IMPERATIVE_TARGETS:
        if pattern.search(query):
            return status
    return None


def _canonical_entity(field: str, value: object) -> object:
    if field in {"site_code", "work_order_code"} and isinstance(value, str):
        return value.strip().upper()
    if field in {"status", "target_status"} and isinstance(value, str):
        return _canonical_status(value)
    if field == "work_order_id":
        try:
            return str(UUID(str(value)))
        except ValueError:
            return str(value)
    if field == "limit" and isinstance(value, int) and not isinstance(value, bool):
        return value
    return value


def _canonical_status(value: str) -> str:
    normalized = re.sub(r"[\s-]+", "_", value.strip().lower())
    if normalized == "complete":
        return "completed"
    if normalized in {"cancelled", "canceled"}:
        return "cancelled"
    return normalized


def _reject(
    reason: SemanticRejectionReason,
    detail: str,
) -> SemanticValidationResult:
    return SemanticValidationResult(allowed=False, reason=reason, detail=detail)
