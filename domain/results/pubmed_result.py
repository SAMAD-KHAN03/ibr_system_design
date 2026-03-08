from dataclasses import dataclass, field
from core.results.component_results import ComponentResult
from domain.enums import PubMedEvidenceCategory

COMPONENT_NAME = "PubMed"



@dataclass
class PubMedResult(ComponentResult):

    @classmethod
    def build(cls, drug: str, condition: str, rct_count: int, conclusions: list) -> "PubMedResult":
        if rct_count >= 10:
            category = PubMedEvidenceCategory.HIGH
        elif rct_count > 0:
            category = PubMedEvidenceCategory.MEDIUM
        else:
            category = PubMedEvidenceCategory.LOW

        # ── Doc format: Benefit factor sentence ──────────────────────────────
        output = (
            f"There are {rct_count} RCTs conducted for the evaluation of "
            f"{drug} use in {condition}."
        )

        return cls(
            name=COMPONENT_NAME,
            category=category,
            metadata={
                "drug": drug,
                "condition": condition,
                "rct_count": rct_count,
                "output": output,
            },
        )
