"""
main.py — Composition Root

iBR Score = Sum(Benefit weighted scores) - Sum(Risk weighted scores)
  > 6   → Favorable
  2–6   → Conditional
  < 2   → Unfavourable

Sheet maxima (for reference):
  Max benefit score = 1210  |  Min benefit score = 110
  Max risk score    = 1425  |  Min risk score    = 140
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# ── Components ────────────────────────────────────────────────────────────────
from domain.components.approval_status_component import ApprovalStatusComponent
from domain.components.contraindication_component import ContraindicationComponent
from domain.components.pubmed_component import PubMedComponent
from domain.components.alternatives_component import AlternativesComponent
# Future: from domain.components.mme_component import MMEComponent
# Future: from domain.components.duplication_component import DuplicationComponent
# Future: from domain.components.severity_component import SeverityComponent
# Future: from domain.components.interaction_component import InteractionComponent
# Future: from domain.components.adr_severity_component import ADRSeverityComponent
# Future: from domain.components.preventability_component import PreventabilityComponent
# Future: from domain.components.reversibility_component import ReversibilityComponent
# ── Benefit rules (B1–B6) ────────────────────────────────────────────────────
from scoring.rules.approval_status_rule import ApprovalStatusRule   # B1  active
from scoring.rules.pubmed_rule import PubMedEvidenceRule            # B3  active
from scoring.rules.alternatives_rule import AlternativesRule        # B5  active
# Future: from scoring.rules.mme_rule import MMERule                # B2
# Future: from scoring.rules.duplication_rule import DuplicationRule # B4
# Future: from scoring.rules.severity_rule import SeverityRule      # B6

# ── Risk rules (R1–R5) ───────────────────────────────────────────────────────
from scoring.rules.contraindication_rule import ContraindicationRule # R1  override
# Future: from scoring.rules.interaction_rule import InteractionRule  # R2
# Future: from scoring.rules.adr_severity_rule import ADRSeverityRule # R3
# Future: from scoring.rules.preventability_rule import PreventabilityRule # R4
# Future: from scoring.rules.reversibility_rule import ReversibilityRule  # R5

from scoring.scoring_engine import ScoringEngine
from BRA_engine import BRAAnalysisEngine


def build_engine() -> BRAAnalysisEngine:
    """
    Wire the full pipeline.

    To add a new factor:
      1. Uncomment its rule import above
      2. Add rule instance to benefit_rules or risk_rules below
      3. If it has an override behaviour, add to override_rules instead
    """

    scoring_engine = ScoringEngine(
        benefit_rules=[
            ApprovalStatusRule(),   # B1: Approved=2×70=140 | Off-label=1×50=50
            PubMedEvidenceRule(),   # B3: High(>3 RCTs)=3×90=270 | Low=0×20=0
            AlternativesRule(),     # B5: None=2×70=140 | Same=1×50=50 | Safer=0×20=0
            # MMERule(),            # B2: Established=2×60=120 | New=1×40=40
            # DuplicationRule(),    # B4: Unique=3×80=240 | Overlap=2×60=120 | Redundant=0×20=0
            # SeverityRule(),       # B6: AcuteLT=3×100=300 … Signs=1×20=20
        ],
        risk_rules=[
            # InteractionRule(),    # R2: Contraindicated=3×100=300 … None=0×10=0
            # ADRSeverityRule(),    # R3: LT+risk=3×100=300 … NoSerious=0×10=0
            # PreventabilityRule(), # R4: NonPreventable=3×80=240 | Preventable=2×50=100
            # ReversibilityRule(),  # R5: Irreversible=3×95=285 | Reversible=1×40=40
        ],
        override_rules=[
            ContraindicationRule(), # R1: Absolute=3×100=300 → forces Unfavourable
        ],
    )

    # Inner pipeline used to score each alternative (no Alternatives component
    # to avoid infinite recursion)
    alt_scoring_engine = ScoringEngine(
        benefit_rules=[
            ApprovalStatusRule(),
            PubMedEvidenceRule(),
        ],
        risk_rules=[],
        override_rules=[
            ContraindicationRule(),
        ],
    )
    alternatives_pipeline = (
        BRAAnalysisEngine(scoring_engine=alt_scoring_engine)
        .add_sequential(ContraindicationComponent())
        .add_sequential(ApprovalStatusComponent())
        .add_parallel(PubMedComponent())
    )

    engine = (
        BRAAnalysisEngine(scoring_engine=scoring_engine)
        .add_sequential(ContraindicationComponent())
        .add_sequential(ApprovalStatusComponent())
        .add_parallel(PubMedComponent())
        .add_parallel(AlternativesComponent(scoring_engine=alternatives_pipeline))
    )
    return engine


if __name__ == "__main__":
    patient_data = {
        "id": "P001",
        "fullName": "Jane Doe",
        "age": 38,
        "gender": "female",
        "chiefComplaint": "Heart failure management",
        "pregnancy_info": {"pregnancy_status": "Not Applicable", "lactation": "No"},
        "currentDiagnosis": [
            {"name": "Heart Failure", "treatmentGiven": "Medication", "medicationName": "carvedilol"}
        ],
        "pastMedicalConditions": [
            {"conditionName": "Hypertension", "status": "Active", "treatmentGiven": "lisinopril",
             "dateOfDiagnosis": "2020-01-01", "details": "", "stopDate": ""}
        ],
        "allergies": [],
        "ongoingMedications": [
            {"name": "carvedilol", "dosage": "6.25mg", "indication": "heart failure"}
        ],
    }
    drug_data = {"name": "carvedilol", "condition": "heart failure"}

    engine = build_engine()
    context = engine.execute(patient_data=patient_data, drug_data=drug_data)

    if context:
        print("\n" + "=" * 60)
        print("iBR REPORT OUTPUT")
        print("=" * 60)
        for name, result in context.component_results.items():
            print(f"\n── {name} ──")
            print(result.metadata.get("output", ""))

        print("\n── Final iBR Score ──")
        fs = context.final_score
        if fs:
            if fs.get("override_triggered"):
                print(f"  ⚠  Override: {fs['override_rule']}")
                print(f"  Risk total : {fs['risk_total']}")
            else:
                print(f"  Benefit total : {fs['benefit_total']}")
                print(f"  Risk total    : {fs['risk_total']}")
                print(f"  Benefit breakdown : {fs['benefit_breakdown']}")
                print(f"  Risk breakdown    : {fs['risk_breakdown']}")
            print(f"  iBR Score  : {fs['ibr_score']}")
            print(f"  iBR Outcome: {fs['ibr_outcome']}")

        if context.warnings:
            print("\n── Warnings ──")
            for w in context.warnings:
                print(f"  • {w}")
