"""
main.py — Composition Root

iBR Score = Sum(Benefit weighted scores) - Sum(Risk weighted scores)
  > 6   → Favorable
  2–6   → Conditional
  < 2   → Unfavourable

Pipeline execution order
────────────────────────
Sequential (must complete in order):
  1. ContraindicationComponent          — R1 override check (halts if absolute contraindication)
  2. ApprovalStatusComponent            — B1
  3. TherapeuticDuplicationComponent    — Detects duplicate drug classes/MOA across ALL meds;
                                          CONTRAINDICATED pairs → hard halt;
                                          NOT_RECOMMENDED / CONDITIONAL → logged, pipeline continues
  4. ADRComponent                       — R2 + R3 (stores raw ADR analysis for downstream)
  5. RMMComponent                       — Step 4 RMM table (reads from ADRResult)

Parallel (after sequential phase):
  6a. PubMedComponent                   — B3
  6b. AlternativesComponent             — B5  (uses alternatives_pipeline internally)
  6c. RiskMitigationComponent           — R4 + R5 (reads from ADRResult)
  6d. DiseaseSeverityComponent          — B6

alternatives_pipeline (mirrors main engine, AlternativesComponent excluded):
Sequential:
  1. ContraindicationComponent
  2. ApprovalStatusComponent
  3. TherapeuticDuplicationComponent
  4. ADRComponent
  5. RMMComponent
Parallel:
  6a. PubMedComponent
  6b. RiskMitigationComponent
  6c. DiseaseSeverityComponent
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# ── Components ────────────────────────────────────────────────────────────────
from domain.components.approval_status_component        import ApprovalStatusComponent
from domain.components.contraindication_component       import ContraindicationComponent
from domain.components.pubmed_component                 import PubMedComponent
from domain.components.alternatives_component           import AlternativesComponent
from domain.components.adr_component                    import ADRComponent
from domain.components.rmm_component                    import RMMComponent
from domain.components.risk_mitigation_component        import RiskMitigationComponent
from domain.components.disease_severity_component       import DiseaseSeverityComponent
from domain.components.therapeutic_duplication_component import TherapeuticDuplicationComponent

# ── Benefit rules (B1–B6) ────────────────────────────────────────────────────
from scoring.rules.approval_status_rule import ApprovalStatusRule   # B1  active
from scoring.rules.pubmed_rule          import PubMedEvidenceRule    # B3  active
from scoring.rules.alternatives_rule    import AlternativesRule      # B5  active
from scoring.rules.severity_rule        import SeverityRule          # B6  active
# Future: from scoring.rules.mme_rule        import MMERule          # B2
# Future: from scoring.rules.duplication_rule import DuplicationRule  # B4

# ── Risk rules (R1–R5) ───────────────────────────────────────────────────────
from scoring.rules.contraindication_rule  import ContraindicationRule   # R1  override
from scoring.rules.interaction_rule       import InteractionRule         # R2  active
from scoring.rules.adr_severity_rule      import ADRSeverityRule         # R3  active
from scoring.rules.preventability_rule    import PreventabilityRule      # R4  active
from scoring.rules.reversibility_rule     import ReversibilityRule       # R5  active

from scoring.scoring_engine import ScoringEngine
from BRA_engine             import BRAAnalysisEngine


def build_engine() -> BRAAnalysisEngine:
    scoring_engine = ScoringEngine(
        benefit_rules=[
            ApprovalStatusRule(),
            PubMedEvidenceRule(),
            AlternativesRule(),
            SeverityRule(),
        ],
        risk_rules=[
            InteractionRule(),
            ADRSeverityRule(),
            PreventabilityRule(),
            ReversibilityRule(),
        ],
        override_rules=[
            ContraindicationRule(),
        ],
    )

    alt_scoring_engine = ScoringEngine(
        benefit_rules=[
            ApprovalStatusRule(),
            PubMedEvidenceRule(),
            SeverityRule(),
        ],
        risk_rules=[
            InteractionRule(),
            ADRSeverityRule(),
            PreventabilityRule(),
            ReversibilityRule(),
        ],
        override_rules=[
            ContraindicationRule(),
        ],
    )

    # Mirrors the main engine exactly — AlternativesComponent intentionally excluded
    # to prevent infinite recursion (alternatives scoring alternatives).
    alternatives_pipeline = (
        BRAAnalysisEngine(scoring_engine=alt_scoring_engine)
        .add_parallel(ContraindicationComponent())
        .add_parallel(ApprovalStatusComponent())
        .add_sequential(TherapeuticDuplicationComponent())
        .add_sequential(ADRComponent())
        .add_sequential(RMMComponent())
        .add_parallel(PubMedComponent())
        .add_parallel(RiskMitigationComponent())
        .add_parallel(DiseaseSeverityComponent())
    )

    engine = (
        BRAAnalysisEngine(scoring_engine=scoring_engine)
        .add_parallel(ContraindicationComponent())
        .add_parallel(ApprovalStatusComponent())
        .add_sequential(TherapeuticDuplicationComponent())   # ← Step 3: NICE duplication check
        .add_sequential(ADRComponent())
        .add_sequential(RMMComponent())
        .add_parallel(PubMedComponent())
        .add_parallel(AlternativesComponent(scoring_engine=alternatives_pipeline))
        .add_parallel(RiskMitigationComponent())
        .add_parallel(DiseaseSeverityComponent())
    )
    return engine


if __name__ == "__main__":
    # Quick smoke-test using the real API request shape
    from bra_assessor import assess, print_report
    from api.request_adapter import adapt_request

    sample_request = {
        "patient": {
            "id": "P001",
            "fullName": "Sarah Jenkins",
            "age": "42",
            "gender": "Female",
            "isPregnant": False,
            "chiefComplaint": "Shortness of breath on exertion",
            "currentDiagnosis": [
                {"name": "Hypertension",  "treatmentGiven": "Medication", "medicationName": "Lisinopril"},
                {"name": "Anxiety",       "treatmentGiven": "Medication", "medicationName": "Lorazepam"},
            ],
            "pastMedicalConditions": [
                {
                    "conditionName": "Diabetes Type 2", "status": "Active",
                    "treatmentGiven": "Medication", "dateOfDiagnosis": "2020-03-15",
                    "details": "", "stopDate": "",
                },
            ],
            "allergies": [{"allergyName": "Penicillin", "severity": "Severe", "notes": "Anaphylaxis"}],
            "ongoingMedications": [
                {"name": "Metformin",    "dosage": "500 mg", "indication": None},
                {"name": "Atorvastatin", "dosage": "20 mg",  "indication": None},
            ],
        },
        "newMedications": [
            {"name": "Furosemide 40 MG Oral Tablet", "dosage": "40 mg", "type": "New"},
            {"name": "Aspirin 75 MG Oral Tablet",    "dosage": "75 mg", "type": "New"},
        ],
        "assessmentContext": {
            "assessmentDate": "2026-03-08",
            "doctorName":     "Dr. John Doe",
            "specialization": "Cardiology",
        },
    }

    patient_data, new_medications = adapt_request(sample_request)
    report = assess(patient_data=patient_data, new_medications=new_medications)
    print_report(report)
