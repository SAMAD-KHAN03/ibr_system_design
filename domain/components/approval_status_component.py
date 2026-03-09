from typing import List, Tuple
from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.enums import ApprovalCategory
from domain.results.approval_status_result import ApprovalStatusResult, DrugApprovalEntry
from infrastructure.approvalstatus_infrastructure.usfda_checker import USFDAChecker


class ApprovalStatusComponent(Component):
    """
    Checks USFDA approval for:
      1. The primary drug under review              (from drug_data)
      2. All ongoing medications                    (patient_data["ongoingMedications"])
      3. Medications from current diagnoses         (patient_data["currentDiagnosis"])
      4. Treatments from past medical conditions    (patient_data["pastMedicalConditions"])

    Each (drug, condition) pair is checked independently and stored as a
    DrugApprovalEntry. The scoring rule reads only the primary drug's category
    so existing scoring logic requires zero changes.
    """

    NAME = "ApprovalStatus"

    def __init__(self, checker: USFDAChecker = None):
        self._checker = checker or USFDAChecker()

    @property
    def component_name(self) -> str:
        return self.NAME

    # ── Entry point ─────────────────────────────────────────────────────────

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        pairs = self._collect_drug_condition_pairs(context)

        if not pairs:
            context.add_warning("ApprovalStatus: no drug/condition pairs found — skipped.")
            return ExecutionResult.fail("No drug or condition data available")

        entries: List[DrugApprovalEntry] = []
        errors: List[str] = []

        for drug, condition, source in pairs:
            entry, error = self._check_single(drug, condition, source)
            if error:
                errors.append(error)
                context.add_warning(f"ApprovalStatus: {error}")
            else:
                entries.append(entry)
                print(f"  ✓ [{source}] {entry.output}")

        if not entries:
            return ExecutionResult.fail(f"All FDA lookups failed: {'; '.join(errors)}")

        result = ApprovalStatusResult.build(entries)
        context.add_result(result)

        summary = result.metadata["summary"]
        print(
            f"\n  ApprovalStatus summary — "
            f"{summary['approved_count']}/{summary['total_checked']} approved, "
            f"{summary['off_label_count']} off-label/not found"
        )
        return ExecutionResult.ok(data=result.metadata)

    # ── Pair collection ──────────────────────────────────────────────────────

    def _collect_drug_condition_pairs(
        self, context: ExecutionContext
    ) -> List[Tuple[str, str, str]]:
        """
        Returns a deduplicated list of (drug, condition, source) tuples.
        Each source tag maps to where in PatientModel the data came from.
        """
        seen: set[Tuple[str, str]] = set()
        pairs: List[Tuple[str, str, str]] = []

        def add(drug: str, condition: str, source: str) -> None:
            drug      = drug.strip()
            condition = condition.strip()
            # Primary drug is always added even if condition is empty —
            # background drugs (ongoing, past) are skipped if either is missing.
            if source == "primary":
                if drug and (drug.lower(), condition.lower()) not in seen:
                    seen.add((drug.lower(), condition.lower()))
                    pairs.append((drug, condition, source))
            else:
                if drug and condition and (drug.lower(), condition.lower()) not in seen:
                    seen.add((drug.lower(), condition.lower()))
                    pairs.append((drug, condition, source))

        # 1️⃣  Primary drug being evaluated
        add(context.drug_name, context.condition, "primary")

        patient = context.patient_data

        # 2️⃣  Ongoing medications — use their indication if present,
        #     otherwise fall back to the primary condition
        for med in patient.get("ongoingMedications", []):
            drug      = med.get("name", "")
            condition = med.get("indication") or context.condition
            add(drug, condition, "ongoing_medication")

        # 3️⃣  Current diagnoses — medication prescribed for the diagnosis
        for dx in patient.get("currentDiagnosis", []):
            drug      = dx.get("medicationName", "")
            condition = dx.get("name", "")        # diagnosis name IS the condition
            if drug:
                add(drug, condition, "current_diagnosis")

        # 4️⃣  Past medical conditions — treatment given for each condition
        for cond in patient.get("pastMedicalConditions", []):
            drug      = cond.get("treatmentGiven", "")
            condition = cond.get("conditionName", "")
            if drug:
                add(drug, condition, "past_condition")

        return pairs

    # ── Single lookup ────────────────────────────────────────────────────────

    def _check_single(
        self, drug: str, condition: str, source: str
    ) -> Tuple[DrugApprovalEntry | None, str | None]:
        try:
            approved = self._checker.check_approval(drug, condition)
            entry = DrugApprovalEntry(
                drug=drug,
                condition=condition,
                source=source,
                approved=approved,
                category=ApprovalCategory.APPROVED if approved else ApprovalCategory.OFF_LABEL,
            )
            return entry, None
        except Exception as exc:
            return None, f"FDA lookup failed for '{drug}/{condition}': {exc}"
