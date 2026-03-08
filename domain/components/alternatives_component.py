from typing import List

from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.results.alternatives_result import AlternativesResult, AlternativeEntry
from infrastructure.alternatives_infrastructure.fda_alternatives_finder import FDAAlternativesFinder


class AlternativesComponent(Component):
    """
    1. Finds top-N alternative drugs via FDA API (+ RxNorm fallback for drug class).
    2. Runs a fresh BRAAnalysisEngine pipeline on each alternative so every
       alternative gets its own Contraindication / ApprovalStatus / PubMed scores.
    3. Stores all scored AlternativeEntry objects in AlternativesResult.

    Dependency Inversion: the engine used to score alternatives is injected at
    construction time from main.py — AlternativesComponent never imports
    BRAAnalysisEngine directly, keeping the dependency graph acyclic.
    """

    NAME = "Alternatives"

    def __init__(
        self,
        scoring_engine,           # BRAAnalysisEngine instance injected from main.py
        finder: FDAAlternativesFinder = None,
        top_n: int = 3,
    ):
        self._engine = scoring_engine
        self._finder = finder or FDAAlternativesFinder()
        self._top_n  = top_n

    @property
    def component_name(self) -> str:
        return self.NAME

    # ── Entry point ──────────────────────────────────────────────────────────

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        drug      = context.drug_name
        condition = context.condition

        if not drug or not condition:
            context.add_warning("Alternatives: drug name or condition missing — skipped.")
            return ExecutionResult.fail("Missing drug or condition")

        print(f"\n  [Alternatives] Finding top {self._top_n} alternatives for '{drug}' in '{condition}'")
        raw_alternatives = self._finder.get_top_alternatives(drug, condition, self._top_n)

        if not raw_alternatives:
            context.add_warning(f"Alternatives: no alternatives found for '{drug}' / '{condition}'.")
            context.add_result(AlternativesResult.build([]))
            return ExecutionResult.ok()

        entries: List[AlternativeEntry] = []

        for alt in raw_alternatives:
            entry = self._score_alternative(alt, condition, context.patient_data)
            entries.append(entry)
            print(f"  ✓ [Alternatives] {entry.name} scored: {entry.total_score:.1f}")

        result = AlternativesResult.build(entries)
        context.add_result(result)
        return ExecutionResult.ok(data=result.metadata)

    # ── Per-alternative scoring ──────────────────────────────────────────────

    def _score_alternative(
        self, alt: dict, condition: str, patient_data: dict
    ) -> AlternativeEntry:
        """
        Runs the full BRAAnalysisEngine on one alternative drug.
        Returns an AlternativeEntry with the scored context embedded.
        """
        drug_name = alt.get("Active_Moiety", alt.get("Generic_Name", "Unknown"))

        drug_data = {
            "name":      drug_name,
            "condition": condition,
        }

        try:
            print(f"\n  [Alternatives] ── Scoring alternative: {drug_name} ──")
            alt_context = self._engine.execute(
                patient_data=patient_data,
                drug_data=drug_data,
            )

            score = alt_context.final_score if alt_context else None

            # Collect output strings from each component for the report
            component_outputs = {}
            if alt_context:
                for comp_name, comp_result in alt_context.component_results.items():
                    component_outputs[comp_name] = comp_result.metadata.get("output", "")

        except Exception as exc:
            print(f"  [Alternatives] Pipeline error for '{drug_name}': {exc}")
            score             = None
            component_outputs = {}

        return AlternativeEntry(
            name=drug_name,
            brand_name=alt.get("Brand_Name", "Unknown"),
            generic_name=alt.get("Generic_Name", "Unknown"),
            drug_class=alt.get("Drug_Class", "Unknown"),
            route=alt.get("Route", "Unknown"),
            condition=condition,
            score=score,
            component_outputs=component_outputs,
        )
