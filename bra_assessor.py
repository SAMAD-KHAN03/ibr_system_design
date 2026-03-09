"""
bra_assessor.py — Per-Medicine Assessment Runner

CORRECT DESIGN:
  - The full BRA engine runs ONLY on newMedications (drugs under review).
  - All other medicines in patient_data (ongoingMedications, currentDiagnosis,
    pastMedicalConditions) are CONTEXT — they are used internally by components
    for ADR/contraindication/duplication checks, but are NOT independently assessed.
  - assess() accepts a list of new_medications and runs engine.execute() once
    per entry.

TherapeuticDuplicationComponent integration notes:
  - Runs as Step 3 (sequential), after ApprovalStatus, before ADR.
  - CONTRAINDICATED pairs → pipeline halts (halted=True in entry).
  - NOT_RECOMMENDED / CONDITIONAL / NO_RATIONALE pairs → pipeline continues;
    findings surfaced in entry["therapeutic_duplication"].
  - Result keyed as "TherapeuticDuplication" in context.component_results.
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
            "<drug_name>": {
                "drug":                    str,
                "condition":               str,
                "dosage":                  str,
                "ibr_score":               float | None,
                "ibr_outcome":             "Favorable" | "Conditional" | "Unfavourable" | None,
                "benefit_total":           float | None,
                "risk_total":              float | None,
                "benefit_breakdown":       dict,
                "risk_breakdown":          dict,
                "max_benefit":             float | None,
                "max_risk":                float | None,
                "override_triggered":      bool,
                "override_rule":           str | None,
                "therapeutic_duplication": dict | None,   ← NEW: structured duplication findings
                "component_outputs":       dict,
                "rmm_table":               list,
                "warnings":                list,
                "halted":                  bool,
            },
            ...
        },
        "summary": {
            "total_medicines_evaluated": int,
            "favorable":    [...],
            "conditional":  [...],
            "unfavourable": [...],
            "overridden":   [...],
            "duplication_alerts": int,   ← NEW: total non-unique pairs across all assessments
        }
    }
    """
    engine = build_engine()

    if not new_medications:
        return {
            "per_medicine": {},
            "summary": {
                "total_medicines_evaluated": 0,
                "favorable":          [],
                "conditional":        [],
                "unfavourable":       [],
                "overridden":         [],
                "duplication_alerts": 0,
            },
        }

    per_medicine: Dict[str, Any] = {}
    favorable, conditional, unfavourable, overridden = [], [], [], []
    total_duplication_alerts = 0

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
                "drug":    drug_name,
                "condition": med.get("condition", ""),
                "dosage":  med.get("dosage", ""),
                "error":   "Engine returned no context",
                "halted":  True,
            }
            unfavourable.append(drug_name)
            continue

        fs = context.final_score or {}
        halted = fs.get("ibr_score") is None  # scoring never ran → pipeline halted

        # ── Extract TherapeuticDuplication result ────────────────────────────
        duplication_data = _extract_duplication(context)
        if duplication_data:
            total_duplication_alerts += duplication_data.get("duplicate_count", 0)

        # ── Extract component outputs ────────────────────────────────────────
        component_outputs = {}
        rmm_table = []

        for name, result in context.component_results.items():
            meta = result.metadata or {}
            component_outputs[name] = meta.get("output", "")

            if name == "RMM" and "rmm_table" in meta:
                rmm_table = meta["rmm_table"]

        entry = {
            "drug":                    drug_name,
            "condition":               med.get("condition", ""),
            "dosage":                  med.get("dosage", ""),
            "ibr_score":               fs.get("ibr_score"),
            "ibr_outcome":             fs.get("ibr_outcome"),
            "benefit_total":           fs.get("benefit_total"),
            "risk_total":              fs.get("risk_total"),
            "benefit_breakdown":       fs.get("benefit_breakdown", {}),
            "risk_breakdown":          fs.get("risk_breakdown", {}),
            "max_benefit":             fs.get("max_benefit"),
            "max_risk":                fs.get("max_risk"),
            "override_triggered":      fs.get("override_triggered", False),
            "override_rule":           fs.get("override_rule"),
            "therapeutic_duplication": duplication_data,   # ← structured duplication findings
            "component_outputs":       component_outputs,
            "rmm_table":               rmm_table,
            "warnings":                context.warnings,
            "halted":                  halted,
        }
        per_medicine[drug_name] = entry

        if halted:
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
            "favorable":          favorable,
            "conditional":        conditional,
            "unfavourable":       [m for m in unfavourable if m not in overridden],
            "overridden":         overridden,
            "duplication_alerts": total_duplication_alerts,
        },
    }


def _extract_duplication(context) -> Dict[str, Any] | None:
    """
    Pulls the TherapeuticDuplication result out of context.component_results.
    Returns None if the component didn't run (e.g. pipeline halted before it).
    """
    result = context.get_result("TherapeuticDuplication")
    if result is None:
        return None
    return result.metadata


# ── Report printer ───────────────────────────────────────────────────────────

def print_report(report: Dict[str, Any]) -> None:
    summary = report.get("summary", {})
    print("\n" + "=" * 70)
    print("  iBR ASSESSMENT REPORT — NEW MEDICATIONS")
    print("=" * 70)
    print(f"  Total assessed      : {summary.get('total_medicines_evaluated', 0)}")
    print(f"  Favorable           : {', '.join(summary.get('favorable',    [])) or '—'}")
    print(f"  Conditional         : {', '.join(summary.get('conditional',  [])) or '—'}")
    print(f"  Unfavourable        : {', '.join(summary.get('unfavourable', [])) or '—'}")
    print(f"  Overridden          : {', '.join(summary.get('overridden',   [])) or '—'}")
    print(f"  Duplication alerts  : {summary.get('duplication_alerts', 0)}")

    for drug, entry in report.get("per_medicine", {}).items():
        print(f"\n{'─'*70}")
        print(f"  DRUG      : {entry['drug'].upper()}")
        print(f"  Condition : {entry.get('condition') or '—'}")
        print(f"  Dosage    : {entry.get('dosage')    or '—'}")

        if entry.get("error"):
            print(f"  ⚠  Error: {entry['error']}")
            continue

        if entry.get("halted"):
            print("  ⚠  Pipeline halted — contraindicated combination or override triggered.")
            _print_duplication_section(entry.get("therapeutic_duplication"))
            print(f"  Warnings:")
            for w in entry.get("warnings", []):
                print(f"    • {w}")
            continue

        # ── Therapeutic Duplication ──────────────────────────────────────────
        _print_duplication_section(entry.get("therapeutic_duplication"))

        # ── Scoring ──────────────────────────────────────────────────────────
        if entry.get("override_triggered"):
            print(f"\n  ⚠  OVERRIDE: {entry['override_rule']}")
            print(f"  Risk total    : {entry.get('risk_total')}")
        else:
            print(f"\n  Benefit total : {entry.get('benefit_total')}")
            print(f"  Risk total    : {entry.get('risk_total')}")
            print(f"  Benefit B/D   : {entry.get('benefit_breakdown')}")
            print(f"  Risk B/D      : {entry.get('risk_breakdown')}")

        print(f"  iBR Score     : {entry.get('ibr_score')}")
        print(f"  iBR Outcome   : {entry.get('ibr_outcome')}")

        if entry.get("warnings"):
            print("  Warnings:")
            for w in entry["warnings"]:
                print(f"    • {w}")

    print("\n" + "=" * 70 + "\n")


def _print_duplication_section(dup: Dict[str, Any] | None) -> None:
    """Prints the therapeutic duplication block inside a drug entry."""
    if not dup:
        return

    total   = dup.get("total_pairs", 0)
    uniq    = dup.get("unique_count", 0)
    dup_cnt = dup.get("duplicate_count", 0)

    print(f"\n  ── Therapeutic Duplication (NICE) ──────────────────────────")
    print(f"     Pairs checked  : {total}  |  Unique: {uniq}  |  Duplicates: {dup_cnt}")
    print(
        f"     Contraindicated: {dup.get('contraindicated_count', 0)}  |  "
        f"Not recommended: {dup.get('not_recommended_count', 0)}  |  "
        f"Conditional: {dup.get('conditional_count', 0)}  |  "
        f"Supported: {dup.get('supported_count', 0)}  |  "
        f"No rationale: {dup.get('no_rationale_count', 0)}"
    )

    # Print each non-unique pair's detail
    for pair in dup.get("pairs", []):
        if pair.get("outcome") == "UNIQUE":
            continue
        print(f"\n     {pair['drug_a']}  ↔  {pair['drug_b']}")
        print(f"     Outcome : {pair['outcome']}")
        if pair.get("duplicate_reason"):
            print(f"     Overlap : {pair['duplicate_reason']}")
        if pair.get("shared_indications"):
            print(f"     Shared  : {', '.join(pair['shared_indications'])}")
        for rule in pair.get("matched_rules", []):
            print(f"     NICE {rule['guideline_code']} §{rule['section_ref']} — {rule['recommendation']}")
            print(f"       {rule['recommendation_text']}")
            if rule.get("conditions"):
                print(f"       Conditions: {'; '.join(rule['conditions'])}")
            print(f"       {rule['url']}")
