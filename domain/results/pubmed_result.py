from dataclasses import dataclass, field
from typing import List
from core.results.component_results import ComponentResult
from domain.enums import PubMedEvidenceCategory

COMPONENT_NAME = "PubMed"


@dataclass
class DrugPubMedEntry:
    drug: str
    condition: str
    source: str
    rct_count: int
    category: PubMedEvidenceCategory

    @property
    def output(self) -> str:
        return (
            f"There are {self.rct_count} RCTs conducted for the evaluation of "
            f"{self.drug} use in {self.condition}."
        )

    def to_dict(self) -> dict:
        return {
            "drug": self.drug,
            "condition": self.condition,
            "source": self.source,
            "rct_count": self.rct_count,
            "category": self.category.value,
            "output": self.output,
        }


@dataclass
class PubMedResult(ComponentResult):
    entries: List[DrugPubMedEntry] = field(default_factory=list)

    @classmethod
    def build(cls, entries: List[DrugPubMedEntry]) -> "PubMedResult":
        # Primary drug drives the top-level category
        primary = next((e for e in entries if e.source == "primary"), None)
        top_category = primary.category if primary else PubMedEvidenceCategory.LOW

        return cls(
            name=COMPONENT_NAME,
            category=top_category,
            entries=entries,
            metadata={
                "summary": {
                    "total_checked": len(entries),
                },
                "entries": [e.to_dict() for e in entries],
                "output": "\n".join(e.output for e in entries),
            },
        )
