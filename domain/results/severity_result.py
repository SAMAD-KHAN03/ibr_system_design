from dataclasses import dataclass, field
from typing import Any, Dict
from core.results.component_results import ComponentResult
from domain.enums import SeverityCategory

COMPONENT_NAME = "DiseaseSeverity"


# Maps the Gemini classification string → SeverityCategory
_CATEGORY_MAP = {
    "acute, life-threatening":      SeverityCategory.ACUTE_LIFE_THREATENING,
    "acute life-threatening":       SeverityCategory.ACUTE_LIFE_THREATENING,
    "acute, non-life-threatening":  SeverityCategory.ACUTE_NON_LIFE_THREATENING,
    "acute non-life-threatening":   SeverityCategory.ACUTE_NON_LIFE_THREATENING,
    "chronic, life-threatening":    SeverityCategory.CHRONIC_LIFE_THREATENING,
    "chronic life-threatening":     SeverityCategory.CHRONIC_LIFE_THREATENING,
    "chronic, non-life-threatening":SeverityCategory.CHRONIC_NON_LIFE_THREATENING,
    "chronic non-life-threatening": SeverityCategory.CHRONIC_NON_LIFE_THREATENING,
    "quality of life":              SeverityCategory.QUALITY_OF_LIFE,
    "signs/symptoms":               SeverityCategory.SIGNS_SYMPTOMS,
}


def _map_gemini_category(gemini_str: str) -> SeverityCategory:
    """Converts Gemini's free-text category string to SeverityCategory enum."""
    lowered = gemini_str.lower().strip()
    for key, cat in _CATEGORY_MAP.items():
        if key in lowered:
            return cat
    # fallback: chronic non-LT is the conservative default
    return SeverityCategory.CHRONIC_NON_LIFE_THREATENING


@dataclass
class SeverityResult(ComponentResult):
    """
    Stores Factor 2.6 disease severity analysis.
    category → SeverityCategory used by SeverityRule (B6).

    Uses worst-case (highest-scoring) category across all diagnosed conditions,
    consistent with how ADR results use worst-case interaction severity.
    """
    raw: Dict[str, Any] = field(default_factory=dict)

    # Scoring order — higher index = higher severity weight
    _SEVERITY_RANK = [
        SeverityCategory.SIGNS_SYMPTOMS,
        SeverityCategory.QUALITY_OF_LIFE,
        SeverityCategory.CHRONIC_NON_LIFE_THREATENING,
        SeverityCategory.CHRONIC_LIFE_THREATENING,
        SeverityCategory.ACUTE_NON_LIFE_THREATENING,
        SeverityCategory.ACUTE_LIFE_THREATENING,
    ]

    @classmethod
    def build(cls, severity_analysis: Dict[str, Any]) -> "SeverityResult":
        """
        Derives worst-case (highest severity) SeverityCategory from all diagnoses.
        """
        consequences = severity_analysis.get("factor_2_6_consequences_of_non_treatment", {})
        diagnoses    = severity_analysis.get("diagnoses_analyzed", [])

        worst_category = SeverityCategory.CHRONIC_NON_LIFE_THREATENING  # safe default
        rank_map = {cat: i for i, cat in enumerate(cls._SEVERITY_RANK)}

        per_disease = []
        for disease, data in consequences.items():
            classifications = data.get("classifications", [])
            for clf in classifications:
                cat_str  = clf.get("category", "")
                category = _map_gemini_category(cat_str)
                per_disease.append({"disease": disease, "category": category.value, "raw_category": cat_str})
                if rank_map.get(category, 0) > rank_map.get(worst_category, 0):
                    worst_category = category

        output_lines = [
            f"Disease Severity (Factor 2.6):",
            f"  • Diagnoses analyzed: {', '.join(diagnoses) if diagnoses else 'None'}",
            f"  • Worst-case severity: {worst_category.value}",
        ]
        for d in per_disease:
            output_lines.append(f"  • {d['disease']}: {d['raw_category']}")

        return cls(
            name=COMPONENT_NAME,
            category=worst_category,
            raw=severity_analysis,
            metadata={
                "severity_category":       worst_category.value,
                "diagnoses_analyzed":       diagnoses,
                "per_disease_categories":   per_disease,
                "output":                   "\n".join(output_lines),
            },
        )
