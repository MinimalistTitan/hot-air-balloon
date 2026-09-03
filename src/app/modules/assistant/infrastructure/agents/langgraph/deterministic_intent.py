import re
from dataclasses import dataclass
from enum import StrEnum


class DeterministicIntent(StrEnum):
    """High-confidence intents that do not require LLM interpretation."""

    DIRECT_RESPONSE = "direct_response"
    LIST_WORK_ORDERS = "list_work_orders"
    GET_ASSET_STATUS = "get_asset_status"
    LIST_MAINTENANCE_TICKETS = "list_maintenance_tickets"
    CHECK_SPARE_PARTS = "check_spare_parts"
    GET_PRODUCTION_SCHEDULE = "get_production_schedule"


@dataclass(frozen=True, slots=True)
class IntentResolution:
    intent: DeterministicIntent
    tool_name: str | None
    payload: dict[str, object]


_NO_TOOL_PATTERN = re.compile(
    r"\b(?:do\s+not|don['\u2019]t|never)\s+(?:call|invoke|use)\s+(?:any\s+)?tools?\b"
    r"|\bwithout\s+(?:calling|invoking|using)?\s*(?:any\s+)?tools?\b"
    r"|\bno\s+tool\s+calls?\b",
    re.IGNORECASE,
)
_INFORMATIONAL_PATTERN = re.compile(
    r"^\s*(?:explain|define)\b|^\s*what\s+(?:is|are)\s+(?:a|an)\b",
    re.IGNORECASE,
)
_SITE_PATTERN = re.compile(
    r"\b(?:at|for|in|site)\s+(?:site\s+)?([a-z0-9]+(?:-[a-z0-9]+)+)\b",
    re.IGNORECASE,
)
_LIMIT_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_LIMIT_VALUE_PATTERN = rf"(?:\d+|{'|'.join(_LIMIT_WORDS)})"
_LIMIT_PATTERN = re.compile(
    rf"\b(?:top|first|limit(?:ed\s+to)?|show(?:\s+me)?|list|display|give\s+me)"
    rf"\s+(?:the\s+)?(?P<limit>{_LIMIT_VALUE_PATTERN})\b",
    re.IGNORECASE,
)
_WORK_ORDER_CODE_PATTERN = re.compile(r"\bWO-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)
_RETRIEVAL_PATTERN = re.compile(
    r"\b(?:show|list|find|get|fetch|retrieve|display|give\s+me)\b",
    re.IGNORECASE,
)
_DUE_SCHEDULE_PATTERN = re.compile(
    r"\bproduction\s+schedule\b"
    r"|\b(?:work\s+orders?)\b.{0,40}\b(?:due|deadline|schedule|upcoming)\b"
    r"|\b(?:due|upcoming)\b.{0,40}\bwork\s+orders?\b",
    re.IGNORECASE,
)
_SPARE_PARTS_PATTERN = re.compile(
    r"\bspare\s+parts?\b|\bparts?\s+(?:availability|inventory|stock)\b",
    re.IGNORECASE,
)
_MAINTENANCE_TICKETS_PATTERN = re.compile(r"\bmaintenance\s+tickets?\b", re.IGNORECASE)
_ASSET_STATUS_PATTERN = re.compile(
    r"\basset\s+status(?:es)?\b|\bstatus\s+of\s+(?:the\s+)?assets?\b",
    re.IGNORECASE,
)
_WORK_ORDERS_PATTERN = re.compile(r"\bwork\s+orders?\b", re.IGNORECASE)

_STATUS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bin[\s_-]+progress\b", re.IGNORECASE), "in_progress"),
    (re.compile(r"\bcompleted?\b", re.IGNORECASE), "completed"),
    (re.compile(r"\bcancel(?:led|ed)\b", re.IGNORECASE), "cancelled"),
    (re.compile(r"\bpending\b", re.IGNORECASE), "pending"),
    (re.compile(r"\bopen\b", re.IGNORECASE), "open"),
)


def resolve_intent(query: str) -> IntentResolution | None:
    """Resolve only intents whose tool and supported entities are unambiguous."""

    if _NO_TOOL_PATTERN.search(query):
        return IntentResolution(
            intent=DeterministicIntent.DIRECT_RESPONSE,
            tool_name=None,
            payload={},
        )

    if _INFORMATIONAL_PATTERN.search(query):
        return IntentResolution(
            intent=DeterministicIntent.DIRECT_RESPONSE,
            tool_name=None,
            payload={},
        )

    payload = _common_payload(query)

    if _DUE_SCHEDULE_PATTERN.search(query):
        return IntentResolution(
            intent=DeterministicIntent.GET_PRODUCTION_SCHEDULE,
            tool_name="get_production_schedule",
            payload=payload,
        )

    if _SPARE_PARTS_PATTERN.search(query) and _RETRIEVAL_PATTERN.search(query):
        return IntentResolution(
            intent=DeterministicIntent.CHECK_SPARE_PARTS,
            tool_name="get_spare_parts_availability",
            payload=payload,
        )

    if _MAINTENANCE_TICKETS_PATTERN.search(query) and _RETRIEVAL_PATTERN.search(query):
        return IntentResolution(
            intent=DeterministicIntent.LIST_MAINTENANCE_TICKETS,
            tool_name="get_maintenance_tickets",
            payload=payload,
        )

    if _ASSET_STATUS_PATTERN.search(query):
        return IntentResolution(
            intent=DeterministicIntent.GET_ASSET_STATUS,
            tool_name="get_asset_status",
            payload=_site_payload(query),
        )

    if (
        _WORK_ORDERS_PATTERN.search(query)
        and _RETRIEVAL_PATTERN.search(query)
        and not _WORK_ORDER_CODE_PATTERN.search(query)
    ):
        status = _extract_status(query)
        if status is not None:
            payload["status"] = status
        return IntentResolution(
            intent=DeterministicIntent.LIST_WORK_ORDERS,
            tool_name="get_work_orders",
            payload=payload,
        )

    return None


def _common_payload(query: str) -> dict[str, object]:
    payload = _site_payload(query)
    limit = _extract_limit(query)
    if limit is not None:
        payload["limit"] = limit
    return payload


def _site_payload(query: str) -> dict[str, object]:
    site_code = extract_site_code(query)
    if site_code is None:
        return {}
    return {"site_code": site_code}


def extract_site_code(query: str) -> str | None:
    """Extract and canonicalize an explicitly named site code."""

    for site_match in _SITE_PATTERN.finditer(query):
        site_code = site_match.group(1).upper()
        if not _WORK_ORDER_CODE_PATTERN.fullmatch(site_code):
            return site_code
    return None


def _extract_limit(query: str) -> int | None:
    limit_match = _LIMIT_PATTERN.search(query)
    if limit_match is None:
        return None
    raw_limit = limit_match.group("limit").lower()
    limit = int(raw_limit) if raw_limit.isdecimal() else _LIMIT_WORDS[raw_limit]
    return limit if 1 <= limit <= 100 else None


def _extract_status(query: str) -> str | None:
    for pattern, status in _STATUS_PATTERNS:
        if pattern.search(query):
            return status
    return None
