"""
duplication_checker.py
======================
Stage 2 + 3 of the therapeutic duplication pipeline:
  - Generates all pairwise combinations of DrugProfile objects
  - Detects overlap on 3 axes (class, MOA, shared indication)
  - Looks up NICE combination rules
  - Classifies each pair using the deterministic priority hierarchy

This module is pure logic — no I/O, no network calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from typing import Optional

from infrastructure.therapeutic_duplication_infrastructure.drug_profiler import DrugProfile
from infrastructure.therapeutic_duplication_infrastructure.nice_guidelines_db import CombinationRule, find_combination_rules


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DuplicateReason(str, Enum):
    SAME_CLASS      = "SAME_CLASS"
    SAME_MOA        = "SAME_MOA"
    SAME_INDICATION = "SAME_INDICATION"
    CLASS_AND_MOA   = "CLASS_AND_MOA"
    ALL_THREE       = "ALL_THREE"


class PairOutcome(str, Enum):
    UNIQUE                    = "UNIQUE"
    COMBINATION_SUPPORTED     = "COMBINATION_SUPPORTED"
    CONDITIONALLY_SUPPORTED   = "CONDITIONALLY_SUPPORTED"
    DUPLICATE_NO_RATIONALE    = "DUPLICATE_NO_RATIONALE"
    DUPLICATE_NOT_RECOMMENDED = "DUPLICATE_NOT_RECOMMENDED"
    DUPLICATE_CONTRAINDICATED = "DUPLICATE_CONTRAINDICATED"


# Severity order (higher index = more severe)
_OUTCOME_SEVERITY: dict[str, int] = {
    "SUPPORTED":        0,
    "CONDITIONAL":      1,
    "NOT_RECOMMENDED":  2,
    "CONTRAINDICATED":  3,
}

_RECOMMENDATION_TO_OUTCOME: dict[str, PairOutcome] = {
    "SUPPORTED":        PairOutcome.COMBINATION_SUPPORTED,
    "CONDITIONAL":      PairOutcome.CONDITIONALLY_SUPPORTED,
    "NOT_RECOMMENDED":  PairOutcome.DUPLICATE_NOT_RECOMMENDED,
    "CONTRAINDICATED":  PairOutcome.DUPLICATE_CONTRAINDICATED,
}


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

@dataclass
class DrugPairResult:
    drug_a: str
    drug_b: str
    outcome: PairOutcome
    duplicate_reason: Optional[DuplicateReason]
    shared_indications: set[str]
    matched_rules: list[CombinationRule]
    detail: str             # Human-readable summary for the report


# ---------------------------------------------------------------------------
# Core checker
# ---------------------------------------------------------------------------

class TherapeuticDuplicationChecker:
    """
    Analyses all pairwise drug combinations and returns DrugPairResult objects.
    """

    def check_all_pairs(
        self, profiles: list[DrugProfile]
    ) -> list[DrugPairResult]:
        results: list[DrugPairResult] = []
        for pa, pb in combinations(profiles, 2):
            results.append(self._check_pair(pa, pb))
        return results

    # ── Pair pipeline ────────────────────────────────────────────────────────

    def _check_pair(self, pa: DrugProfile, pb: DrugProfile) -> DrugPairResult:
        # Step 1: detect duplication
        reason, shared = self._detect_duplication(pa, pb)

        if reason is None:
            # No overlap on any axis → UNIQUE
            return DrugPairResult(
                drug_a=pa.name, drug_b=pb.name,
                outcome=PairOutcome.UNIQUE,
                duplicate_reason=None,
                shared_indications=set(),
                matched_rules=[],
                detail=f"No shared class, MOA, or indication between {pa.name} and {pb.name}.",
            )

        # Step 2: NICE lookup
        rules = find_combination_rules(
            class_a=pa.drug_class, name_a=pa.name,
            class_b=pb.drug_class, name_b=pb.name,
            shared_indications=shared,
        )

        # Step 3: classify
        outcome, detail = self._classify_outcome(pa, pb, reason, shared, rules)

        return DrugPairResult(
            drug_a=pa.name, drug_b=pb.name,
            outcome=outcome,
            duplicate_reason=reason,
            shared_indications=shared,
            matched_rules=rules,
            detail=detail,
        )

    # ── Axis detection ───────────────────────────────────────────────────────

    def _detect_duplication(
        self, pa: DrugProfile, pb: DrugProfile
    ) -> tuple[Optional[DuplicateReason], set[str]]:
        """
        Returns (DuplicateReason | None, shared_indications).
        UNKNOWN class/MOA is never flagged as a duplicate to avoid false positives.
        """
        same_class = (
            pa.drug_class == pb.drug_class
            and pa.drug_class != "UNKNOWN"
        )
        same_moa = (
            pa.mechanism_of_action == pb.mechanism_of_action
            and pa.mechanism_of_action != "UNKNOWN"
        )
        shared_ind = pa.indications & pb.indications

        if same_class and same_moa and shared_ind:
            return DuplicateReason.ALL_THREE,   shared_ind
        if same_class and same_moa:
            return DuplicateReason.CLASS_AND_MOA, shared_ind
        if same_class:
            return DuplicateReason.SAME_CLASS,  shared_ind
        if same_moa:
            return DuplicateReason.SAME_MOA,    shared_ind
        if shared_ind:
            return DuplicateReason.SAME_INDICATION, shared_ind
        return None, set()

    # ── Outcome classification ───────────────────────────────────────────────

    def _classify_outcome(
        self,
        pa: DrugProfile,
        pb: DrugProfile,
        reason: DuplicateReason,
        shared: set[str],
        rules: list[CombinationRule],
    ) -> tuple[PairOutcome, str]:
        """
        Deterministic priority hierarchy (architecture doc §4.4):
          CONTRAINDICATED > NOT_RECOMMENDED > CONDITIONAL > SUPPORTED > NO_RATIONALE
        """
        if not rules:
            detail = (
                f"⚠ THERAPEUTIC DUPLICATION — No NICE Rationale\n"
                f"  Pair: {pa.name} + {pb.name}\n"
                f"  Overlap: {reason.value}\n"
                f"  Shared indication(s): {', '.join(sorted(shared)) or 'None detected'}\n"
                f"  No matching NICE guideline rule found for this combination.\n"
                f"  Clinical review required before dispensing."
            )
            return PairOutcome.DUPLICATE_NO_RATIONALE, detail

        # Sort by severity — take highest
        rules_sorted = sorted(
            rules,
            key=lambda r: _OUTCOME_SEVERITY.get(r.recommendation, -1),
            reverse=True,
        )
        top_rule = rules_sorted[0]
        outcome = _RECOMMENDATION_TO_OUTCOME.get(
            top_rule.recommendation, PairOutcome.DUPLICATE_NO_RATIONALE
        )

        icon = {
            PairOutcome.COMBINATION_SUPPORTED:   "✅ SUPPORTED",
            PairOutcome.CONDITIONALLY_SUPPORTED:  "⚠️ CONDITIONAL",
            PairOutcome.DUPLICATE_NOT_RECOMMENDED:"🔴 NOT RECOMMENDED",
            PairOutcome.DUPLICATE_CONTRAINDICATED:"🚫 CONTRAINDICATED",
        }.get(outcome, "⚠ DUPLICATE")

        conditions_text = ""
        if top_rule.conditions:
            conditions_text = "\n  Conditions: " + "; ".join(top_rule.conditions)

        detail = (
            f"{icon}\n"
            f"  Pair: {pa.name} + {pb.name}\n"
            f"  Overlap: {reason.value} | Shared: {', '.join(sorted(shared)) or 'N/A'}\n"
            f"  NICE {top_rule.guideline_code} §{top_rule.section_ref} [{top_rule.strength}]\n"
            f"  Recommendation: {top_rule.recommendation_text}\n"
            f"  Rationale: {top_rule.rationale}"
            f"{conditions_text}\n"
            f"  Reference: {top_rule.url}"
        )

        return outcome, detail
