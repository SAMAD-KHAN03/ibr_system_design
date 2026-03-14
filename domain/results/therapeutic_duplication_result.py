"""
domain/results/therapeutic_duplication_result.py

Domain result stored in ExecutionContext by TherapeuticDuplicationComponent.

Bug fixed from provided file:
  - Import: core.results.component_results → core.results.component_result
  - .category was never set — DuplicationRule reads result.category as
    DuplicationCategory enum. Fixed by deriving worst-case category from
    PairOutcome using this mapping:
      UNIQUE / COMBINATION_SUPPORTED   → DuplicationCategory.UNIQUE     (3×80=240)
      CONDITIONALLY_SUPPORTED          → DuplicationCategory.OVERLAP    (2×60=120)
      DUPLICATE_NO_RATIONALE           → DuplicationCategory.OVERLAP    (2×60=120)
      DUPLICATE_NOT_RECOMMENDED        → DuplicationCategory.OVERLAP    (2×60=120)
      DUPLICATE_CONTRAINDICATED        → DuplicationCategory.REDUNDANT  (0×20=0)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.results.component_results import ComponentResult          # ← fixed import
from domain.enums import DuplicationCategory
from infrastructure.therapeutic_duplication_infrastructure.duplication_checker import (
    DrugPairResult,
    PairOutcome,
)

COMPONENT_NAME = "TherapeuticDuplication"

# Maps PairOutcome → DuplicationCategory (worst-case used for scoring)
_OUTCOME_TO_CATEGORY: dict[PairOutcome, DuplicationCategory] = {
    PairOutcome.UNIQUE:                    DuplicationCategory.UNIQUE,
    PairOutcome.COMBINATION_SUPPORTED:     DuplicationCategory.UNIQUE,
    PairOutcome.CONDITIONALLY_SUPPORTED:   DuplicationCategory.OVERLAP,
    PairOutcome.DUPLICATE_NO_RATIONALE:    DuplicationCategory.OVERLAP,
    PairOutcome.DUPLICATE_NOT_RECOMMENDED: DuplicationCategory.OVERLAP,
    PairOutcome.DUPLICATE_CONTRAINDICATED: DuplicationCategory.REDUNDANT,
}

# Severity rank for worst-case selection (higher = worse)
_CATEGORY_RANK: dict[DuplicationCategory, int] = {
    DuplicationCategory.UNIQUE:    0,
    DuplicationCategory.OVERLAP:   1,
    DuplicationCategory.REDUNDANT: 2,
}


@dataclass
class TherapeuticDuplicationResult(ComponentResult):
    """
    Stored under context.component_results["TherapeuticDuplication"].
    category → DuplicationCategory used by DuplicationRule (B4).
    """

    @classmethod
    def build(cls, pair_results: list[DrugPairResult]) -> "TherapeuticDuplicationResult":
        counts = {o: 0 for o in PairOutcome}
        for pr in pair_results:
            counts[pr.outcome] += 1

        total        = len(pair_results)
        unique_count = counts[PairOutcome.UNIQUE]
        dup_count    = total - unique_count

        # ── Derive worst-case DuplicationCategory for scoring rule ────────────
        worst_category = DuplicationCategory.UNIQUE
        for pr in pair_results:
            cat = _OUTCOME_TO_CATEGORY.get(pr.outcome, DuplicationCategory.UNIQUE)
            if _CATEGORY_RANK[cat] > _CATEGORY_RANK[worst_category]:
                worst_category = cat

        serialised_pairs = [
            {
                "drug_a":             pr.drug_a,
                "drug_b":             pr.drug_b,
                "outcome":            pr.outcome.value,
                "duplicate_reason":   pr.duplicate_reason.value if pr.duplicate_reason else None,
                "shared_indications": sorted(pr.shared_indications),
                "matched_rules": [
                    {
                        "guideline_code":      r.guideline_code,
                        "section_ref":         r.section_ref,
                        "recommendation":      r.recommendation,
                        "recommendation_text": r.recommendation_text,
                        "url":                 r.url,
                        "rationale":           r.rationale,
                        "conditions":          r.conditions,
                    }
                    for r in pr.matched_rules
                ],
                "detail": pr.detail,
            }
            for pr in pair_results
        ]

        summary_lines = [
            pr.detail for pr in pair_results
            if pr.outcome != PairOutcome.UNIQUE
        ]

        output = (
            f"Therapeutic Duplication (B4):\n"
            f"  • {total} pair(s) checked | {unique_count} unique | {dup_count} duplicate(s)\n"
            f"  • Worst-case category: {worst_category.value}\n"
            f"  • Contraindicated pairs: {counts[PairOutcome.DUPLICATE_CONTRAINDICATED]}\n"
            f"  • Not recommended pairs: {counts[PairOutcome.DUPLICATE_NOT_RECOMMENDED]}\n"
            f"  • Conditional pairs: {counts[PairOutcome.CONDITIONALLY_SUPPORTED]}\n"
            f"  • Supported combinations: {counts[PairOutcome.COMBINATION_SUPPORTED]}"
        )

        return cls(
            name=COMPONENT_NAME,
            category=worst_category,            # ← DuplicationRule reads this
            metadata={
                "duplication_category":     worst_category.value,
                "total_pairs":              total,
                "unique_count":             unique_count,
                "duplicate_count":          dup_count,
                "supported_count":          counts[PairOutcome.COMBINATION_SUPPORTED],
                "conditional_count":        counts[PairOutcome.CONDITIONALLY_SUPPORTED],
                "not_recommended_count":    counts[PairOutcome.DUPLICATE_NOT_RECOMMENDED],
                "contraindicated_count":    counts[PairOutcome.DUPLICATE_CONTRAINDICATED],
                "no_rationale_count":       counts[PairOutcome.DUPLICATE_NO_RATIONALE],
                "has_contraindication":     counts[PairOutcome.DUPLICATE_CONTRAINDICATED] > 0,
                "pairs":                    serialised_pairs,
                "summary_lines":            summary_lines,
                "output":                   output,
            },
        )
