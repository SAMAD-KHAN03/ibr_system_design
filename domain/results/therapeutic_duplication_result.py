"""
therapeutic_duplication_result.py
==================================
Domain result stored in ExecutionContext by TherapeuticDuplicationComponent.

Follows the same pattern as ApprovalStatusResult:
  - Inherits from ComponentResult
  - Exposes a .metadata dict consumed by scoring rules
  - Factory classmethod .build(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Matches the project's ComponentResult base (adjust import path as needed)
try:
    from core.results.component_results import ComponentResult
except ImportError:
    # Standalone fallback so the module can be imported/tested independently
    @dataclass
    class ComponentResult:          # type: ignore[no-redef]
        name: str
        metadata: dict = field(default_factory=dict)

from infrastructure.therapeutic_duplication_infrastructure.duplication_checker import (
    DrugPairResult,
    PairOutcome,
)


@dataclass
class TherapeuticDuplicationResult(ComponentResult):
    """
    Stored under context.component_results["TherapeuticDuplication"].

    metadata keys (consumed by scoring rules / report formatters):
      total_pairs          int
      unique_count         int
      duplicate_count      int
      supported_count      int
      conditional_count    int
      not_recommended_count int
      contraindicated_count int
      no_rationale_count   int
      has_contraindication bool   ← hard-stop signal
      pairs                list[dict]  ← serialised DrugPairResult list
      summary_lines        list[str]   ← human-readable per-pair summaries
    """

    @classmethod
    def build(cls, pair_results: list[DrugPairResult]) -> "TherapeuticDuplicationResult":
        counts = {o: 0 for o in PairOutcome}
        for pr in pair_results:
            counts[pr.outcome] += 1

        total        = len(pair_results)
        unique_count = counts[PairOutcome.UNIQUE]
        dup_count    = total - unique_count

        serialised_pairs = [
            {
                "drug_a":            pr.drug_a,
                "drug_b":            pr.drug_b,
                "outcome":           pr.outcome.value,
                "duplicate_reason":  pr.duplicate_reason.value if pr.duplicate_reason else None,
                "shared_indications": sorted(pr.shared_indications),
                "matched_rules": [
                    {
                        "guideline_code": r.guideline_code,
                        "section_ref":    r.section_ref,
                        "recommendation": r.recommendation,
                        "recommendation_text": r.recommendation_text,
                        "url":            r.url,
                        "rationale":      r.rationale,
                        "conditions":     r.conditions,
                    }
                    for r in pr.matched_rules
                ],
                "detail": pr.detail,
            }
            for pr in pair_results
        ]

        summary_lines = [pr.detail for pr in pair_results if pr.outcome != PairOutcome.UNIQUE]

        metadata = {
            "total_pairs":             total,
            "unique_count":            unique_count,
            "duplicate_count":         dup_count,
            "supported_count":         counts[PairOutcome.COMBINATION_SUPPORTED],
            "conditional_count":       counts[PairOutcome.CONDITIONALLY_SUPPORTED],
            "not_recommended_count":   counts[PairOutcome.DUPLICATE_NOT_RECOMMENDED],
            "contraindicated_count":   counts[PairOutcome.DUPLICATE_CONTRAINDICATED],
            "no_rationale_count":      counts[PairOutcome.DUPLICATE_NO_RATIONALE],
            "has_contraindication":    counts[PairOutcome.DUPLICATE_CONTRAINDICATED] > 0,
            "pairs":                   serialised_pairs,
            "summary_lines":           summary_lines,
        }

        return cls(name="TherapeuticDuplication", metadata=metadata)
