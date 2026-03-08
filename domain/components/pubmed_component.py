from typing import List, Tuple

from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.enums import PubMedEvidenceCategory
from domain.results.pubmed_result import PubMedResult, DrugPubMedEntry
from infrastructure.pubmed_infrastructure.pubmed_searcher import PubMedSearcher


class PubMedComponent(Component):

    NAME = "PubMed"

    def __init__(self, email: str = None, searcher: PubMedSearcher = None):
        self._searcher = searcher or PubMedSearcher(email=email)

    @property
    def component_name(self) -> str:
        return self.NAME

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        pairs = self._collect_drug_condition_pairs(context)

        if not pairs:
            context.add_warning("PubMed: no drug/condition pairs found — skipped.")
            return ExecutionResult.fail("No drug or condition data available")

        entries: List[DrugPubMedEntry] = []

        for drug, condition, source in pairs:
            rct_count, _ = self._searcher.search(drug, condition)

            if rct_count > 3:
                category = PubMedEvidenceCategory.HIGH
            else:
                category = PubMedEvidenceCategory.LOW

            entry = DrugPubMedEntry(
                drug=drug,
                condition=condition,
                source=source,
                rct_count=rct_count,
                category=category,
            )
            entries.append(entry)
            print(f"  ✓ [PubMed/{source}] {entry.output}")

        result = PubMedResult.build(entries)
        context.add_result(result)
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
