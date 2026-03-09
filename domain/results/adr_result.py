from dataclasses import dataclass, field
from typing import Any, Dict, List
from core.results.component_results import ComponentResult
from domain.enums import ADRSeverityCategory, InteractionCategory

COMPONENT_NAME = "ADRAnalysis"


@dataclass
class ADRResult(ComponentResult):
    """
    Stores the outcome of the ADR analysis component (Factor 3.2 + 3.3).

    category        → ADRSeverityCategory used by ADRSeverityRule (R3)
    interaction_category → InteractionCategory used by InteractionRule (R2)
    raw             → full ADRAnalyzer.analyze() dict for downstream consumers
                      (RMMComponent and RiskMitigationComponent read from here)
    """
    interaction_category: InteractionCategory = InteractionCategory.NONE
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(cls, adr_analysis: Dict[str, Any]) -> "ADRResult":
        """
        Derives scoring categories from the raw ADRAnalyzer result dict.

        R3 (ADR Severity) logic:
          LT ADRs with risk factors    → LT_WITH_RISK_FACTORS
          LT ADRs without risk factors → LT_NO_RISK_FACTORS
          Serious with risk factors    → SERIOUS_WITH_RISK
          Serious without risk factors → SERIOUS_NO_RISK
          No serious ADRs found        → NO_SERIOUS_ADRS

        R2 (Interaction) logic — worst-case across all medicines:
          contraindicated  → CONTRAINDICATED
          life-threatening → LIFE_THREATENING
          serious          → SERIOUS
          non-serious      → NON_SERIOUS
          (none)           → NONE
        """
        # ── R3: ADR severity category ─────────────────────────────────────────
        lt_with    = sum(len(d.get("with_risk_factors", []))    for d in adr_analysis.get("factor_3_2", {}).get("LT_ADRs", {}).values())
        lt_without = sum(len(d.get("without_risk_factors", [])) for d in adr_analysis.get("factor_3_2", {}).get("LT_ADRs", {}).values())
        ser_with   = sum(len(d.get("with_risk_factors", []))    for d in adr_analysis.get("factor_3_2", {}).get("Serious_ADRs", {}).values())
        ser_without = sum(len(d.get("without_risk_factors", [])) for d in adr_analysis.get("factor_3_2", {}).get("Serious_ADRs", {}).values())

        if lt_with > 0:
            adr_category = ADRSeverityCategory.LT_WITH_RISK_FACTORS
        elif lt_without > 0:
            adr_category = ADRSeverityCategory.LT_NO_RISK_FACTORS
        elif ser_with > 0:
            adr_category = ADRSeverityCategory.SERIOUS_WITH_RISK
        elif ser_without > 0:
            adr_category = ADRSeverityCategory.SERIOUS_NO_RISK
        else:
            adr_category = ADRSeverityCategory.NO_SERIOUS_ADRS

        # ── R2: Interaction severity category — worst case ────────────────────
        int_priority = [
            InteractionCategory.CONTRAINDICATED,
            InteractionCategory.LIFE_THREATENING,
            InteractionCategory.SERIOUS,
            InteractionCategory.NON_SERIOUS,
            InteractionCategory.NONE,
        ]
        interactions_all = adr_analysis.get("factor_3_3", {}).get("interactions", {})
        worst_interaction = InteractionCategory.NONE
        for med_data in interactions_all.values():
            if med_data.get("contraindicated"):
                worst_interaction = InteractionCategory.CONTRAINDICATED
                break
            if med_data.get("lt_interactions"):
                worst_interaction = InteractionCategory.LIFE_THREATENING
            elif med_data.get("serious_interactions") and worst_interaction not in (
                InteractionCategory.CONTRAINDICATED, InteractionCategory.LIFE_THREATENING
            ):
                worst_interaction = InteractionCategory.SERIOUS
            elif med_data.get("non_serious_interactions") and worst_interaction == InteractionCategory.NONE:
                worst_interaction = InteractionCategory.NON_SERIOUS

        # ── Metadata for output/report ────────────────────────────────────────
        lt_total  = lt_with + lt_without
        ser_total = ser_with + ser_without
        output_lines = [f"ADR Analysis (Factor 3.2 & 3.3)"]
        if lt_total:
            output_lines.append(f"  • Life-threatening ADRs found: {lt_total} ({lt_with} with patient risk factors)")
        if ser_total:
            output_lines.append(f"  • Serious ADRs found: {ser_total} ({ser_with} with patient risk factors)")
        int_count = sum(
            len(d.get("contraindicated", [])) + len(d.get("lt_interactions", [])) +
            len(d.get("serious_interactions", [])) + len(d.get("non_serious_interactions", []))
            for d in interactions_all.values()
        )
        if int_count:
            output_lines.append(f"  • Drug interactions found: {int_count} (worst: {worst_interaction.value})")
        if not lt_total and not ser_total and not int_count:
            output_lines.append("  • No significant ADRs or interactions detected")

        return cls(
            name=COMPONENT_NAME,
            category=adr_category,
            interaction_category=worst_interaction,
            raw=adr_analysis,
            metadata={
                "adr_severity_category":   adr_category.value,
                "interaction_category":    worst_interaction.value,
                "lt_with_risk_factors":    lt_with,
                "lt_without_risk_factors": lt_without,
                "serious_with_risk":       ser_with,
                "serious_without_risk":    ser_without,
                "interaction_count":       int_count,
                "output":                  "\n".join(output_lines),
            },
        )
