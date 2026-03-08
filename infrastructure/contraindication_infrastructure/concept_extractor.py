from typing import Set


# ── Concept map: keyword fragments → canonical concept name ─────────────────
# Extend this dict to add new concepts without touching any other file.

_KEYWORD_MAP: dict[str, list[str]] = {
    "PREGNANCY":              ["pregnan", "gestation", "expecting", "gravid"],
    "LACTATION":              ["lactation", "breastfeed", "breast milk", "nursing"],
    "HEART_FAILURE_ACUTE":    ["acute heart failure", "decompensated heart failure",
                               "acute cardiac failure"],
    "HEART_FAILURE":          ["heart failure", "cardiac failure", "chf", "congestive heart"],
    "ASTHMA_ACUTE":           ["acute asthma", "asthma attack", "asthma exacerbation"],
    "ASTHMA":                 ["asthma"],
    "RENAL_FAILURE":          ["renal failure", "kidney failure", "ckd", "renal impairment",
                               "kidney disease", "nephropathy"],
    "HEPATIC_FAILURE":        ["hepatic failure", "liver failure", "cirrhosis",
                               "liver disease", "hepatitis"],
    "GI_BLEED":               ["gi bleed", "gastrointestinal bleeding", "peptic ulcer",
                               "gastric ulcer", "stomach bleeding"],
    "HYPOTENSION":            ["hypotension", "low blood pressure", "cardiogenic shock"],
    "BRADYCARDIA":            ["bradycardia", "slow heart rate", "heart block", "av block"],
    "HYPERTENSION":           ["hypertension", "high blood pressure", "htn"],
    "DIABETES":               ["diabetes", "diabetic", "hyperglycemia"],
    "STROKE":                 ["stroke", "cerebrovascular", "cva"],
    "MYOCARDIAL_INFARCTION":  ["myocardial infarction", "heart attack", "acute coronary"],
    "ARRHYTHMIA":             ["arrhythmia", "atrial fibrillation", "afib",
                               "ventricular tachycardia"],
    "COPD":                   ["copd", "chronic obstructive", "emphysema",
                               "chronic bronchitis"],
    "SEIZURE":                ["seizure", "epilepsy", "convulsion"],
    "DEPRESSION":             ["depression", "depressive disorder", "mdd"],
    "GLAUCOMA":               ["glaucoma"],
    "IMMUNOSUPPRESSED":       ["transplant", "immunosuppressed", "immunocompromised",
                               "bone marrow"],
    "HEMATOLOGIC_MALIGNANCY": ["leukemia", "aml", "cancer", "malignancy"],
}


def extract_concepts(text: str) -> Set[str]:
    """
    Map free text → a set of canonical concept strings.
    Used for both patient conditions and FDA label sections.
    """
    lowered = text.lower()
    found: Set[str] = set()

    for concept, keywords in _KEYWORD_MAP.items():
        if any(kw in lowered for kw in keywords):
            found.add(concept)

    # Specificity: if acute variant detected, remove the generic one
    # so scoring rules don't double-count
    if "HEART_FAILURE_ACUTE" in found:
        found.discard("HEART_FAILURE")
    if "ASTHMA_ACUTE" in found:
        found.discard("ASTHMA")

    return found


def extract_contraindication_concepts(fda_text: str) -> Set[str]:
    """
    Only extract concepts from text that contains explicit contraindication markers.
    Prevents warnings/precautions from being misclassified as hard contraindications.
    """
    lowered = fda_text.lower()
    if not any(k in lowered for k in ["contraindicated", "contraindication", "should not be used"]):
        return set()
    return extract_concepts(fda_text)