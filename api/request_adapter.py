"""
api/request_adapter.py

Converts the external API request body into the internal patient_data schema
that all components, adapters, and the bra_assessor expect.

External schema (from API):
    patient.age          → string "42"
    patient.isPregnant   → bool
    patient.gender       → "Female" (capitalised)
    newMedications       → list of drugs under review
    ongoingMedications   → existing medications (indication may be null)
    currentDiagnosis     → active diagnoses with medication names
    pastMedicalConditions → history

Internal schema (what BRAAnalysisEngine / components expect):
    patient_data:
        id, fullName, age (int), gender (lowercase),
        pregnancy_info: { pregnancy_status, lactation }
        chiefComplaint, currentDiagnosis, pastMedicalConditions,
        allergies, ongoingMedications
    drug_data:
        name, condition
"""

from typing import Dict, Any, List, Tuple
import re


def _normalize_drug_name(drug_name: str) -> str:
    """
    Strips dosage strength and dosage form from a drug name string.
    Self-contained — no external imports needed.
    "Diclofenac 50 MG Oral Tablet" → "Diclofenac"
    "Metformin"                    → "Metformin"  (unchanged)
    """
    name = re.sub(r'\d+(\d+)?\s*(mg|ml|g|%|mcg|iu|units?)', '', drug_name, flags=re.IGNORECASE)
    name = re.sub(
        r'\b(oral|tablet|capsule|injection|cream|ointment|gel|solution|'
        r'suspension|patch|spray|inhaler|drop|syrup|powder|suppository|'
        r'lozenge|vial|film|liquid|foam|extended.release|immediate.release)\b',
        '', name, flags=re.IGNORECASE
    )
    name = re.sub(r'\s+', ' ', name).strip().strip(',').strip()
    return name or drug_name.strip()


def adapt_request(body: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """
    Parses the full API request body.

    Returns
    -------
    patient_data : dict
        Internal patient_data format used by all components.
    new_medications : list of {name, condition}
        One entry per newMedication — each will be one engine run.
    """
    patient_raw = body.get("patient", {})

    # ── Age: normalise string → int ───────────────────────────────────────────
    age_raw = patient_raw.get("age", 0)
    try:
        age = int(age_raw)
    except (ValueError, TypeError):
        age = 0

    # ── Gender: normalise to lowercase ────────────────────────────────────────
    gender = patient_raw.get("gender", "").lower()

    # ── Pregnancy: map isPregnant bool → pregnancy_info dict ─────────────────
    is_pregnant  = patient_raw.get("isPregnant", False)
    pregnancy_info = {
        "pregnancy_status": "Ongoing Pregnancy" if is_pregnant else "Not Applicable",
        "lactation":        "No",
        "Trimester":        patient_raw.get("trimester"),
    }

    # ── ongoingMedications: fill missing indication from chiefComplaint ───────
    chief_complaint = patient_raw.get("chiefComplaint", "")
    ongoing_meds = []
    for med in patient_raw.get("ongoingMedications", []):
        ongoing_meds.append({
            "name":      med.get("name", ""),
            "dosage":    med.get("dosage", ""),
            "indication": med.get("indication") or chief_complaint,
        })

    # ── Assemble internal patient_data ────────────────────────────────────────
    patient_data = {
        "id":                   patient_raw.get("id", ""),
        "fullName":             patient_raw.get("fullName", ""),
        "age":                  age,
        "gender":               gender,
        "chiefComplaint":       chief_complaint,
        "pregnancy_info":       pregnancy_info,
        "currentDiagnosis":     patient_raw.get("currentDiagnosis", []),
        "pastMedicalConditions": patient_raw.get("pastMedicalConditions", []),
        "allergies":            patient_raw.get("allergies", []),
        "ongoingMedications":   ongoing_meds,
        # Pass through extras for context
        "mrn":                  patient_raw.get("mrn", ""),
        "lifestyleSocialHistory": patient_raw.get("lifestyleSocialHistory", ""),
        "familyHistory":        patient_raw.get("familyHistory", ""),
    }

    # ── newMedications → list of drug_data dicts ──────────────────────────────
    # condition is inferred from currentDiagnosis names since newMedications
    # don't carry their own indication in the request body.
    diagnosis_names = [
        dx.get("name", "")
        for dx in patient_raw.get("currentDiagnosis", [])
        if dx.get("name")
    ]
    # Fallback chain: currentDiagnosis names → chiefComplaint → "General"
    # An empty condition causes ApprovalStatus and other components to skip
    # the primary drug entirely, halting the pipeline.
    inferred_condition = (
        ", ".join(diagnosis_names)
        if diagnosis_names
        else (chief_complaint.strip() or "General")
    )

    new_medications: List[Dict[str, str]] = []
    seen_meds: set = set()
    for med in body.get("newMedications", []):
        raw_name = med.get("name", "").strip()
        if not raw_name:
            continue
        # Strip dosage/form suffix so FDA APIs receive just the active ingredient.
        # "Diclofenac 50 MG Oral Tablet" -> "Diclofenac"
        clean_name = _normalize_drug_name(raw_name)
        # Deduplicate — skip if same clean name already added
        if clean_name.lower() in seen_meds:
            continue
        seen_meds.add(clean_name.lower())
        new_medications.append({
            "name":      clean_name,
            "raw_name":  raw_name,
            "dosage":    med.get("dosage", ""),
            "condition": inferred_condition,
        })

    return patient_data, new_medications
