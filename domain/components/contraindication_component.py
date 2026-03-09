from typing import Set, List, Tuple, Optional

from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.enums import ContraindicationCategory
from domain.results.contraindication_result import (
    ContraindicationResult,
    DrugContraindicationEntry,
)
from infrastructure.contraindication_infrastructure.fda_label_fetcher import FDALabelFetcher
from infrastructure.contraindication_infrastructure.concept_extractor import extract_concepts, extract_contraindication_concepts
from infrastructure.contraindication_infrastructure.gemini_explainer import GeminiExplainer


class ContraindicationComponent(Component):
    """
    Checks ALL patient medicines for contraindications against the patient's
    OTHER active conditions. Sources checked:

      1. Primary drug under review           (drug_data)
      2. Ongoing medications                 (patient_data["ongoingMedications"])
      3. Current diagnosis medications       (patient_data["currentDiagnosis"])
      4. Past medical condition treatments   (patient_data["pastMedicalConditions"])

    Pipeline behaviour
    ------------------
    * ALL SAFE       → ExecutionResult.ok()    — pipeline continues.
    * ANY FLAGGED    → ExecutionResult.halt()  — pipeline stops; at least one
                       drug is contraindicated and must not proceed to scoring.

    The treating condition for each drug is excluded from its own check so
    a drug prescribed specifically for a condition is not falsely flagged.
    """

    NAME = "Contraindication"

    def __init__(
        self,
        fetcher:   FDALabelFetcher = None,
        explainer: GeminiExplainer = None,
    ):
        self._fetcher   = fetcher   or FDALabelFetcher()
        self._explainer = explainer or GeminiExplainer()

    @property
    def component_name(self) -> str:
        return self.NAME

    # ── Entry point ──────────────────────────────────────────────────────────

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        drug_pairs = self._collect_drug_condition_pairs(context)

        if not drug_pairs:
            context.add_warning("Contraindication: no drugs found — skipped.")
            context.add_result(ContraindicationResult.build([]))
            return ExecutionResult.ok()

        # Build patient concepts once (full set — per-drug exclusions applied inside loop)
        patient_concepts_full = self._extract_patient_concepts(context)
        patient_context_str   = self._build_patient_context(context)

        entries: List[DrugContraindicationEntry] = []

        for drug, treating_condition, source in drug_pairs:
            entry = self._check_single(
                drug, treating_condition, source,
                patient_concepts_full, patient_context_str,
            )
            entries.append(entry)
            status = "⚠ " if entry.is_contraindicated else "✓"
            print(f"  {status} [Contraindication/{source}] {drug} → {entry.category.value}"
                  + (f" ({', '.join(entry.risk_concepts)})" if entry.risk_concepts else ""))

        result = ContraindicationResult.build(entries)
        context.add_result(result)

        # ── Background drug warnings (never halt) ─────────────────────────────
        # Ongoing meds, current diagnosis meds, past condition treatments are
        # already prescribed by a doctor. Flag them as warnings for the report
        # but do NOT halt — halting would prevent scoring the drug under review.
        background_flagged = [e for e in entries if e.is_contraindicated and e.source != "primary"]
        for e in background_flagged:
            msg = (f"Contraindication warning [{e.source}]: '{e.drug}' flagged for "
                   f"{', '.join(e.risk_concepts)} — report to prescriber.")
            context.add_warning(msg)
            print(f"  ⚠  [background] {msg}")

        # ── Primary drug — halt only if THIS drug is contraindicated ──────────
        primary_flagged = [e for e in entries if e.is_contraindicated and e.source == "primary"]
        if primary_flagged:
            names = ", ".join(e.drug for e in primary_flagged)
            print(f"\n  ⚠  Contraindication: primary drug '{names}' is contraindicated — halting pipeline.")
            # Store flag on context so AlternativesComponent knows to run
            context.primary_contraindicated = True
            return ExecutionResult.halt(
                f"Primary drug contraindicated: {names}"
            )

        context.primary_contraindicated = False
        print(f"  ✓ Contraindication: primary drug cleared.")
        return ExecutionResult.ok()

    # ── Drug collection ──────────────────────────────────────────────────────

    def _collect_drug_condition_pairs(
        self, context: ExecutionContext
    ) -> List[Tuple[str, str, str]]:
        """
        Returns deduplicated (drug, treating_condition, source) tuples.
        The treating_condition is excluded per-drug during the FDA check so
        the drug is not flagged for the very condition it is prescribed to treat.
        """
        seen: set[tuple[str, str]] = set()
        pairs: List[Tuple[str, str, str]] = []

        def add(drug: str, condition: str, source: str) -> None:
            drug, condition = drug.strip(), condition.strip()
            if drug and (drug.lower(), condition.lower()) not in seen:
                seen.add((drug.lower(), condition.lower()))
                pairs.append((drug, condition, source))

        # 1️⃣  Primary drug
        add(context.drug_name, context.condition, "primary")

        patient = context.patient_data

        # 2️⃣  Ongoing medications
        for med in patient.get("ongoingMedications", []):
            drug      = med.get("name", "")
            condition = med.get("indication") or context.condition
            add(drug, condition, "ongoing_medication")

        # 3️⃣  Current diagnosis medications
        for dx in patient.get("currentDiagnosis", []):
            drug      = dx.get("medicationName", "")
            condition = dx.get("name", "")
            if drug:
                add(drug, condition, "current_diagnosis")

        # 4️⃣  Past condition treatments
        for cond in patient.get("pastMedicalConditions", []):
            drug      = cond.get("treatmentGiven", "")
            condition = cond.get("conditionName", "")
            if drug:
                add(drug, condition, "past_condition")

        return pairs

    # ── Single drug check ────────────────────────────────────────────────────

    def _check_single(
        self,
        drug: str,
        treating_condition: str,
        source: str,
        patient_concepts_full: Set[str],
        patient_context_str: str,
    ) -> DrugContraindicationEntry:
        """
        Check one drug. Excludes the treating_condition concepts from the
        patient concept set so the drug isn't flagged for its own indication.
        Returns a DrugContraindicationEntry (safe or flagged).
        """
        def _safe_entry() -> DrugContraindicationEntry:
            return DrugContraindicationEntry(
                drug=drug, source=source,
                treating_condition=treating_condition,
                category=ContraindicationCategory.SAFE,
                risk_concepts=[], clinical_explanation="",
            )

        sections = self._fetcher.fetch_sections(drug)
        if not sections:
            return _safe_entry()

        # Remove concepts that belong to the treating condition
        exclusion_concepts  = extract_concepts(treating_condition)
        patient_concepts    = patient_concepts_full - exclusion_concepts

        fda_text     = sections.get("contraindications", "") + " " + sections.get("boxed_warning", "")
        fda_concepts = extract_contraindication_concepts(fda_text)

        overlap = patient_concepts & fda_concepts
        if not overlap:
            return _safe_entry()

        risk_concept = next(iter(overlap))
        category     = self._classify(risk_concept, sections)
        fda_context  = "\n\n".join(f"{k.upper()}:\n{v}" for k, v in sections.items() if v)
        explanation  = self._explainer.explain(
            drug, risk_concept, treating_condition, fda_context, patient_context_str
        )

        return DrugContraindicationEntry(
            drug=drug, source=source,
            treating_condition=treating_condition,
            category=category,
            risk_concepts=list(overlap),
            clinical_explanation=explanation,
        )

    # ── Patient concept extraction ───────────────────────────────────────────

    def _extract_patient_concepts(self, context: ExecutionContext) -> Set[str]:
        """
        Builds the FULL patient concept set (no exclusions yet — exclusions
        are applied per-drug inside _check_single).
        """
        texts: list[str] = []
        patient = context.patient_data

        # Demographics
        age = patient.get("age", 0)
        try:
            age = int(age)
        except (ValueError, TypeError):
            age = 0
        if age >= 65:
            texts.append("elderly")
        elif 0 < age < 18:
            texts.append("pediatric")

        # Pregnancy / lactation
        preg = patient.get("pregnancy_info", {})
        if preg.get("pregnancy_status") == "Ongoing Pregnancy":
            texts.extend(["pregnancy", "pregnant"])
        if preg.get("lactation") == "Yes":
            texts.extend(["lactation", "breastfeeding"])

        # Current diagnoses
        for dx in patient.get("currentDiagnosis", []):
            texts.append(dx.get("name", ""))

        # Past medical conditions
        for cond in patient.get("pastMedicalConditions", []):
            status = cond.get("status", "").lower()
            if status in ("active", "chronic", ""):
                texts.append(cond.get("conditionName", ""))

        # Allergies
        for allergy in patient.get("allergies", []):
            texts.append(allergy.get("allergyName", ""))

        all_concepts: Set[str] = set()
        for text in texts:
            if text:
                all_concepts |= extract_concepts(text)

        return all_concepts

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _classify(risk_concept: str, sections: dict) -> ContraindicationCategory:
        if "PREGNANCY" in risk_concept or "LACTATION" in risk_concept:
            return ContraindicationCategory.PREGNANCY
        if sections.get("boxed_warning"):
            return ContraindicationCategory.BOXED_WARNING
        return ContraindicationCategory.ABSOLUTE

    @staticmethod
    def _build_patient_context(context: ExecutionContext) -> str:
        p = context.patient_data
        lines = [
            f"Age: {p.get('age', 'unknown')}",
            f"Gender: {p.get('gender', 'unknown')}",
            f"Chief complaint: {p.get('chiefComplaint', '')}",
        ]
        current_dx = [d.get("name", "") for d in p.get("currentDiagnosis", []) if d.get("name")]
        if current_dx:
            lines.append(f"Current diagnoses: {', '.join(current_dx)}")
        past = [c.get("conditionName", "") for c in p.get("pastMedicalConditions", []) if c.get("conditionName")]
        if past:
            lines.append(f"Past conditions: {', '.join(past)}")
        preg = p.get("pregnancy_info", {})
        if preg.get("pregnancy_status") == "Ongoing Pregnancy":
            lines.append(f"Pregnancy: {preg.get('Trimester', 'unknown trimester')}")
        if preg.get("lactation") == "Yes":
            lines.append("Lactation: active")
        return "\n".join(lines)
