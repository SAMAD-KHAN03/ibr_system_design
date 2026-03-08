from dataclasses import dataclass
from core.results.component_results import ComponentResult
from domain.enums import ApprovalCategory
from typing import List
from dataclasses import dataclass, field

COMPONENT_NAME = "ApprovalStatus"



@dataclass
class DrugApprovalEntry:
    drug: str
    condition: str
    source: str
    approved: bool
    category: ApprovalCategory

    @property
    def output(self) -> str:
        if self.approved:
            return (
                f"{self.drug} is approved for use in {self.condition} as per the "
                f"USFDA's USPI (United States Prescriber Information)."
            )
        return (
            f"{self.drug} is not found to be approved for use in {self.condition} "
            f"as per the USFDA's USPI. Please consider alternative medications "
            f"or review clinical evidence."
        )

    def to_dict(self) -> dict:
        output = self.output
        return {
            "drug": self.drug,
            "condition": self.condition,
            "source": self.source,
            "approved": self.approved,
            "category": self.category.value,
            "output": output,
        }


@dataclass
class ApprovalStatusResult(ComponentResult):
    entries: List[DrugApprovalEntry] = field(default_factory=list)

    @classmethod
    def build(cls, entries: List[DrugApprovalEntry]) -> "ApprovalStatusResult":
        primary = next((e for e in entries if e.source == "primary"), None)
        top_category = primary.category if primary else ApprovalCategory.NOT_FOUND

        approved_count = sum(1 for e in entries if e.approved)
        total_count    = len(entries)

        # ── Doc format: one output sentence per drug ─────────────────────────
        entry_outputs = [e.to_dict()["output"] for e in entries]

        return cls(
            name=COMPONENT_NAME,
            category=top_category,
            entries=entries,
            metadata={
                "summary": {
                    "total_checked": total_count,
                    "approved_count": approved_count,
                    "off_label_count": total_count - approved_count,
                },
                "entries": [e.to_dict() for e in entries],
                # Single formatted output block for UI/report rendering
                "output": "\n".join(entry_outputs),
            },
        )
