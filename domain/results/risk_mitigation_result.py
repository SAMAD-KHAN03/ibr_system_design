from dataclasses import dataclass, field
from typing import Any, Dict
from core.results.component_results import ComponentResult
from domain.enums import PreventabilityCategory, ReversibilityCategory

COMPONENT_NAME = "RiskMitigation"


@dataclass
class RiskMitigationResult(ComponentResult):
    """
    Stores Factor 3.4 results: risk reversibility (R5) and preventability (R4).

    category             → PreventabilityCategory  for PreventabilityRule (R4)
    reversibility_category → ReversibilityCategory for ReversibilityRule  (R5)
    raw                  → full RiskMitigationAnalyzer.analyze() dict
    """
    reversibility_category: ReversibilityCategory = ReversibilityCategory.REVERSIBLE
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(cls, mitigation_analysis: Dict[str, Any]) -> "RiskMitigationResult":
        """
        Derives worst-case R4 and R5 categories across all ADRs.

        R4 (Preventability) — worst case:
          Non-Tolerable ADR | Non-preventable ADR → NON_PREVENTABLE (score=3×80=240)
          Preventable ADR                         → PREVENTABLE     (score=2×50=100)

        R5 (Reversibility) — worst case:
          Irreversible ADR → IRREVERSIBLE (score=3×95=285)
          Reversible ADR   → REVERSIBLE   (score=1×40=40)
          Tolerable ADR    → REVERSIBLE   (maps to reversible, tolerable means manageable)
        """
        rev_data  = mitigation_analysis.get("reversibility_results", {})
        prev_data = mitigation_analysis.get("preventability_results", {})

        # ── R5: worst-case reversibility ──────────────────────────────────────
        rev_category = ReversibilityCategory.REVERSIBLE
        for entry in rev_data.values():
            if "Irreversible" in entry.get("classification", ""):
                rev_category = ReversibilityCategory.IRREVERSIBLE
                break  # already worst

        # ── R4: worst-case preventability ─────────────────────────────────────
        prev_category = PreventabilityCategory.PREVENTABLE
        for entry in prev_data.values():
            clf = entry.get("classification", "")
            if "Non-Tolerable" in clf or "Non-preventable" in clf:
                prev_category = PreventabilityCategory.NON_PREVENTABLE
                break

        irrev_count = sum(1 for e in rev_data.values()  if "Irreversible" in e.get("classification", ""))
        nonprev_count = sum(1 for e in prev_data.values() if "Non-preventable" in e.get("classification", "") or "Non-Tolerable" in e.get("classification", ""))
        total = mitigation_analysis.get("total_adrs_analyzed", 0)

        output_lines = [
            f"Risk Mitigation Feasibility (Factor 3.4):",
            f"  • Total ADRs analyzed: {total}",
            f"  • Irreversible ADRs: {irrev_count}",
            f"  • Non-preventable ADRs: {nonprev_count}",
            f"  • R4 (Preventability): {prev_category.value}",
            f"  • R5 (Reversibility): {rev_category.value}",
        ]

        return cls(
            name=COMPONENT_NAME,
            category=prev_category,
            reversibility_category=rev_category,
            raw=mitigation_analysis,
            metadata={
                "preventability_category":  prev_category.value,
                "reversibility_category":   rev_category.value,
                "irreversible_count":        irrev_count,
                "non_preventable_count":     nonprev_count,
                "total_adrs_analyzed":       total,
                "output":                    "\n".join(output_lines),
            },
        )
