"""
bra_assessor.py — Per-Medicine Assessment Runner

CORRECT DESIGN:
  - The full BRA engine runs ONLY on newMedications (drugs under review).
  - Background medicines in patient_data are CONTEXT only.
  - assess() runs engine.execute() once per new_medication entry.
  - All 6 benefit/risk factor results + structured RMM summary + patient
    safety sheet are extracted and returned.

RMM Summary structure (matches Image 1):
  Grouped by medicine → each medicine has:
    risk, lab_tests, symptoms_to_monitor, actions_required

Patient Safety Sheet (matches Image 2):
  Generated via Claude API — patient-readable numbered list:
    1. Lab tests to perform (with frequency)
    2. Symptoms to monitor and report
"""

import json
import requests
from typing import Dict, Any, List
from main import build_engine


# ── Claude API call ───────────────────────────────────────────────────────────

def _call_claude(prompt: str) -> str:
    """Calls Claude claude-sonnet-4-6 and returns the text response."""
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        data = response.json()
        content = data.get("content", [])
        return " ".join(block.get("text", "") for block in content if block.get("type") == "text").strip()
    except Exception as exc:
        print(f"  [PatientSafetySheet] Claude API error: {exc}")
        return ""


# ── Per-component metadata extractors ─────────────────────────────────────────

def _extract_contraindication(meta: dict) -> dict:
    return {
        "output":       meta.get("output", ""),
        "overall_safe": meta.get("overall_safe", True),
        "summary":      meta.get("summary", {}),
        "flagged_drugs": meta.get("flagged_drugs", []),
        "all_entries":  meta.get("all_entries", []),
    }


def _extract_approval_status(meta: dict) -> dict:
    return {
        "output":  meta.get("output", ""),
        "summary": meta.get("summary", {}),
        "entries": meta.get("entries", []),
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
        "output":                  meta.get("output", ""),
        "adr_severity_category":   meta.get("adr_severity_category", ""),
        "interaction_category":    meta.get("interaction_category", ""),
        "lt_with_risk_factors":    meta.get("lt_with_risk_factors", 0),
        "lt_without_risk_factors": meta.get("lt_without_risk_factors", 0),
        "serious_with_risk":       meta.get("serious_with_risk", 0),
        "serious_without_risk":    meta.get("serious_without_risk", 0),
        "interaction_count":       meta.get("interaction_count", 0),
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
        "output":                  meta.get("output", ""),
        "preventability_category": meta.get("preventability_category", ""),
        "reversibility_category":  meta.get("reversibility_category", ""),
        "irreversible_count":      meta.get("irreversible_count", 0),
        "non_preventable_count":   meta.get("non_preventable_count", 0),
        "total_adrs_analyzed":     meta.get("total_adrs_analyzed", 0),
    }


def _extract_disease_severity(meta: dict) -> dict:
    return {
        "output":                 meta.get("output", ""),
        "severity_category":      meta.get("severity_category", ""),
        "diagnoses_analyzed":     meta.get("diagnoses_analyzed", []),
        "per_disease_categories": meta.get("per_disease_categories", []),
    }


_COMPONENT_EXTRACTORS = {
    "Contraindication":     _extract_contraindication,
    "MME":                  _extract_mme,
    "TherapeuticDuplication": _extract_therapeutic_duplication,
    "ApprovalStatus":       _extract_approval_status,
    "ADRAnalysis":          _extract_adr_analysis,
    "RMM":                  _extract_rmm,
    "PubMed":               _extract_pubmed,
    "Alternatives":         _extract_alternatives,
    "RiskMitigation":       _extract_risk_mitigation,
    "DiseaseSeverity":      _extract_disease_severity,
}


def _extract_all_components(context) -> Dict[str, Any]:
    components = {}
    for name, result in context.component_results.items():
        meta = result.metadata or {}
        extractor = _COMPONENT_EXTRACTORS.get(name)
        components[name] = extractor(meta) if extractor else meta
    return components


def _build_factor_summary(components: Dict[str, Any], fs: dict) -> dict:
    bd = fs.get("benefit_breakdown", {})
    rd = fs.get("risk_breakdown", {})
    return {
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
        "B3_StrengthOfEvidence": {
            "score":  bd.get("B3_StrengthOfEvidence"),
            "detail": components.get("PubMed", {}),
        },
        "B4_TherapeuticDuplication": {
            "score":    bd.get("B4_TherapeuticDuplication"),
            "category": components.get("TherapeuticDuplication", {}).get("duplication_category"),
            "detail":   components.get("TherapeuticDuplication", {}),
        },
        "B5_Alternatives": {
            "score":  bd.get("B5_Alternatives"),
            "detail": components.get("Alternatives", {}),
        },
        "B6_DiseaseSeverity": {
            "score":    bd.get("B6_DiseaseSeverity"),
            "category": components.get("DiseaseSeverity", {}).get("severity_category"),
            "detail":   components.get("DiseaseSeverity", {}),
        },
        "R1_Contraindication": {
            "score":    rd.get("R1_Contraindication") or (fs.get("risk_total") if fs.get("override_triggered") else 0),
            "override": fs.get("override_triggered", False),
            "detail":   components.get("Contraindication", {}),
        },
        "R2_Interactions": {
            "score":    rd.get("R2_Interactions"),
            "category": components.get("ADRAnalysis", {}).get("interaction_category"),
            "detail": {
                "interaction_category": components.get("ADRAnalysis", {}).get("interaction_category"),
                "interaction_count":    components.get("ADRAnalysis", {}).get("interaction_count"),
                "output":               components.get("ADRAnalysis", {}).get("output"),
            },
        },
        "R3_ADRSeverity": {
            "score":    rd.get("R3_ADRSeverity"),
            "category": components.get("ADRAnalysis", {}).get("adr_severity_category"),
            "detail": {
                "adr_severity_category":   components.get("ADRAnalysis", {}).get("adr_severity_category"),
                "lt_with_risk_factors":    components.get("ADRAnalysis", {}).get("lt_with_risk_factors"),
                "lt_without_risk_factors": components.get("ADRAnalysis", {}).get("lt_without_risk_factors"),
                "serious_with_risk":       components.get("ADRAnalysis", {}).get("serious_with_risk"),
                "serious_without_risk":    components.get("ADRAnalysis", {}).get("serious_without_risk"),
                "output":                  components.get("ADRAnalysis", {}).get("output"),
            },
        },
        "R4_RiskPreventability": {
            "score":    rd.get("R4_RiskPreventability"),
            "category": components.get("RiskMitigation", {}).get("preventability_category"),
            "detail": {
                "preventability_category": components.get("RiskMitigation", {}).get("preventability_category"),
                "non_preventable_count":   components.get("RiskMitigation", {}).get("non_preventable_count"),
                "total_adrs_analyzed":     components.get("RiskMitigation", {}).get("total_adrs_analyzed"),
                "output":                  components.get("RiskMitigation", {}).get("output"),
            },
        },
        "R5_RiskReversibility": {
            "score":    rd.get("R5_RiskReversibility"),
            "category": components.get("RiskMitigation", {}).get("reversibility_category"),
            "detail": {
                "reversibility_category": components.get("RiskMitigation", {}).get("reversibility_category"),
                "irreversible_count":     components.get("RiskMitigation", {}).get("irreversible_count"),
                "total_adrs_analyzed":    components.get("RiskMitigation", {}).get("total_adrs_analyzed"),
                "output":                 components.get("RiskMitigation", {}).get("output"),
            },
        },
    }


# ── RMM Summary ───────────────────────────────────────────────────────────────

def _build_rmm_summary(rmm_data: dict) -> dict:
    """
    Restructures the flat RMM table into the grouped-by-medicine format
    matching Image 1:

    {
        "total_entries": int,
        "lt_entries": int,
        "serious_entries": int,
        "by_medicine": [
            {
                "medicine": "Amlodipine",
                "risks": [
                    {
                        "risk": "Heart Failure",
                        "risk_type": "LT/Fatal ADR",
                        "lab_tests": "...",           ← from section_5_warnings
                        "symptoms_to_monitor": [...], ← parsed from proactive_actions
                        "actions_required": "...",    ← immediate_actions_required
                        "actions_reasoning": "...",   ← immediate_actions_reasoning
                        "fda_warning_extract": "...", ← section_5_warnings_and_precautions_extract
                    },
                    ...
                ]
            },
            ...
        ]
    }
    """
    rmm_table = rmm_data.get("rmm_table", [])
    total     = rmm_data.get("total_entries", len(rmm_table))
    lt_count  = rmm_data.get("lt_entries", sum(1 for e in rmm_table if "LT" in e.get("risk_type", "")))

    # Group entries by medicine name
    medicine_map: Dict[str, List[dict]] = {}
    for entry in rmm_table:
        med = entry.get("medicine", "Unknown")
        if med not in medicine_map:
            medicine_map[med] = []

        # Parse symptoms into a clean list
        raw_symptoms = entry.get("proactive_actions_symptoms_to_monitor", "")
        symptoms_list = [s.strip() for s in raw_symptoms.split(",") if s.strip()] if raw_symptoms else []

        # Extract lab tests from section_5 text — if it contains "lab" or "monitor" keywords
        # Otherwise use a cleaned version of the FDA extract
        fda_extract = entry.get("section_5_warnings_and_precautions_extract", "")
        lab_tests = _extract_lab_tests(fda_extract, entry.get("risk_description", ""))

        medicine_map[med].append({
            "risk":               entry.get("risk_description", ""),
            "risk_type":          entry.get("risk_type", ""),
            "lab_tests":          lab_tests,
            "symptoms_to_monitor": symptoms_list,
            "actions_required":   entry.get("immediate_actions_required", ""),
            "actions_reasoning":  entry.get("immediate_actions_reasoning", ""),
            "fda_warning_extract": fda_extract if fda_extract and fda_extract != "NA" else "",
        })

    by_medicine = [
        {"medicine": med, "risks": risks}
        for med, risks in medicine_map.items()
    ]

    return {
        "total_entries":   total,
        "lt_entries":      lt_count,
        "serious_entries": total - lt_count,
        "by_medicine":     by_medicine,   # grouped by medicine (for accordion UI)
        "table":           rmm_table,     # flat raw table (all entries)
    }


def _extract_lab_tests(fda_extract: str, risk_description: str) -> str:
    """
    Derives a lab test recommendation from the FDA label extract and risk type.
    Falls back to risk-based defaults for well-known ADRs.
    """
    if fda_extract and fda_extract != "NA":
        lower = fda_extract.lower()
        if any(k in lower for k in ["lab", "monitor", "test", "serum", "ecg", "blood"]):
            # Return first meaningful sentence containing a lab keyword
            for sentence in fda_extract.split("."):
                if any(k in sentence.lower() for k in ["lab", "monitor", "test", "serum", "ecg", "blood"]):
                    return sentence.strip() + "."

    # Risk-based defaults for common ADRs
    risk_lower = risk_description.lower()
    defaults = {
        "heart failure":    "BNP / NT-proBNP, echocardiogram, chest X-ray, serum electrolytes",
        "hepatic failure":  "LFTs (ALT, AST, bilirubin, ALP) every 2 weeks",
        "stroke":           "Blood pressure monitoring, platelet count, coagulation studies",
        "renal failure":    "Serum creatinine, eGFR, urine output monitoring",
        "hyperkalaemia":    "Serum potassium every 2–4 days",
        "gi bleed":         "FBC, haemoglobin, stool occult blood test",
        "lactic acidosis":  "Serum lactate, arterial blood gas",
        "anaphylaxis":      "No routine lab test — clinical monitoring required",
        "ototoxicity":      "Audiometry baseline and periodic hearing tests",
        "pulmonary":        "Chest X-ray, pulmonary function tests",
    }
    for keyword, lab in defaults.items():
        if keyword in risk_lower:
            return lab
    return "Routine clinical monitoring as per prescriber guidance"


# ── Patient Safety Sheet ──────────────────────────────────────────────────────

def _generate_patient_safety_sheet(
    rmm_table: List[dict],
    drug_name: str,
    patient_data: dict,
) -> dict:
    """
    Calls Claude claude-sonnet-4-6 to generate a patient-readable safety sheet
    matching Image 2:

    {
        "lab_tests": [
            { "test": "Liver function tests", "frequency": "every 2 weeks" },
            { "test": "Serum electrolytes",   "frequency": "every week" }
        ],
        "symptoms_to_monitor": [
            "Muscle weakness, numbness/tingling, nausea...",
            ...
        ],
        "summary_text": "Full patient-readable paragraph"
    }
    """
    if not rmm_table:
        return {
            "lab_tests": [],
            "symptoms_to_monitor": [],
            "summary_text": "No specific monitoring requirements identified.",
        }

    # Build a compact summary of all RMM entries for the prompt
    rmm_lines = []
    for entry in rmm_table:
        rmm_lines.append(
            f"- Medicine: {entry.get('medicine')} | "
            f"Risk: {entry.get('risk_description')} | "
            f"Symptoms: {entry.get('proactive_actions_symptoms_to_monitor', '')} | "
            f"Action: {entry.get('immediate_actions_required', '')}"
        )

    patient_age    = patient_data.get("age", "")
    patient_gender = patient_data.get("gender", "")
    diagnoses      = ", ".join(
        dx.get("name", "") for dx in patient_data.get("currentDiagnosis", []) if dx.get("name")
    )

    prompt = f"""You are a clinical pharmacist creating a patient safety sheet.

Patient: {patient_age}-year-old {patient_gender}, diagnosed with: {diagnoses}
New medication being assessed: {drug_name}

Risk Monitoring Requirements (from FDA labels):
{chr(10).join(rmm_lines)}

Generate a patient safety sheet in the following JSON format ONLY — no preamble, no markdown, no explanation:
{{
  "lab_tests": [
    {{"test": "<test name>", "frequency": "<how often>"}}
  ],
  "symptoms_to_monitor": [
    "<symptom group 1>",
    "<symptom group 2>"
  ],
  "summary_text": "<2-3 sentence plain-language summary for the patient>"
}}

Rules:
- Deduplicate — if the same lab test or symptom appears for multiple medicines, list it once
- Group related symptoms together (e.g. cardiac symptoms in one item, hepatic in another)
- Use plain language a patient can understand
- lab_tests: include only tests that require scheduling (exclude clinical observation)
- symptoms_to_monitor: max 4 items, each a comma-separated list of related symptoms
- summary_text: tell the patient what to do and when to contact their doctor
- Return ONLY the JSON object, nothing else"""

    print(f"  [PatientSafetySheet] Generating for '{drug_name}'...")
    raw = _call_claude(prompt)

    if not raw:
        return _fallback_patient_safety_sheet(rmm_table)

    # Strip any accidental markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    try:
        parsed = json.loads(raw)
        # Validate expected keys exist
        return {
            "lab_tests":           parsed.get("lab_tests", []),
            "symptoms_to_monitor": parsed.get("symptoms_to_monitor", []),
            "summary_text":        parsed.get("summary_text", ""),
        }
    except (json.JSONDecodeError, Exception) as exc:
        print(f"  [PatientSafetySheet] JSON parse error: {exc} — using fallback")
        return _fallback_patient_safety_sheet(rmm_table)


def _fallback_patient_safety_sheet(rmm_table: List[dict]) -> dict:
    """Fallback when Claude API is unavailable — derives from RMM table directly."""
    all_symptoms: List[str] = []
    lab_tests_seen: set = set()
    lab_tests: List[dict] = []

    for entry in rmm_table:
        raw = entry.get("proactive_actions_symptoms_to_monitor", "")
        if raw:
            all_symptoms.extend([s.strip() for s in raw.split(",") if s.strip()])

        risk = entry.get("risk_description", "").lower()
        lab  = _extract_lab_tests("", risk)
        if lab and lab not in lab_tests_seen:
            lab_tests_seen.add(lab)
            lab_tests.append({"test": lab, "frequency": "as directed by your doctor"})

    # Deduplicate symptoms and group into max 3 items
    seen_symptoms: set = set()
    unique_symptoms: List[str] = []
    for s in all_symptoms:
        if s.lower() not in seen_symptoms:
            seen_symptoms.add(s.lower())
            unique_symptoms.append(s)

    grouped = [", ".join(unique_symptoms[i:i+5]) for i in range(0, min(len(unique_symptoms), 15), 5)]

    return {
        "lab_tests":           lab_tests[:4],
        "symptoms_to_monitor": grouped[:4],
        "summary_text": (
            "Please follow up with your healthcare provider as scheduled. "
            "Report any new or worsening symptoms immediately, "
            "especially those listed above."
        ),
    }


# ── Main assess function ──────────────────────────────────────────────────────

def assess(patient_data: dict, new_medications: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Runs the full BRA pipeline once per new medication under review.
    Returns structured per-medicine results including:
      - All 9 iBR factors (B1-B6, R1-R5) with scores and detail
      - rmm_summary: grouped by medicine (matches RMM Summary image)
      - patient_safety_sheet: patient-readable summary (matches Safety Sheet image)
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
                "drug":      drug_name,
                "condition": med.get("condition", ""),
                "dosage":    med.get("dosage", ""),
                "error":     "Engine returned no context",
                "halted":    True,
            }
            unfavourable.append(drug_name)
            continue

        fs = context.final_score or {}
        halted = fs.get("ibr_score") is None

        components = _extract_all_components(context)
        factors    = _build_factor_summary(components, fs)

        # ── Structured RMM summary (grouped by medicine) ─────────────────────
        rmm_summary = _build_rmm_summary(components.get("RMM", {}))

        # ── Patient safety sheet (Claude-generated) ───────────────────────────
        raw_rmm_table = components.get("RMM", {}).get("rmm_table", [])
        patient_safety_sheet = _generate_patient_safety_sheet(
            rmm_table=raw_rmm_table,
            drug_name=drug_name,
            patient_data=patient_data,
        )

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
            "factors":            factors,
            "rmm_summary":        rmm_summary,
            "patient_safety_sheet": patient_safety_sheet,
            "components":         components,
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

        print(f"  iBR Score   : {entry.get('ibr_score')}")
        print(f"  iBR Outcome : {entry.get('ibr_outcome')}")

        rmm = entry.get("rmm_summary", {})
        print(f"\n  RMM Summary: {rmm.get('total_entries', 0)} entries")
        for med_block in rmm.get("by_medicine", []):
            print(f"    [{med_block['medicine']}]")
            for risk in med_block.get("risks", []):
                print(f"      Risk: {risk['risk']}")
                print(f"      Symptoms: {', '.join(risk['symptoms_to_monitor'][:3])}")
                print(f"      Action: {risk['actions_required']}")

        pss = entry.get("patient_safety_sheet", {})
        if pss.get("lab_tests") or pss.get("symptoms_to_monitor"):
            print("\n  Patient Safety Sheet:")
            for lt in pss.get("lab_tests", []):
                print(f"    Lab: {lt.get('test')} — {lt.get('frequency')}")
            for sym in pss.get("symptoms_to_monitor", []):
                print(f"    Monitor: {sym[:80]}")

        factors = entry.get("factors", {})
        if factors:
            print("\n  Factor scores:")
            for factor, data in factors.items():
                print(f"    {factor}: score={data.get('score')}  category={data.get('category', '')}")

        if entry.get("warnings"):
            print("  Warnings:")
            for w in entry["warnings"]:
                print(f"    • {w}")

    print("\n" + "=" * 70 + "\n")
