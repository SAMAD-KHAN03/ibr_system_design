from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.results.pubmed_result import PubMedResult
from infrastructure.pubmed_infrastructure.pubmed_searcher import PubMedSearcher

from typing import List, Tuple

class PubMedComponent(Component):

    NAME = "PubMed"

    def __init__(self, email: str = None, searcher: PubMedSearcher = None):
        self._searcher = searcher or PubMedSearcher(email=email)

    @property
    def component_name(self) -> str:
        return self.NAME

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        
        # print(f'drug received at pubmed{drug}')
        # print(f'the patient context is {context.patient_data}')
        # if not drug or not condition:
        #     context.add_warning("PubMed: drug name or condition missing — skipped.")
        #     return ExecutionResult.fail("Missing drug or condition")

        pairs = self._collect_drug_condition_pairs(context)
        # print(f'pairs are {pairs}')
        if not pairs:
            context.add_warning("PubMed: no drug/condition pairs found — skipped.")
            return ExecutionResult.fail("No drug or condition data available")
        for drug, condition, source in pairs:
            rct_count, conclusions = self._searcher.search(drug, condition)
            result = PubMedResult.build(drug, condition, rct_count, conclusions)
            context.add_result(result)
            print(f"  ✓ PubMed: {rct_count} RCTs found for '{drug}' in '{condition}'.")
        return ExecutionResult.ok(data=result.metadata)
    def _collect_drug_condition_pairs(
        self, context: ExecutionContext
    ) -> List[Tuple[str, str, str]]:
        seen: set[tuple[str, str]] = set()
        pairs: List[Tuple[str, str, str]] = []

        def add(drug: str, condition: str, source: str) -> None:
            drug, condition = drug.strip(), condition.strip()
            if drug and condition and (drug.lower(), condition.lower()) not in seen:
                seen.add((drug.lower(), condition.lower()))
                pairs.append((drug, condition, source))

        add(context.drug_name, context.condition, "primary")

        patient = context.patient_data

        for med in patient.get("ongoingMedications", []):
            add(med.get("name", ""), med.get("indication") or context.condition, "ongoing_medication")

        for dx in patient.get("currentDiagnosis", []):
            if dx.get("medicationName"):
                add(dx.get("medicationName", ""), dx.get("name", ""), "current_diagnosis")

        for cond in patient.get("pastMedicalConditions", []):
            if cond.get("treatmentGiven"):
                add(cond.get("treatmentGiven", ""), cond.get("conditionName", ""), "past_condition")

        return pairs
