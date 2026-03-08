"""
main.py — Composition Root

Adding a new component:
  1. Create domain/components/my_component.py       (subclass Component)
  2. Create domain/results/my_result.py             (subclass ComponentResult)
  3. Create scoring/rules/my_rule.py                (subclass WeightedScoreRule)
  4. Add enum values to domain/enums.py
  5. Register below — nothing else ever changes.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from domain.components.approval_status_component import ApprovalStatusComponent
from domain.components.contraindication_component import ContraindicationComponent
from domain.components.pubmed_component import PubMedComponent
from scoring.rules.approval_status_rule import ApprovalStatusRule
from scoring.rules.contraindication_rule import ContraindicationRule
from scoring.rules.pubmed_rule import PubMedEvidenceRule
from scoring.scoring_engine import ScoringEngine
from scoring.rules.alternatives_rule import AlternativesRule
from domain.components.alternatives_component import AlternativesComponent
from BRA_engine import BRAAnalysisEngine
import sys
"""
main.py — Composition Root
"""




def build_engine() -> BRAAnalysisEngine:
    scoring_engine = ScoringEngine(
        rules=[
            ApprovalStatusRule(),
            PubMedEvidenceRule(),
            AlternativesRule(),
        ],
        override_rules=[
            ContraindicationRule(),
        ],
    )

    # Build the inner engine used to score each alternative.
    # It runs the same components EXCEPT AlternativesComponent itself
    # (to avoid infinite recursion).
    alternatives_scoring_engine = ScoringEngine(
        rules=[
            ApprovalStatusRule(),
            PubMedEvidenceRule(),
        ],
        override_rules=[
            ContraindicationRule(),
        ],
    )
    alternatives_pipeline = (
        BRAAnalysisEngine(scoring_engine=alternatives_scoring_engine)
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
        "pregnancy_info": {
            "pregnancy_status": "Not Pregnant",
            "Trimester": "null",
            "lactation": "null",
        },
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

    drug_data = {
        "name": "carvedilol",
        "condition": "heart failure",
    }

    engine = build_engine()
    context = engine.execute(patient_data=patient_data, drug_data=drug_data)

    if context:
        print("\n" + "="*60)
        print("iBR REPORT OUTPUT")
        print("="*60)
        for name, result in context.component_results.items():
            print(f"\n── {name} ──")
            print(result.metadata.get("output", ""))
        print("\n── Final Score ──")
        print(context.final_score)
        if context.warnings:
            print("\n── Warnings ──")
            for w in context.warnings:
                print(f"  • {w}")