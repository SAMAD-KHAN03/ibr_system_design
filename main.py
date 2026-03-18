"""
main.py — Composition Root

iBR Score = Sum(Benefit weighted scores) - Sum(Risk weighted scores)
  > 6   → Favorable
  2–6   → Conditional
  < 2   → Unfavourable

Sheet maxima (for reference):
  Max benefit score = 1210  |  Min benefit score = 110
  Max risk score    = 1425  |  Min risk score    = 140

Pipeline execution order
────────────────────────
Sequential (order-sensitive, each must complete before the next):
  1. ContraindicationComponent   — R1 override check; halts pipeline if primary drug
                                   is absolutely contraindicated; background drug
                                   contraindications are logged as warnings only.
  2. ApprovalStatusComponent     — B1 USFDA approval status
  3. ADRComponent                — R2 + R3; stores raw ADR analysis on context
                                   for downstream consumers (RMM, RiskMitigation)
  4. RMMComponent                — Step 4 RMM table; reads ADRResult from context

Parallel (independent; run concurrently after sequential phase):
  5a. PubMedComponent            — B3 strength of evidence
  5b. AlternativesComponent      — B5 (uses alternatives_pipeline internally)
  5c. RiskMitigationComponent    — R4 + R5; reads ADRResult from context
  5d. DiseaseSeverityComponent   — B6

Active scoring factors
──────────────────────
  Benefit : B1 ApprovalStatus, B3 StrengthOfEvidence, B5 Alternatives, B6 DiseaseSeverity
  Risk    : R1 Contraindication (override), R2 Interactions, R3 ADRSeverity,
            R4 RiskPreventability, R5 RiskReversibility

Stubbed (component and rule exist, component not yet wired):
  B2 MME (Molecule Market Experience)
  B4 TherapeuticDuplication
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# ── Components ────────────────────────────────────────────────────────────────
from domain.components.approval_status_component    import ApprovalStatusComponent
from domain.components.contraindication_component   import ContraindicationComponent
from domain.components.pubmed_component             import PubMedComponent
from domain.components.alternatives_component       import AlternativesComponent
from domain.components.adr_component                import ADRComponent
from domain.components.rmm_component                import RMMComponent
from domain.components.risk_mitigation_component    import RiskMitigationComponent
from domain.components.disease_severity_component   import DiseaseSeverityComponent
from domain.components.mme_component               import MMEComponent
from domain.components.therapeutic_duplication_component import TherapeuticDuplicationComponent

# ── Benefit rules (B1–B6) ────────────────────────────────────────────────────
from scoring.rules.approval_status_rule import ApprovalStatusRule   # B1  active
from scoring.rules.pubmed_rule          import PubMedEvidenceRule    # B3  active
from scoring.rules.alternatives_rule    import AlternativesRule      # B5  active
from scoring.rules.severity_rule        import SeverityRule          # B6  active
from scoring.rules.mme_rule         import MMERule              # B2  active
from scoring.rules.duplication_rule import DuplicationRule              # B4  active

# ── Risk rules (R1–R5) ───────────────────────────────────────────────────────
from scoring.rules.contraindication_rule  import ContraindicationRule   # R1  override
from scoring.rules.interaction_rule       import InteractionRule         # R2  active
from scoring.rules.adr_severity_rule      import ADRSeverityRule         # R3  active
from scoring.rules.preventability_rule    import PreventabilityRule      # R4  active
from scoring.rules.reversibility_rule     import ReversibilityRule       # R5  active

from scoring.scoring_engine  import ScoringEngine       # ← correct import path
from BRA_engine      import BRAAnalysisEngine


def build_engine() -> BRAAnalysisEngine:
    """
    Wires the full BRA pipeline.

    To activate B2 / B4 when their components are ready:
      1. Uncomment the component import above
      2. Add component to .add_sequential() below
      3. Uncomment the rule import and add rule to benefit_rules list
    """

    # ── Main scoring engine (all active factors) ──────────────────────────────
    scoring_engine = ScoringEngine(
        benefit_rules=[
            ApprovalStatusRule(),   # B1: Approved=2×70=140 | Off-label=1×50=50
            PubMedEvidenceRule(),   # B3: High(>3 RCTs)=3×90=270 | Low=0×20=0
            AlternativesRule(),     # B5: None=2×70=140 | Same=1×50=50 | Safer=0×20=0
            SeverityRule(),         # B6: AcuteLT=3×100=300 … Signs=1×20=20
            MMERule(),              # B2: Established=2×60=120 | New=1×40=40
            DuplicationRule(),      # B4: Unique=3×80=240 | Overlap=2×60=120 | Redundant=0×20=0
        ],
        risk_rules=[
            InteractionRule(),      # R2: Contraindicated=3×100=300 … None=0×10=0
            ADRSeverityRule(),      # R3: LT+risk=3×100=300 … NoSerious=0×10=0
            PreventabilityRule(),   # R4: NonPreventable=3×80=240 | Preventable=2×50=100
            ReversibilityRule(),    # R5: Irreversible=3×95=285 | Reversible=1×40=40
        ],
        override_rules=[
            ContraindicationRule(), # R1: Absolute=3×100=300 → forces Unfavourable
        ],
    )

    # ── Alternatives scoring engine (no AlternativesComponent → no recursion) ─
    # Mirrors the main scoring engine factor-for-factor.
    # AlternativesRule is excluded because alternatives don't score their own alternatives.
    alt_scoring_engine = ScoringEngine(
        benefit_rules=[
            ApprovalStatusRule(),
            PubMedEvidenceRule(),
            MMERule(),
            DuplicationRule(),
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

    # ── Alternatives pipeline (mirrors main pipeline, AlternativesComponent excluded) ─
    # IMPORTANT: ContraindicationComponent and ApprovalStatusComponent must be
    # add_sequential() — they are order-dependent and can halt the pipeline.
    alternatives_pipeline = (
        BRAAnalysisEngine(scoring_engine=alt_scoring_engine)
        # Sequential phase
        .add_sequential(ContraindicationComponent())   # R1 — must run first
        .add_sequential(MMEComponent())                # B2
        .add_sequential(TherapeuticDuplicationComponent())  # B4
        .add_sequential(ADRComponent())                # R2+R3
        .add_sequential(RMMComponent())                # Step 4
        # Parallel phase
        .add_parallel(ApprovalStatusComponent())     # B1
        .add_parallel(PubMedComponent())               # B3
        .add_parallel(RiskMitigationComponent())       # R4+R5
        .add_parallel(DiseaseSeverityComponent())      # B6
    )

    # ── Main engine ───────────────────────────────────────────────────────────
    # IMPORTANT: Sequential components run in order and can halt the pipeline.
    # Parallel components run concurrently and are order-independent.
    # ContraindicationComponent MUST be first in sequential — it is the hard stop.
    engine = (
        BRAAnalysisEngine(scoring_engine=scoring_engine)
        # ── Sequential phase ──────────────────────────────────────────────────
        .add_sequential(ContraindicationComponent())   # R1 — halt on primary contraindication
        .add_sequential(ApprovalStatusComponent())     # B1
        .add_sequential(MMEComponent())                # B2 — market experience
        .add_sequential(TherapeuticDuplicationComponent())  # B4 — NICE duplication check
        .add_sequential(ADRComponent())                # R2+R3 — must complete before RMM
        .add_sequential(RMMComponent())                # Step 4 — depends on ADRResult
        # ── Parallel phase ────────────────────────────────────────────────────
        .add_parallel(PubMedComponent())               # B3
        .add_parallel(AlternativesComponent(scoring_engine=alternatives_pipeline))  # B5
        .add_parallel(RiskMitigationComponent())       # R4+R5 — depends on ADRResult
        .add_parallel(DiseaseSeverityComponent())      # B6
    )
    return engine


if __name__ == "__main__":
    from bra_assessor import assess, print_report
    from api.request_adapter import adapt_request

    sample_request = {
        "patient": {
            "id":             "P001",
            "fullName":       "Sarah Jenkins",
            "age":            "42",
            "gender":         "Female",
            "isPregnant":     False,
            "chiefComplaint": "Shortness of breath on exertion",
            "currentDiagnosis": [
                {"name": "Hypertension", "treatmentGiven": "Medication", "medicationName": "Lisinopril"},
                {"name": "Anxiety",      "treatmentGiven": "Medication", "medicationName": "Lorazepam"},
            ],
            "pastMedicalConditions": [
                {
                    "conditionName": "Diabetes Type 2", "status": "Active",
                    "treatmentGiven": "Medication",     "dateOfDiagnosis": "2020-03-15",
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
