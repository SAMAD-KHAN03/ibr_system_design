from dataclasses import dataclass, field
from typing import List
from core.results.component_results import ComponentResult
from domain.enums import ContraindicationCategory

COMPONENT_NAME = "Contraindication"


@dataclass
class DrugContraindicationEntry:
    drug: str
    source: str
    treating_condition: str
    category: ContraindicationCategory
    risk_concepts: list
    clinical_explanation: str

    @property
    def is_contraindicated(self) -> bool:
        return self.category != ContraindicationCategory.SAFE

    def to_dict(self) -> dict:
        # ── Doc format: Unfavorable outcome sentence ─────────────────────────
        if self.is_contraindicated:
            risk_label = ", ".join(r.replace("_", " ").lower() for r in self.risk_concepts)
            output = (
                f"Unsafe to Use in this patient because {self.drug} is contraindicated "
                f"in patients with {risk_label}."
            )
            if self.clinical_explanation:
                output += f" {self.clinical_explanation}"
        else:
            output = (
                f"{self.drug} — No contraindications detected for use in "
                f"{self.treating_condition}."
            )

        return {
            "drug": self.drug,
            "source": self.source,
            "treating_condition": self.treating_condition,
            "contraindicated": self.is_contraindicated,
            "category": self.category.value,
            "risk_concepts": self.risk_concepts,
            "clinical_explanation": self.clinical_explanation,
            "output": output,
        }


@dataclass
class ContraindicationResult(ComponentResult):
    entries: List[DrugContraindicationEntry] = field(default_factory=list)

    @classmethod
    def build(cls, entries: List[DrugContraindicationEntry]) -> "ContraindicationResult":
        severity_order = [
            ContraindicationCategory.ABSOLUTE,
            ContraindicationCategory.BOXED_WARNING,
            ContraindicationCategory.PREGNANCY,
            ContraindicationCategory.SAFE,
        ]

        worst = ContraindicationCategory.SAFE
        for level in severity_order:
            if any(e.category == level for e in entries):
                worst = level
                break

        flagged = [e for e in entries if e.is_contraindicated]

        # ── Doc format: one output sentence per drug ─────────────────────────
        entry_outputs = [e.to_dict()["output"] for e in entries]

        return cls(
            name=COMPONENT_NAME,
            category=worst,
            entries=entries,
            metadata={
                "overall_safe": worst == ContraindicationCategory.SAFE,
                "summary": {
                    "total_checked": len(entries),
                    "contraindicated_count": len(flagged),
                    "safe_count": len(entries) - len(flagged),
                    "worst_category": worst.value,
                },
                "flagged_drugs": [e.to_dict() for e in flagged],
                "all_entries": [e.to_dict() for e in entries],
                # Single formatted output block for UI/report rendering
                "output": "\n".join(entry_outputs),
            },
        )
