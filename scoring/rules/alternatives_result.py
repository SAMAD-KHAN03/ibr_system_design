from dataclasses import dataclass, field
from typing import List, Optional
from core.components_module import ComponentResult
from domain.enums import AlternativeScoreCategory

COMPONENT_NAME = "Alternatives"


@dataclass
class AlternativeEntry:
    """One scored alternative drug."""
    name:        str
    brand_name:  str
    generic_name: str
    drug_class:  str
    route:       str
    condition:   str
    score:       Optional[dict]   # full ScoringEngine output dict, None if failed
    component_outputs: dict       # name → metadata["output"] from each component

    @property
    def total_score(self) -> float:
        return self.score.get("ibr_score", 0.0) if self.score else 0.0

    def to_dict(self) -> dict:
        return {
            "name":              self.name,
            "brand_name":        self.brand_name,
            "generic_name":      self.generic_name,
            "drug_class":        self.drug_class,
            "route":             self.route,
            "condition":         self.condition,
            "ibr_score":         self.total_score,
            "ibr_outcome":       self.score.get("ibr_outcome", "Unknown") if self.score else "Unknown",
            "benefit_total":     self.score.get("benefit_total", 0.0) if self.score else 0.0,
            "risk_total":        self.score.get("risk_total", 0.0) if self.score else 0.0,
            "score_breakdown":   self.score,
            "component_outputs": self.component_outputs,
        }


@dataclass
class AlternativesResult(ComponentResult):
    entries: List[AlternativeEntry] = field(default_factory=list)

    @classmethod
    def build(cls, entries: List[AlternativeEntry]) -> "AlternativesResult":
        category = (
            AlternativeScoreCategory.NOT_FOUND if not entries
            else AlternativeScoreCategory.NONE_EXISTS  # component sets precise value
        )

        # Sort by score descending for easy reporting
        ranked = sorted(entries, key=lambda e: e.total_score, reverse=True)

        output_lines = []
        for i, e in enumerate(ranked, 1):
            output_lines.append(
                f"{i}. {e.name} ({e.brand_name}) — "
                f"Drug class: {e.drug_class} | "
                f"Route: {e.route} | "
                f"iBR Score: {e.total_score:.1f}"
            )
            for comp_name, comp_out in e.component_outputs.items():
                if comp_out:
                    output_lines.append(f"   [{comp_name}] {comp_out}")

        return cls(
            name=COMPONENT_NAME,
            category=category,
            entries=ranked,
            metadata={
                "total_alternatives": len(entries),
                "entries": [e.to_dict() for e in ranked],
                "output": "\n".join(output_lines) if output_lines else "No alternatives found.",
            },
        )
