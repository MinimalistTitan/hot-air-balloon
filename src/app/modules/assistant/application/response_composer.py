from dataclasses import dataclass

from app.shared.kernel.response_evidence import (
    ActionRequiredEvidence,
    CollectionEvidence,
    EvidenceBlock,
    FailureEvidence,
    MutationEvidence,
)


@dataclass(frozen=True, slots=True)
class ComposedResponse:
    answer: str
    blocks: tuple[EvidenceBlock, ...]


class FinalResponseComposer:
    def compose(
        self,
        query: str,
        evidence: tuple[EvidenceBlock, ...],
    ) -> ComposedResponse:
        del query
        if not evidence:
            raise ValueError("evidence is required")

        sections = [self._render(block) for block in evidence]
        return ComposedResponse(
            answer="\n\n".join(sections),
            blocks=evidence,
        )

    def _render(self, block: EvidenceBlock) -> str:
        match block:
            case CollectionEvidence():
                return self._collection(block)
            case MutationEvidence():
                return self._mutation(block)
            case ActionRequiredEvidence():
                return f"Action required: {block.action}. Reason: {block.reason}."
            case FailureEvidence():
                return f"Unable to complete the request ({block.code}): {block.message}"

    def _collection(self, block: CollectionEvidence) -> str:
        count = len(block.items)
        label = block.entity_label if count == 1 else block.entity_label_plural
        filters = ", ".join(f"{field.label}: {field.value}" for field in block.filters)
        suffix = f" ({filters})" if filters else ""

        if count == 0:
            return f"No {block.entity_label_plural} found{suffix}."

        header = f"Found {count} {label}{suffix}"
        if block.requested_count is not None and count < block.requested_count:
            header += f", fewer than the {block.requested_count} requested"

        rows = [f"{index}. {item.label}" for index, item in enumerate(block.items, start=1)]
        return f"{header}:\n" + "\n".join(rows)

    def _mutation(self, block: MutationEvidence) -> str:
        if not block.changed:
            return (
                f"{block.entity_label.title()} {block.entity_id} is already {block.current_state}."
            )

        if block.previous_state is None:
            return f"{block.entity_label.title()} {block.entity_id} is now {block.current_state}."

        return (
            f"{block.entity_label.title()} {block.entity_id} changed from "
            f"{block.previous_state} to {block.current_state}."
        )
