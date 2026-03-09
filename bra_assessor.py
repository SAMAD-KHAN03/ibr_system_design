"""
bra_assessor.py — Per-Medicine Assessment Runner

CORRECT DESIGN:
  - The full BRA engine runs ONLY on newMedications (drugs under review).
  - All other medicines in patient_data (ongoingMedications, currentDiagnosis,
    pastMedicalConditions) are CONTEXT — they are used internally by components
    for ADR/contraindication checks, but are NOT independently assessed.
  - assess() accepts a list of new_medications and runs engine.execute() once
    per entry.

Background medicines being scored was the source of:
  1. Null ibr_scores (background drugs halt at Contraindication phase)
  2. Explosive number of engine runs (full pipeline per background drug)
"""

from typing import Dict, Any, List
from main import build_engine


def assess(patient_data: dict, new_medications: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Runs the full BRA pipeline once per new medication under review.

    Parameters
    ----------
    patient_data      : internal patient schema (after request_adapter)
    new_medications   : list of {name, condition, dosage} — from newMedications
                        in the API request, already adapted by request_adapter

    Returns
    -------
    {
        "per_medicine": {
            "Furosemide 40 MG Oral Tablet": {
                "drug":              str,
                "condition":         str,
                "dosage":            str,
                "ibr_score":         float | None,
                "ibr_outcome":       "Favorable" | "Conditional" | "Unfavourable" | None,
                "benefit_total":     float | None,
                "risk_total":        float | None,
                "benefit_breakdown": dict,
                "risk_breakdown":    dict,
                "max_benefit":       float | None,
                "max_risk":          float | None,
                "override_triggered": bool,
                "override_rule":     str | None,
                "component_outputs": dict,
                "warnings":          list,
                "halted":            bool,   # True if pipeline stopped early
            },
            ...
        },
        "summary": {
            "total_medicines_evaluated": int,
            "favorable":    [...],
            "conditional":  [...],
            "unfavourable": [...],
            "overridden":   [...],
        }
    }
    """
    engine = build_engine()

    if not new_medications:
        return {
            "per_medicine": {},
            "summary": {
                "total_medicines_evaluated": 0,
                "favorable": [], "conditional": [], "unfavourable": [], "overridden": [],
            },
        }

    per_medicine: Dict[str, Any] = {}
    favorable, conditional, unfavourable, overridden = [], [], [], []

    for med in new_medications:
        drug_name = med["name"]
        drug_data = {"name": drug_name, "condition": med.get("condition", "")}

        print(f"\n{'='*60}")
        print(f"  Assessing NEW medication: {drug_name}")
        print(f"  Condition : {med.get('condition') or 'unspecified'}")
        print(f"{'='*60}")

        context = engine.execute(patient_data=patient_data, drug_data=drug_data)

        if context is None:
            per_medicine[drug_name] = {
                "drug":          drug_name,
                "condition":     med.get("condition", ""),
                "dosage":        med.get("dosage", ""),
                "error":         "Engine returned no context",
                "halted":        True,
            }
            unfavourable.append(drug_name)
            continue

        fs = context.final_score or {}
        halted = fs.get("ibr_score") is None  # scoring never ran → pipeline halted

        # ── Extract component outputs ────────────────────────────────────────
        # Each component gets its own structured key so the frontend can
        # consume specific sections without parsing free-text strings.
        component_outputs = {}
        rmm_table = []

        for name, result in context.component_results.items():
            meta = result.metadata or {}
            component_outputs[name] = meta.get("output", "")

            # RMM: pull the full table out of metadata
            if name == "RMM" and "rmm_table" in meta:
                rmm_table = meta["rmm_table"]

        entry = {
            "drug":               drug_name,
            "condition":          med.get("condition", ""),
            "dosage":             med.get("dosage", ""),
            "ibr_score":          fs.get("ibr_score"),
            "ibr_outcome":        fs.get("ibr_outcome"),
            "benefit_total":      fs.get("benefit_total"),
            "risk_total":         fs.get("risk_total"),
            "benefit_breakdown":  fs.get("benefit_breakdown", {}),
            "risk_breakdown":     fs.get("risk_breakdown", {}),
            "max_benefit":        fs.get("max_benefit"),
            "max_risk":           fs.get("max_risk"),
            "override_triggered": fs.get("override_triggered", False),
            "override_rule":      fs.get("override_rule"),
            "component_outputs":  component_outputs,
            "rmm_table":          rmm_table,
            "warnings":           context.warnings,
            "halted":             halted,
        }
        per_medicine[drug_name] = entry

        if halted:
            # Pipeline stopped (e.g. primary drug contraindicated via override)
            unfavourable.append(drug_name)
        elif fs.get("override_triggered"):
            overridden.append(drug_name)
            unfavourable.append(drug_name)
        elif fs.get("ibr_outcome") == "Favorable":
            favorable.append(drug_name)
        elif fs.get("ibr_outcome") == "Conditional":
            conditional.append(drug_name)
        else:
            unfavourable.append(drug_name)

    return {
        "per_medicine": per_medicine,
        "summary": {
            "total_medicines_evaluated": len(new_medications),
            "favorable":    favorable,
            "conditional":  conditional,
            "unfavourable": [m for m in unfavourable if m not in overridden],
            "overridden":   overridden,
        },
    }


def print_report(report: Dict[str, Any]) -> None:
    summary = report.get("summary", {})
    print("\n" + "=" * 70)
    print("  iBR ASSESSMENT REPORT — NEW MEDICATIONS")
    print("=" * 70)
    print(f"  Total assessed  : {summary.get('total_medicines_evaluated', 0)}")
    print(f"  Favorable       : {', '.join(summary.get('favorable', [])) or '—'}")
    print(f"  Conditional     : {', '.join(summary.get('conditional', [])) or '—'}")
    print(f"  Unfavourable    : {', '.join(summary.get('unfavourable', [])) or '—'}")
    print(f"  Overridden      : {', '.join(summary.get('overridden', [])) or '—'}")

    for drug, entry in report.get("per_medicine", {}).items():
        print(f"\n{'─'*70}")
        print(f"  DRUG      : {entry['drug'].upper()}")
        print(f"  Condition : {entry.get('condition') or '—'}")
        print(f"  Dosage    : {entry.get('dosage') or '—'}")

        if entry.get("error"):
            print(f"  ⚠  Error: {entry['error']}")
            continue

        if entry.get("halted"):
            print("  ⚠  Pipeline halted — primary drug is contraindicated.")
            print(f"  Warnings: {entry.get('warnings', [])}")
            continue

        if entry.get("override_triggered"):
            print(f"  ⚠  OVERRIDE: {entry['override_rule']}")
            print(f"  Risk total    : {entry.get('risk_total')}")
        else:
            print(f"  Benefit total : {entry.get('benefit_total')}")
            print(f"  Risk total    : {entry.get('risk_total')}")
            print(f"  Benefit B/D   : {entry.get('benefit_breakdown')}")
            print(f"  Risk B/D      : {entry.get('risk_breakdown')}")

        print(f"  iBR Score   : {entry.get('ibr_score')}")
        print(f"  iBR Outcome : {entry.get('ibr_outcome')}")

        if entry.get("warnings"):
            print("  Warnings:")
            for w in entry["warnings"]:
                print(f"    • {w}")

    print("\n" + "=" * 70 + "\n")
