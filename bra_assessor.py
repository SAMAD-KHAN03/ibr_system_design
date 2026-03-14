"""
bra_assessor.py — Per-Medicine Assessment Runner

CORRECT DESIGN:
  - The full BRA engine runs ONLY on newMedications (drugs under review).
  - Background medicines in patient_data are CONTEXT only — used internally
    by components for ADR/interaction checks, never independently assessed.
  - assess() runs engine.execute() once per new_medication entry.
  - All 6 benefit/risk factor results + RMM table are extracted in full
    structured form from each component's metadata.
"""

from typing import Dict, Any, List
from main import build_engine


# ── Per-component metadata extractors ────────────────────────────────────────
# Each function pulls the full structured data from a component's metadata dict.
# This is the single place to update if a component's metadata schema changes.

def _extract_contraindication(meta: dict) -> dict:
    return {
        "output":                meta.get("output", ""),
        "overall_safe":          meta.get("overall_safe", True),
        "summary":               meta.get("summary", {}),
        "flagged_drugs":         meta.get("flagged_drugs", []),
        "all_entries":           meta.get("all_entries", []),
    }


def _extract_approval_status(meta: dict) -> dict:
    return {
        "output":   meta.get("output", ""),
        "summary":  meta.get("summary", {}),
        "entries":  meta.get("entries", []),
    }


def _extract_mme(meta: dict) -> dict:
    return {
        "output":        meta.get("output", ""),
        "mme_category":  meta.get("mme_category", ""),
        "generic_name":  meta.get("generic_name"),
        "approval_date": meta.get("approval_date"),
        "years":         meta.get("years"),
        "found":         meta.get("found", False),
        "threshold":     meta.get("threshold", 5),
    }


def _extract_therapeutic_duplication(meta: dict) -> dict:
    return {
        "output":                meta.get("output", ""),
        "duplication_category":  meta.get("duplication_category", ""),
        "total_pairs":           meta.get("total_pairs", 0),
        "unique_count":          meta.get("unique_count", 0),
        "duplicate_count":       meta.get("duplicate_count", 0),
        "supported_count":       meta.get("supported_count", 0),
        "conditional_count":     meta.get("conditional_count", 0),
        "not_recommended_count": meta.get("not_recommended_count", 0),
        "contraindicated_count": meta.get("contraindicated_count", 0),
        "no_rationale_count":    meta.get("no_rationale_count", 0),
        "has_contraindication":  meta.get("has_contraindication", False),
        "pairs":                 meta.get("pairs", []),
        "summary_lines":         meta.get("summary_lines", []),
    }


def _extract_adr_analysis(meta: dict) -> dict:
    return {
        "output":                    meta.get("output", ""),
        "adr_severity_category":     meta.get("adr_severity_category", ""),
        "interaction_category":      meta.get("interaction_category", ""),
        "lt_with_risk_factors":      meta.get("lt_with_risk_factors", 0),
        "lt_without_risk_factors":   meta.get("lt_without_risk_factors", 0),
        "serious_with_risk":         meta.get("serious_with_risk", 0),
        "serious_without_risk":      meta.get("serious_without_risk", 0),
        "interaction_count":         meta.get("interaction_count", 0),
    }


def _extract_rmm(meta: dict) -> dict:
    return {
        "output":        meta.get("output", ""),
        "total_entries": meta.get("total_entries", 0),
        "lt_entries":    meta.get("lt_entries", 0),
        "rmm_table":     meta.get("rmm_table", []),
    }


def _extract_pubmed(meta: dict) -> dict:
    return {
        "output":  meta.get("output", ""),
        "summary": meta.get("summary", {}),
        "entries": meta.get("entries", []),
    }


def _extract_alternatives(meta: dict) -> dict:
    return {
        "output":             meta.get("output", ""),
        "total_alternatives": meta.get("total_alternatives", 0),
        "entries":            meta.get("entries", []),
    }


def _extract_risk_mitigation(meta: dict) -> dict:
    return {
        "output":                   meta.get("output", ""),
        "preventability_category":  meta.get("preventability_category", ""),
        "reversibility_category":   meta.get("reversibility_category", ""),
        "irreversible_count":        meta.get("irreversible_count", 0),
        "non_preventable_count":     meta.get("non_preventable_count", 0),
        "total_adrs_analyzed":       meta.get("total_adrs_analyzed", 0),
    }


def _extract_disease_severity(meta: dict) -> dict:
    return {
        "output":                 meta.get("output", ""),
        "severity_category":      meta.get("severity_category", ""),
        "diagnoses_analyzed":     meta.get("diagnoses_analyzed", []),
        "per_disease_categories": meta.get("per_disease_categories", []),
    }


# Map component name → extractor function
_COMPONENT_EXTRACTORS = {
    "Contraindication": _extract_contraindication,
    "MME":              _extract_mme,
    "TherapeuticDuplication": _extract_therapeutic_duplication,
    "ApprovalStatus":   _extract_approval_status,
    "ADRAnalysis":      _extract_adr_analysis,
    "RMM":              _extract_rmm,
    "PubMed":           _extract_pubmed,
    "Alternatives":     _extract_alternatives,
    "RiskMitigation":   _extract_risk_mitigation,
    "DiseaseSeverity":  _extract_disease_severity,
}


def _extract_all_components(context) -> Dict[str, Any]:
    """
    Extracts full structured data from every component result in context.
    Returns a dict keyed by component name, each value is the structured output.
    """
    components = {}
    for name, result in context.component_results.items():
        meta = result.metadata or {}
        extractor = _COMPONENT_EXTRACTORS.get(name)
        if extractor:
            components[name] = extractor(meta)
        else:
            # Unknown component — fall back to full metadata passthrough
            components[name] = meta
    return components


def _build_factor_summary(components: Dict[str, Any], fs: dict) -> dict:
    """
    Builds a clean per-factor summary matching the iBR sheet B1-B6, R1-R5.
    Makes it easy for the frontend to render each factor independently.
    """
    bd = fs.get("benefit_breakdown", {})
    rd = fs.get("risk_breakdown", {})

    return {
        # ── Benefit factors ──────────────────────────────────────────────────
        "B1_ApprovalStatus": {
            "score":    bd.get("B1_ApprovalStatus"),
            "category": components.get("ApprovalStatus", {}).get("summary", {}).get("approved_count"),
            "detail":   components.get("ApprovalStatus", {}),
        },
        "B2_MME": {
            "score":    bd.get("B2_MME"),
            "category": components.get("MME", {}).get("mme_category"),
            "detail":   components.get("MME", {}),
        },
        "B4_TherapeuticDuplication": {
            "score":    bd.get("B4_TherapeuticDuplication"),
            "category": components.get("TherapeuticDuplication", {}).get("duplication_category"),
            "detail":   components.get("TherapeuticDuplication", {}),
        },
        "B3_StrengthOfEvidence": {
            "score":    bd.get("B3_StrengthOfEvidence"),
            "detail":   components.get("PubMed", {}),
        },
        "B5_Alternatives": {
            "score":    bd.get("B5_Alternatives"),
            "detail":   components.get("Alternatives", {}),
        },
        "B6_DiseaseSeverity": {
            "score":    bd.get("B6_DiseaseSeverity"),
            "category": components.get("DiseaseSeverity", {}).get("severity_category"),
            "detail":   components.get("DiseaseSeverity", {}),
        },
        # ── Risk factors ─────────────────────────────────────────────────────
        "R1_Contraindication": {
            "score":    rd.get("R1_Contraindication") or (fs.get("risk_total") if fs.get("override_triggered") else 0),
            "override": fs.get("override_triggered", False),
            "detail":   components.get("Contraindication", {}),
        },
        "R2_Interactions": {
            "score":    rd.get("R2_Interactions"),
            "category": components.get("ADRAnalysis", {}).get("interaction_category"),
            "detail":   {
                "interaction_category": components.get("ADRAnalysis", {}).get("interaction_category"),
                "interaction_count":    components.get("ADRAnalysis", {}).get("interaction_count"),
                "output":               components.get("ADRAnalysis", {}).get("output"),
            },
        },
        "R3_ADRSeverity": {
            "score":    rd.get("R3_ADRSeverity"),
            "category": components.get("ADRAnalysis", {}).get("adr_severity_category"),
            "detail":   {
                "adr_severity_category":    components.get("ADRAnalysis", {}).get("adr_severity_category"),
                "lt_with_risk_factors":     components.get("ADRAnalysis", {}).get("lt_with_risk_factors"),
                "lt_without_risk_factors":  components.get("ADRAnalysis", {}).get("lt_without_risk_factors"),
                "serious_with_risk":        components.get("ADRAnalysis", {}).get("serious_with_risk"),
                "serious_without_risk":     components.get("ADRAnalysis", {}).get("serious_without_risk"),
                "output":                   components.get("ADRAnalysis", {}).get("output"),
            },
        },
        "R4_RiskPreventability": {
            "score":    rd.get("R4_RiskPreventability"),
            "category": components.get("RiskMitigation", {}).get("preventability_category"),
            "detail":   {
                "preventability_category": components.get("RiskMitigation", {}).get("preventability_category"),
                "non_preventable_count":   components.get("RiskMitigation", {}).get("non_preventable_count"),
                "total_adrs_analyzed":     components.get("RiskMitigation", {}).get("total_adrs_analyzed"),
                "output":                  components.get("RiskMitigation", {}).get("output"),
            },
        },
        "R5_RiskReversibility": {
            "score":    rd.get("R5_RiskReversibility"),
            "category": components.get("RiskMitigation", {}).get("reversibility_category"),
            "detail":   {
                "reversibility_category": components.get("RiskMitigation", {}).get("reversibility_category"),
                "irreversible_count":     components.get("RiskMitigation", {}).get("irreversible_count"),
                "total_adrs_analyzed":    components.get("RiskMitigation", {}).get("total_adrs_analyzed"),
                "output":                 components.get("RiskMitigation", {}).get("output"),
            },
        },
    }


def _build_rmm_summary(rmm_data: dict) -> dict:
    """
    Builds the RMM summary section from RMM component data.
    Mirrors the format from the previous working system.
    """
    rmm_table = rmm_data.get("rmm_table", [])
    total     = rmm_data.get("total_entries", len(rmm_table))
    lt_count  = rmm_data.get("lt_entries", sum(1 for e in rmm_table if "LT" in e.get("risk_type", "")))

    return {
        "total_entries":          total,
        "lt_entries":             lt_count,
        "serious_entries":        total - lt_count,
        "output":                 rmm_data.get("output", ""),
        "table":                  rmm_table,
    }


# ── Main assess function ──────────────────────────────────────────────────────

def assess(patient_data: dict, new_medications: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Runs the full BRA pipeline once per new medication under review.

    Parameters
    ----------
    patient_data    : internal patient schema (after request_adapter)
    new_medications : list of {name, condition, dosage}

    Returns
    -------
    {
        "per_medicine": {
            "<drug_name>": {
                "drug":              str,
                "condition":         str,
                "dosage":            str,
                "ibr_score":         float | None,
                "ibr_outcome":       str | None,
                "benefit_total":     float | None,
                "risk_total":        float | None,
                "benefit_breakdown": { B1, B3, B5, B6 scores },
                "risk_breakdown":    { R2, R3, R4, R5 scores },
                "max_benefit":       float | None,
                "max_risk":          float | None,
                "override_triggered": bool,
                "override_rule":     str | None,
                "factors":           { B1, B3, B5, B6, R1, R2, R3, R4, R5 structured },
                "rmm_summary":       { total, lt_count, table[] },
                "components":        { full metadata per component },
                "warnings":          list[str],
                "halted":            bool,
            }
        },
        "summary": { ... }
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
                "drug":    drug_name,
                "condition": med.get("condition", ""),
                "dosage":  med.get("dosage", ""),
                "error":   "Engine returned no context",
                "halted":  True,
            }
            unfavourable.append(drug_name)
            continue

        fs = context.final_score or {}
        halted = fs.get("ibr_score") is None

        # Extract full structured data from every component
        components = _extract_all_components(context)

        # Build per-factor view (B1-B6, R1-R5)
        factors = _build_factor_summary(components, fs)

        # Build RMM summary section
        rmm_summary = _build_rmm_summary(components.get("RMM", {}))

        entry = {
            "drug":               drug_name,
            "raw_name":           med.get("raw_name", drug_name),
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
            "factors":            factors,       # ← full B1-B6 R1-R5 structured
            "rmm_summary":        rmm_summary,   # ← full RMM table + summary
            "components":         components,    # ← raw component outputs passthrough
            "warnings":           context.warnings,
            "halted":             halted,
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
            for w in entry.get("warnings", []):
                print(f"    • {w}")
            continue

        if entry.get("override_triggered"):
            print(f"  ⚠  OVERRIDE: {entry['override_rule']}")
            print(f"  Risk total    : {entry.get('risk_total')}")
        else:
            print(f"  Benefit total : {entry.get('benefit_total')} / {entry.get('max_benefit')}")
            print(f"  Risk total    : {entry.get('risk_total')} / {entry.get('max_risk')}")
            print(f"  Benefit B/D   : {entry.get('benefit_breakdown')}")
            print(f"  Risk B/D      : {entry.get('risk_breakdown')}")

        print(f"  iBR Score   : {entry.get('ibr_score')}")
        print(f"  iBR Outcome : {entry.get('ibr_outcome')}")

        rmm = entry.get("rmm_summary", {})
        if rmm.get("total_entries"):
            print(f"\n  RMM: {rmm['total_entries']} entries ({rmm['lt_entries']} LT, {rmm['serious_entries']} serious)")

        factors = entry.get("factors", {})
        if factors:
            print("\n  Factor scores:")
            for factor, data in factors.items():
                score = data.get("score")
                cat   = data.get("category", "")
                print(f"    {factor}: score={score}  category={cat}")

        if entry.get("warnings"):
            print("  Warnings:")
            for w in entry["warnings"]:
                print(f"    • {w}")

    print("\n" + "=" * 70 + "\n")
