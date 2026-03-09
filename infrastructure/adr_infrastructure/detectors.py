import re
from typing import Dict, Any, List

from infrastructure.adr_infrastructure.helpers import (
    _extract_context,
    _deduplicate_adrs,
    _can_patient_be_pregnant,
)


# ── ADR name extraction ───────────────────────────────────────────────────────

def extract_adr_name(context: str, keyword: str) -> str:
    context_lower = context.lower()

    serious_conditions = [
        "lactic acidosis", "metabolic acidosis", "diabetic ketoacidosis",
        "hemorrhagic pancreatitis", "necrotizing pancreatitis", "acute pancreatitis",
        "anaphylaxis", "anaphylactic shock", "anaphylactic reaction", "angioedema",
        "stevens-johnson syndrome", "toxic epidermal necrolysis",
        "respiratory failure", "respiratory arrest",
        "acute liver failure", "hepatic failure", "hepatotoxicity",
        "pulmonary toxicity", "cardiac arrest", "ventricular arrhythmia",
        "torsades de pointes", "agranulocytosis", "neutropenia",
        "aplastic anemia", "renal failure", "acute kidney injury",
        "nephrotoxicity", "ototoxicity", "myocardial infarction",
        "stroke", "pulmonary embolism", "sepsis", "rhabdomyolysis",
        "pancreatitis", "hypoglycemia", "hyperglycemia", "heart failure",
        "ventricular fibrillation", "spontaneous abortion",
    ]
    for condition in serious_conditions:
        if condition in context_lower:
            return condition.title()

    patterns = [
        r"cases of\s+([a-z\s]+?)(?:\s+have|\s+has|\s+may|\.|\s+in)",
        r"risk of\s+([a-z\s]+?)(?:\s+in|\s+and|\.|,)",
        r"may result in\s+([a-z\s]+?)(?:\,|\.|;)",
        r"can cause\s+([a-z\s]+?)(?:\,|\.|;|\s+in)",
    ]
    for pattern in patterns:
        match = re.search(pattern, context_lower)
        if match:
            adr_name = match.group(1).strip()
            if len(adr_name) > 5:
                return adr_name.title()

    return None


def clean_serious_adr_name(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text)
    text = re.sub(r"\[see[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(see[^\)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\d+\.?\d*\)", "", text)
    text = re.sub(r"\[[\d\.]+\]", "", text)
    text = re.sub(r"\s*see\s+section\s+\d+.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*see\s+warnings.*$", "", text, flags=re.IGNORECASE)
    text = text.strip()
    if len(text) < 5:
        return None
    return text.title()


# ── Risk factor patterns (shared by all detectors) ───────────────────────────

RISK_FACTOR_PATTERNS = {
    "renal":           ["renal impairment", "kidney disease", "egfr", "creatinine clearance",
                        "renal dysfunction", "kidney failure", "renal failure", "chronic kidney disease"],
    "hepatic":         ["liver disease", "hepatic impairment", "cirrhosis", "liver failure", "hepatic dysfunction"],
    "cardiac":         ["heart failure", "chf", "cardiac dysfunction", "cardiomyopathy",
                        "congestive heart failure", "ventricular fibrillation", "arrhythmia",
                        "ventricular tachycardia", "atrial fibrillation"],
    "age":             ["elderly", "geriatric", "age", "older patients", "patients over"],
    "metabolic":       ["diabetes", "diabetic", "metabolic acidosis", "hyperglycemia", "hypoglycemia"],
    "respiratory":     ["copd", "asthma", "respiratory disease", "pulmonary disease"],
    "vascular":        ["deep vein thrombosis", "dvt", "pulmonary embolism", "thrombosis", "venous thrombosis"],
    "lipid":           ["hyperlipidemia", "hypertriglyceridemia", "high cholesterol", "dyslipidemia"],
    "gastrointestinal":["gi bleed", "gastrointestinal bleeding", "peptic ulcer", "ulcer"],
    "hematologic":     ["anemia", "thrombocytopenia", "neutropenia", "leukopenia"],
}


def extract_interaction_risk_factors(
    context: str, patient_data: Dict[str, Any]
) -> List[str]:
    patient    = patient_data.get("patient", {})
    context_lower = context.lower()
    risk_factors  = []

    patient_conditions = []
    if patient.get("condition"):
        patient_conditions.append(patient["condition"].lower())
    if patient.get("diagnosis"):
        patient_conditions.append(patient["diagnosis"].lower())
    for history in patient_data.get("MedicalHistory", []):
        if history.get("status") == "Active":
            name = history.get("diagnosisName", "").lower()
            if name:
                patient_conditions.append(name)

    for risk_type, keywords in RISK_FACTOR_PATTERNS.items():
        if any(kw in context_lower for kw in keywords):
            for cond in patient_conditions:
                if any(kw in cond for kw in keywords):
                    risk_factors.append(f"{risk_type} condition")
                    break

    return list(set(risk_factors))


def match_patient_risk_factors(
    adr: Dict[str, Any],
    patient_data: Dict[str, Any],
    fda_sections: Dict[str, Any],
) -> Dict[str, Any]:
    patient       = patient_data.get("patient", {})
    context_lower = adr["context"].lower()

    section_map = {
        "Section 6": "adverse_reactions",
        "Section 5": "warnings_and_cautions",
        "Boxed Warning": "boxed_warning",
    }
    full_text = ""
    for key, field in section_map.items():
        if key in adr.get("section", ""):
            raw = fda_sections.get(field) or fda_sections.get("warnings", "")
            full_text = raw.lower() if raw else ""
            break

    matched_factors = []

    # Age check
    patient_age = patient.get("age", 0)
    if patient_age > 65:
        if any(kw in context_lower or kw in full_text for kw in RISK_FACTOR_PATTERNS["age"]):
            matched_factors.append(f"age >65 (patient age: {patient_age})")

    # Conditions
    patient_conditions = []
    if patient.get("condition"):
        patient_conditions.append(patient["condition"].lower())
    if patient.get("diagnosis"):
        for d in patient["diagnosis"].lower().split(","):
            patient_conditions.append(d.strip())
    for history in patient_data.get("MedicalHistory", []):
        if history.get("status") == "Active":
            name = history.get("diagnosisName", "").lower()
            if name:
                patient_conditions.append(name)

    for condition in patient_conditions:
        for risk_type, keywords in RISK_FACTOR_PATTERNS.items():
            if risk_type == "age":
                continue
            patient_has = any(kw in condition for kw in keywords)
            fda_mentions = any(kw in context_lower or kw in full_text for kw in keywords)
            if patient_has and fda_mentions:
                matched_factors.append(f"{risk_type} condition ({condition})")

    # Deduplicate by prefix
    unique, seen = [], set()
    for factor in matched_factors:
        key = factor.split("(")[0].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(factor)

    return {"has_risk_factors": len(unique) > 0, "matched_factors": unique}
