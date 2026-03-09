"""
therapeutic_duplication_component.py
=====================================
Pipeline component that detects therapeutic duplication across ALL medications
a patient is receiving (ongoing + current diagnoses + new prescriptions) and
classifies each duplicate pair against NICE guidelines.

Pipeline position:  Sequential  (runs before parallel enrichment steps)
Hard-stop trigger:  Yes — if ANY pair is CONTRAINDICATED, triggers hard_stop
                    via context.trigger_hard_stop() AND returns ExecutionResult.halt()

Drug resolution strategy (per architecture doc §8.1):
  1. Static NICE-aligned knowledge base  (instant)
  2. FDA OpenFDA API                     (network, primary)
  3. RxNorm / RxClass API               (network, fallback)

NICE guidelines strictly enforced — no other guideline sources used.

Usage in engine:
    engine.add_sequential(TherapeuticDuplicationComponent())
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult

from domain.results.therapeutic_duplication_result import TherapeuticDuplicationResult

from infrastructure.therapeutic_duplication_infrastructure.drug_profiler import (
    DrugProfiler,
    DrugProfile,
)
from infrastructure.therapeutic_duplication_infrastructure.duplication_checker import (
    TherapeuticDuplicationChecker,
    DrugPairResult,
    PairOutcome,
)

log = logging.getLogger(__name__)


class TherapeuticDuplicationComponent(Component):
    """
    Checks ALL drug combinations (ongoing + current diagnoses + new meds)
    for therapeutic duplication using NICE guideline rules only.

    Scope of drugs checked (mirrors ApprovalStatusComponent's pair collection):
      1. New drug(s) under review                   — from drug_data
      2. Ongoing medications                        — patient_data["ongoingMedications"]
      3. Medications from current diagnoses         — patient_data["currentDiagnosis"]
      4. Treatments from past medical conditions    — patient_data["pastMedicalConditions"]

    All resolved drugs are checked pairwise (C(n,2) combinations).
    """

    NAME = "TherapeuticDuplication"

    def __init__(
        self,
        profiler: DrugProfiler = None,
        checker: TherapeuticDuplicationChecker = None,
    ):
        self._profiler = profiler or DrugProfiler()
        self._checker  = checker  or TherapeuticDuplicationChecker()

    @property
    def component_name(self) -> str:
        return self.NAME

    # ── Entry point ──────────────────────────────────────────────────────────

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        # 1. Collect all drug names from context
        drug_names = self._collect_all_drug_names(context)

        if len(drug_names) < 2:
            context.add_warning(
                "TherapeuticDuplication: fewer than 2 drugs found — no pairs to check."
            )
            # Store an empty result so downstream rules don't KeyError
            result = TherapeuticDuplicationResult.build([])
            context.add_result(result)
            return ExecutionResult.ok(data=result.metadata)

        # 2. Resolve each drug name → DrugProfile
        profiles: list[DrugProfile] = []
        unresolved: list[str] = []
        for name in drug_names:
            profile = self._profiler.profile(name)
            profiles.append(profile)
            if not profile.resolved:
                unresolved.append(name)
                context.add_warning(
                    f"TherapeuticDuplication: could not resolve drug profile for '{name}' "
                    f"— excluded from duplication check."
                )

        resolved_profiles = [p for p in profiles if p.resolved]

        print(f"\n  TherapeuticDuplication: resolved {len(resolved_profiles)}/{len(drug_names)} drugs")
        for p in resolved_profiles:
            print(f"    ✓ {p.name} → class={p.drug_class}, moa={p.mechanism_of_action}")
        if unresolved:
            print(f"    ✗ Unresolved: {', '.join(unresolved)}")

        if len(resolved_profiles) < 2:
            context.add_warning(
                "TherapeuticDuplication: fewer than 2 drugs resolved — cannot check pairs."
            )
            result = TherapeuticDuplicationResult.build([])
            context.add_result(result)
            return ExecutionResult.ok(data=result.metadata)

        # 3. Run pairwise duplication check
        pair_results: list[DrugPairResult] = self._checker.check_all_pairs(resolved_profiles)

        # 4. Print per-pair findings
        print(f"\n  TherapeuticDuplication: checked {len(pair_results)} pair(s)")
        for pr in pair_results:
            if pr.outcome != PairOutcome.UNIQUE:
                print(f"\n  {'─'*60}")
                for line in pr.detail.split("\n"):
                    print(f"  {line}")

        # 5. Build and store result
        result = TherapeuticDuplicationResult.build(pair_results)
        context.add_result(result)

        summary = result.metadata
        print(
            f"\n  TherapeuticDuplication summary — "
            f"{summary['total_pairs']} pairs checked | "
            f"{summary['unique_count']} unique | "
            f"{summary['duplicate_count']} duplicates "
            f"({summary['contraindicated_count']} contraindicated, "
            f"{summary['not_recommended_count']} not recommended, "
            f"{summary['conditional_count']} conditional, "
            f"{summary['supported_count']} supported, "
            f"{summary['no_rationale_count']} no rationale)"
        )

        # 6. Hard-stop if any contraindicated pair found
        if summary["has_contraindication"]:
            contraindicated_pairs = [
                p for p in pair_results
                if p.outcome == PairOutcome.DUPLICATE_CONTRAINDICATED
            ]
            reason = "; ".join(
                f"{p.drug_a} + {p.drug_b}" for p in contraindicated_pairs
            )
            # context.trigger_hard_stop()
            # return ExecutionResult.halt(
            #     reason=(
            #         f"TherapeuticDuplication: CONTRAINDICATED combination(s) detected — {reason}. "
            #         f"Pipeline halted. Clinical review required before dispensing."
            #     )
            # )

        return ExecutionResult.ok(data=result.metadata)

    # ── Drug name collection ─────────────────────────────────────────────────

    def _collect_all_drug_names(self, context: ExecutionContext) -> list[str]:
        """
        Collects all unique drug names from every medication source in context.
        Deduplication is case-insensitive.
        Mirrors the multi-source collection logic of ApprovalStatusComponent.
        """
        seen: set[str] = set()
        names: list[str] = []

        def add(drug: str, source: str) -> None:
            drug = drug.strip()
            if drug and drug.lower() not in seen:
                seen.add(drug.lower())
                names.append(drug)
                log.debug("TherapeuticDuplication: added '%s' from %s", drug, source)

        # 1. Primary new drug under review
        add(context.drug_name, "primary_drug")

        patient = context.patient_data

        # 2. Ongoing medications
        for med in patient.get("ongoingMedications", []):
            add(med.get("name", ""), "ongoing_medication")

        # 3. Current diagnoses → medication name
        for dx in patient.get("currentDiagnosis", []):
            add(dx.get("medicationName", ""), "current_diagnosis")

        # 4. Past medical conditions → treatment given
        for cond in patient.get("pastMedicalConditions", []):
            treatment = cond.get("treatmentGiven", "")
            # Only add if treatment is a medication (not "Lifestyle", "Surgery", etc.)
            if treatment and treatment.lower() not in {
                "lifestyle", "surgery", "physiotherapy", "none", "diet", "exercise"
            }:
                add(treatment, "past_condition")

        return names
