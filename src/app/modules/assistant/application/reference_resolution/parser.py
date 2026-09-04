from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.modules.assistant.application.reference_resolution.contracts import (
    ReferenceOperation,
    ReferenceRequest,
)


class ReferenceQueryParser(Protocol):
    def parse(self, query: str) -> ReferenceRequest | None: ...


@dataclass(frozen=True, slots=True)
class RegexReferenceQueryParser:
    field_patterns: tuple[tuple[str, str], ...]
    maximum_patterns: tuple[str, ...] = ()
    minimum_patterns: tuple[str, ...] = ()
    reference_pattern: str = (
        r"\b(?:above|previous|those|they|them|these|it)\b|"
        r"\b(?:the\s+)?(?:first|second|third|fourth|fifth)\s+(?:one|item)\b"
    )

    def parse(self, query: str) -> ReferenceRequest | None:
        if re.search(self.reference_pattern, query, re.IGNORECASE) is None:
            return None
        field_name = next(
            (
                configured_field
                for pattern, configured_field in self.field_patterns
                if re.search(pattern, query, re.IGNORECASE) is not None
            ),
            None,
        )
        if field_name is None:
            return None
        return ReferenceRequest(
            field_name=field_name,
            operation=self._operation(query),
            ordinal=_extract_ordinal(query),
        )

    def _operation(self, query: str) -> ReferenceOperation:
        if any(re.search(pattern, query, re.IGNORECASE) for pattern in self.maximum_patterns):
            return ReferenceOperation.MAXIMUM
        if any(re.search(pattern, query, re.IGNORECASE) for pattern in self.minimum_patterns):
            return ReferenceOperation.MINIMUM
        return ReferenceOperation.FIELD


def _extract_ordinal(query: str) -> int | None:
    match = re.search(
        r"\b(?P<ordinal>first|second|third|fourth|fifth)\s+(?:one|item)\b",
        query,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}[
        match.group("ordinal").lower()
    ]