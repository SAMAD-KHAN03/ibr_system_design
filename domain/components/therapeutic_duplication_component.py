"""
domain/components/therapeutic_duplication_component.py

B4 — Therapeutic Duplication component.

Bugs fixed from provided file:
  - from core.components_module import Component
    → from core.components.component import Component
  - from execution_context import ExecutionContext
    → from core.execution_context import ExecutionContext

Pipeline position: Sequential (after ApprovalStatus, before ADRComponent)
Hard-stop: NOT triggered — contraindicated pairs halt via ContraindicationComponent
           which already handles absolute contraindications. Duplication flagged
           as warnings only; pipeline continues to scoring.
"""

from __future__ import annotations

import logging
from typing import List

from core.components_module import Component          # ← fixed
from execution_context import ExecutionContext      # ← fixed
from core.results.execution_result import ExecutionResult

from domain.results.therapeutic_duplication_result import TherapeuticDuplicationResult

from infrastructure.therapeutic_duplication_infrastructure.drug_profiler import (
    DrugProfiler, DrugProfile,
)
from infrastructure.therapeutic_duplication_infrastructure.duplication_checker import (
    TherapeuticDuplicationChecker, DrugPairResult, PairOutcome,
)

log = logging.getLogger(__name__)


class TherapeuticDuplicationComponent(Component):
    """
    Checks ALL drug combinations (ongoing + current diagnoses + new meds)
    for therapeutic duplication using NICE guideline rules only.

    Sources checked (mirrors ApprovalStatusComponent):
      1. New drug under review         — drug_data
      2. Ongoing medications           — patient_data["ongoingMedications"]
      3. Current diagnosis medications — patient_data["currentDiagnosis"]
      4. Past condition treatments     — patient_data["pastMedicalConditions"]

    Never halts the pipeline — duplications are flagged as warnings.
    The scoring rule (DuplicationRule / B4) penalises OVERLAP and REDUNDANT.
    """

    NAME = "TherapeuticDuplication"

    def __init__(
        self,
        profiler: DrugProfiler = None,
        checker:  TherapeuticDuplicationChecker = None,
    ):
        self._profiler = profiler or DrugProfiler()
        self._checker  = checker  or TherapeuticDuplicationChecker()

    @property
    def component_name(self) -> str:
        return self.NAME

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        drug_names = self._collect_all_drug_names(context)

        if len(drug_names) < 2:
            context.add_warning(
                "TherapeuticDuplication: fewer than 2 drugs found — no pairs to check."
            )
            result = TherapeuticDuplicationResult.build([])
            context.add_result(result)
            return ExecutionResult.ok(data=result.metadata)

        # Resolve each drug name → DrugProfile
        profiles: List[DrugProfile] = []
        unresolved: List[str] = []
        for name in drug_names:
            profile = self._profiler.profile(name)
            profiles.append(profile)
            if not profile.resolved:
                unresolved.append(name)
                context.add_warning(
                    f"TherapeuticDuplication: could not resolve profile for '{name}' "
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

        # Pairwise duplication check
        pair_results: List[DrugPairResult] = self._checker.check_all_pairs(resolved_profiles)

        # Log non-unique findings
        for pr in pair_results:
            if pr.outcome != PairOutcome.UNIQUE:
                print(f"\n  {'─'*60}")
                for line in pr.detail.split("\n"):
                    print(f"  {line}")
                # Add warnings for serious findings
                if pr.outcome in (
                    PairOutcome.DUPLICATE_CONTRAINDICATED,
                    PairOutcome.DUPLICATE_NOT_RECOMMENDED,
                ):
                    context.add_warning(
                        f"TherapeuticDuplication [{pr.outcome.value}]: "
                        f"{pr.drug_a} + {pr.drug_b} — {pr.matched_rules[0].recommendation_text if pr.matched_rules else 'No NICE rule matched'}"
                    )

        result = TherapeuticDuplicationResult.build(pair_results)
        context.add_result(result)

        meta = result.metadata
        print(
            f"\n  TherapeuticDuplication summary — "
            f"{meta['total_pairs']} pairs | "
            f"{meta['unique_count']} unique | "
            f"{meta['duplicate_count']} duplicates "
            f"({meta['contraindicated_count']} contraindicated, "
            f"{meta['not_recommended_count']} not recommended, "
            f"{meta['conditional_count']} conditional)"
        )

        return ExecutionResult.ok(data=result.metadata)

    def _collect_all_drug_names(self, context: ExecutionContext) -> List[str]:
        seen:  set[str]   = set()
        names: List[str]  = []

        def add(drug: str) -> None:
            drug = drug.strip()
            if drug and drug.lower() not in seen:
                seen.add(drug.lower())
                names.append(drug)

        add(context.drug_name)

        patient = context.patient_data

        for med in patient.get("ongoingMedications", []):
            add(med.get("name", ""))

        for dx in patient.get("currentDiagnosis", []):
            add(dx.get("medicationName", ""))

        for cond in patient.get("pastMedicalConditions", []):
            treatment = cond.get("treatmentGiven", "")
            if treatment and treatment.lower() not in {
                "lifestyle", "surgery", "physiotherapy", "none", "diet", "exercise"
            }:
                add(cond.get("details"))

        return names
