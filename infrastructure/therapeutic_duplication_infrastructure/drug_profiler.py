"""
drug_profiler.py
================
Resolves a drug name → DrugProfile (class, MOA, indications).

Resolution strategy (per architecture doc §8.1):
  1. FDA DailyMed / OpenFDA  →  drug class & MOA
  2. RxNorm (NLM)            →  fallback when FDA returns nothing
  3. Static NICE-aligned KB  →  final safety net for well-known drugs

All HTTP calls are best-effort; failures are logged as warnings, never raised.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional
import urllib.request
import urllib.parse
import json

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DrugProfile:
    name: str                          # resolved generic name (lowercase)
    original_input: str                # raw string supplied by caller
    drug_class: str                    # e.g. "ACE_INHIBITOR"
    mechanism_of_action: str           # e.g. "RAAS_INHIBITION_ACEi"
    indications: set[str]              # e.g. {"hypertension", "heart_failure"}
    nice_guideline_codes: list[str]    # e.g. ["NG106", "NG28"]
    resolved: bool = True              # False  ⟹ could not map to KB


# ---------------------------------------------------------------------------
# Static NICE-aligned knowledge base  (safety-net / canonical reference)
# Mirrors the drug classes in the architecture document §6 exactly.
# ---------------------------------------------------------------------------

_STATIC_KB: dict[str, dict] = {
    # ── ACE inhibitors ──────────────────────────────────────────────────────
    "ramipril":      {"class": "ACE_INHIBITOR", "moa": "RAAS_INHIBITION_ACEi",
                      "indications": {"hypertension","heart_failure","ckd","mi_secondary_prevention"},
                      "nice": ["NG106","NG28","CG187"]},
    "lisinopril":    {"class": "ACE_INHIBITOR", "moa": "RAAS_INHIBITION_ACEi",
                      "indications": {"hypertension","heart_failure","ckd","diabetes"},
                      "nice": ["NG106","NG28","CG187"]},
    "enalapril":     {"class": "ACE_INHIBITOR", "moa": "RAAS_INHIBITION_ACEi",
                      "indications": {"hypertension","heart_failure"},
                      "nice": ["NG106","NG28"]},
    "perindopril":   {"class": "ACE_INHIBITOR", "moa": "RAAS_INHIBITION_ACEi",
                      "indications": {"hypertension","heart_failure","stable_coronary_artery_disease"},
                      "nice": ["NG106","NG28"]},

    # ── ARBs ────────────────────────────────────────────────────────────────
    "losartan":      {"class": "ARB", "moa": "RAAS_INHIBITION_ARB",
                      "indications": {"hypertension","heart_failure","ckd","diabetic_nephropathy"},
                      "nice": ["NG106","NG28"]},
    "candesartan":   {"class": "ARB", "moa": "RAAS_INHIBITION_ARB",
                      "indications": {"hypertension","heart_failure"},
                      "nice": ["NG106","NG28"]},
    "valsartan":     {"class": "ARB", "moa": "RAAS_INHIBITION_ARB",
                      "indications": {"hypertension","heart_failure"},
                      "nice": ["NG106","NG28"]},
    "olmesartan":    {"class": "ARB", "moa": "RAAS_INHIBITION_ARB",
                      "indications": {"hypertension"},
                      "nice": ["NG28"]},

    # ── ARNI ────────────────────────────────────────────────────────────────
    "sacubitril":          {"class": "ARNI", "moa": "RAAS_INHIBITION_ARNI",
                            "indications": {"heart_failure"},
                            "nice": ["TA388"]},
    "sacubitril/valsartan":{"class": "ARNI", "moa": "RAAS_INHIBITION_ARNI",
                            "indications": {"heart_failure"},
                            "nice": ["TA388"]},

    # ── Beta-blockers ────────────────────────────────────────────────────────
    "bisoprolol":    {"class": "BETA_BLOCKER", "moa": "BETA_ADRENERGIC_BLOCKADE",
                      "indications": {"heart_failure","hypertension","atrial_fibrillation","angina"},
                      "nice": ["NG106","NG28","CG187"]},
    "carvedilol":    {"class": "BETA_BLOCKER", "moa": "BETA_ADRENERGIC_BLOCKADE",
                      "indications": {"heart_failure","hypertension"},
                      "nice": ["NG106","NG28"]},
    "metoprolol":    {"class": "BETA_BLOCKER", "moa": "BETA_ADRENERGIC_BLOCKADE",
                      "indications": {"heart_failure","hypertension","angina","atrial_fibrillation"},
                      "nice": ["NG106","NG28","CG187"]},
    "atenolol":      {"class": "BETA_BLOCKER", "moa": "BETA_ADRENERGIC_BLOCKADE",
                      "indications": {"hypertension","angina"},
                      "nice": ["NG28"]},
    "propranolol":   {"class": "BETA_BLOCKER", "moa": "BETA_ADRENERGIC_BLOCKADE",
                      "indications": {"hypertension","atrial_fibrillation","anxiety","tremor"},
                      "nice": ["NG28"]},

    # ── Statins ──────────────────────────────────────────────────────────────
    "atorvastatin":  {"class": "STATIN", "moa": "HMG_COA_REDUCTASE_INHIBITION",
                      "indications": {"hyperlipidaemia","cardiovascular_prevention","diabetes"},
                      "nice": ["CG181","NG238"]},
    "rosuvastatin":  {"class": "STATIN", "moa": "HMG_COA_REDUCTASE_INHIBITION",
                      "indications": {"hyperlipidaemia","cardiovascular_prevention"},
                      "nice": ["CG181","NG238"]},
    "simvastatin":   {"class": "STATIN", "moa": "HMG_COA_REDUCTASE_INHIBITION",
                      "indications": {"hyperlipidaemia","cardiovascular_prevention"},
                      "nice": ["CG181","NG238"]},
    "pravastatin":   {"class": "STATIN", "moa": "HMG_COA_REDUCTASE_INHIBITION",
                      "indications": {"hyperlipidaemia","cardiovascular_prevention"},
                      "nice": ["CG181","NG238"]},

    # ── SSRIs ────────────────────────────────────────────────────────────────
    "sertraline":    {"class": "SSRI", "moa": "SEROTONIN_REUPTAKE_INHIBITION",
                      "indications": {"depression","anxiety","ocd","ptsd"},
                      "nice": ["CG90","CG113"]},
    "fluoxetine":    {"class": "SSRI", "moa": "SEROTONIN_REUPTAKE_INHIBITION",
                      "indications": {"depression","anxiety","bulimia"},
                      "nice": ["CG90","CG113"]},
    "citalopram":    {"class": "SSRI", "moa": "SEROTONIN_REUPTAKE_INHIBITION",
                      "indications": {"depression","anxiety"},
                      "nice": ["CG90"]},
    "escitalopram":  {"class": "SSRI", "moa": "SEROTONIN_REUPTAKE_INHIBITION",
                      "indications": {"depression","anxiety","ocd"},
                      "nice": ["CG90","CG113"]},
    "paroxetine":    {"class": "SSRI", "moa": "SEROTONIN_REUPTAKE_INHIBITION",
                      "indications": {"depression","anxiety","ptsd","ocd"},
                      "nice": ["CG90","CG113"]},

    # ── SNRIs ────────────────────────────────────────────────────────────────
    "venlafaxine":   {"class": "SNRI", "moa": "SEROTONIN_NOREPINEPHRINE_REUPTAKE_INHIBITION",
                      "indications": {"depression","anxiety","panic_disorder"},
                      "nice": ["CG90","CG96"]},
    "duloxetine":    {"class": "SNRI", "moa": "SEROTONIN_NOREPINEPHRINE_REUPTAKE_INHIBITION",
                      "indications": {"depression","anxiety","diabetic_neuropathy"},
                      "nice": ["CG90","CG96"]},

    # ── NSAIDs ───────────────────────────────────────────────────────────────
    "ibuprofen":     {"class": "NSAID", "moa": "COX_INHIBITION_NONSELECTIVE",
                      "indications": {"pain","osteoarthritis","inflammation"},
                      "nice": ["CG177","NG100"]},
    "naproxen":      {"class": "NSAID", "moa": "COX_INHIBITION_NONSELECTIVE",
                      "indications": {"pain","osteoarthritis","rheumatoid_arthritis"},
                      "nice": ["CG177","NG100"]},
    "diclofenac":    {"class": "NSAID", "moa": "COX_INHIBITION_NONSELECTIVE",
                      "indications": {"pain","osteoarthritis","inflammation"},
                      "nice": ["CG177","NG100"]},
    "aspirin":       {"class": "NSAID", "moa": "COX_INHIBITION_NONSELECTIVE",
                      "indications": {"pain","antiplatelet","cardiovascular_prevention"},
                      "nice": ["CG177","NG100"]},

    # ── COX-2 inhibitors ─────────────────────────────────────────────────────
    "celecoxib":     {"class": "COX2_INHIBITOR", "moa": "COX2_INHIBITION_SELECTIVE",
                      "indications": {"pain","osteoarthritis","rheumatoid_arthritis"},
                      "nice": ["CG177","NG100"]},
    "etoricoxib":    {"class": "COX2_INHIBITOR", "moa": "COX2_INHIBITION_SELECTIVE",
                      "indications": {"pain","osteoarthritis","gout"},
                      "nice": ["CG177","NG100"]},

    # ── Anticoagulants – VKA ─────────────────────────────────────────────────
    "warfarin":      {"class": "VITAMIN_K_ANTAGONIST", "moa": "VITAMIN_K_CYCLE_INHIBITION",
                      "indications": {"atrial_fibrillation","dvt","pe","anticoagulation"},
                      "nice": ["CG180","NG196"]},

    # ── Anticoagulants – DOACs ───────────────────────────────────────────────
    "apixaban":      {"class": "DOAC_FACTOR_Xa_INHIBITOR", "moa": "FACTOR_Xa_INHIBITION_DIRECT",
                      "indications": {"atrial_fibrillation","dvt","pe","anticoagulation"},
                      "nice": ["TA275","TA256","CG180"]},
    "rivaroxaban":   {"class": "DOAC_FACTOR_Xa_INHIBITOR", "moa": "FACTOR_Xa_INHIBITION_DIRECT",
                      "indications": {"atrial_fibrillation","dvt","pe","anticoagulation"},
                      "nice": ["TA275","TA256","CG180"]},
    "edoxaban":      {"class": "DOAC_FACTOR_Xa_INHIBITOR", "moa": "FACTOR_Xa_INHIBITION_DIRECT",
                      "indications": {"atrial_fibrillation","dvt","pe","anticoagulation"},
                      "nice": ["CG180","NG196"]},
    "dabigatran":    {"class": "DOAC_THROMBIN_INHIBITOR", "moa": "DIRECT_THROMBIN_INHIBITION",
                      "indications": {"atrial_fibrillation","dvt","pe","anticoagulation"},
                      "nice": ["TA249","CG180"]},

    # ── Diabetes – biguanides ────────────────────────────────────────────────
    "metformin":     {"class": "BIGUANIDE", "moa": "AMPK_ACTIVATION_HEPATIC_GLUCOSE_REDUCTION",
                      "indications": {"type2_diabetes","diabetes","obesity"},
                      "nice": ["NG28","NG87"]},

    # ── Diabetes – SGLT2 inhibitors ──────────────────────────────────────────
    "empagliflozin": {"class": "SGLT2_INHIBITOR", "moa": "SGLT2_INHIBITION_RENAL_GLUCOSE_EXCRETION",
                      "indications": {"type2_diabetes","diabetes","heart_failure","ckd"},
                      "nice": ["TA336","TA390","NG28","NG106"]},
    "dapagliflozin": {"class": "SGLT2_INHIBITOR", "moa": "SGLT2_INHIBITION_RENAL_GLUCOSE_EXCRETION",
                      "indications": {"type2_diabetes","diabetes","heart_failure","ckd"},
                      "nice": ["TA336","TA390","NG28","NG106"]},
    "canagliflozin": {"class": "SGLT2_INHIBITOR", "moa": "SGLT2_INHIBITION_RENAL_GLUCOSE_EXCRETION",
                      "indications": {"type2_diabetes","diabetes","ckd"},
                      "nice": ["TA336","NG28"]},

    # ── Diabetes – GLP-1 agonists ────────────────────────────────────────────
    "semaglutide":   {"class": "GLP1_AGONIST", "moa": "GLP1_RECEPTOR_AGONISM",
                      "indications": {"type2_diabetes","diabetes","obesity"},
                      "nice": ["TA772","TA664","NG28"]},
    "liraglutide":   {"class": "GLP1_AGONIST", "moa": "GLP1_RECEPTOR_AGONISM",
                      "indications": {"type2_diabetes","diabetes","obesity"},
                      "nice": ["TA772","TA664","NG28"]},
    "dulaglutide":   {"class": "GLP1_AGONIST", "moa": "GLP1_RECEPTOR_AGONISM",
                      "indications": {"type2_diabetes","diabetes"},
                      "nice": ["TA NG28"]},
    "exenatide":     {"class": "GLP1_AGONIST", "moa": "GLP1_RECEPTOR_AGONISM",
                      "indications": {"type2_diabetes","diabetes"},
                      "nice": ["NG28"]},

    # ── Diabetes – DPP-4 inhibitors ──────────────────────────────────────────
    "sitagliptin":   {"class": "DPP4_INHIBITOR", "moa": "DPP4_INHIBITION_GLP1_AUGMENTATION",
                      "indications": {"type2_diabetes","diabetes"},
                      "nice": ["NG28"]},
    "alogliptin":    {"class": "DPP4_INHIBITOR", "moa": "DPP4_INHIBITION_GLP1_AUGMENTATION",
                      "indications": {"type2_diabetes","diabetes"},
                      "nice": ["NG28"]},
    "saxagliptin":   {"class": "DPP4_INHIBITOR", "moa": "DPP4_INHIBITION_GLP1_AUGMENTATION",
                      "indications": {"type2_diabetes","diabetes"},
                      "nice": ["NG28"]},

    # ── PPIs ─────────────────────────────────────────────────────────────────
    "omeprazole":    {"class": "PPI", "moa": "H_K_ATPase_INHIBITION",
                      "indications": {"gord","peptic_ulcer","gastroprotection"},
                      "nice": ["CG184"]},
    "lansoprazole":  {"class": "PPI", "moa": "H_K_ATPase_INHIBITION",
                      "indications": {"gord","peptic_ulcer","gastroprotection"},
                      "nice": ["CG184"]},
    "pantoprazole":  {"class": "PPI", "moa": "H_K_ATPase_INHIBITION",
                      "indications": {"gord","peptic_ulcer","gastroprotection"},
                      "nice": ["CG184"]},
    "esomeprazole":  {"class": "PPI", "moa": "H_K_ATPase_INHIBITION",
                      "indications": {"gord","peptic_ulcer","gastroprotection"},
                      "nice": ["CG184"]},

    # ── Calcium channel blockers ─────────────────────────────────────────────
    "amlodipine":    {"class": "CALCIUM_CHANNEL_BLOCKER", "moa": "VOLTAGE_GATED_CALCIUM_CHANNEL_BLOCKADE",
                      "indications": {"hypertension","angina"},
                      "nice": ["NG28"]},
    "felodipine":    {"class": "CALCIUM_CHANNEL_BLOCKER", "moa": "VOLTAGE_GATED_CALCIUM_CHANNEL_BLOCKADE",
                      "indications": {"hypertension","angina"},
                      "nice": ["NG28"]},

    # ── Loop diuretics ───────────────────────────────────────────────────────
    "furosemide":    {"class": "LOOP_DIURETIC", "moa": "NKCC2_INHIBITION_LOOP_OF_HENLE",
                      "indications": {"heart_failure","oedema","hypertension"},
                      "nice": ["NG106"]},
    "bumetanide":    {"class": "LOOP_DIURETIC", "moa": "NKCC2_INHIBITION_LOOP_OF_HENLE",
                      "indications": {"heart_failure","oedema"},
                      "nice": ["NG106"]},

    # ── MRA / Aldosterone antagonists ────────────────────────────────────────
    "spironolactone":{"class": "MINERALOCORTICOID_RECEPTOR_ANTAGONIST",
                      "moa": "ALDOSTERONE_RECEPTOR_BLOCKADE",
                      "indications": {"heart_failure","hyperaldosteronism","oedema"},
                      "nice": ["NG106"]},
    "eplerenone":    {"class": "MINERALOCORTICOID_RECEPTOR_ANTAGONIST",
                      "moa": "ALDOSTERONE_RECEPTOR_BLOCKADE",
                      "indications": {"heart_failure","mi_secondary_prevention"},
                      "nice": ["NG106"]},

    # ── Benzodiazepines ──────────────────────────────────────────────────────
    "lorazepam":     {"class": "BENZODIAZEPINE", "moa": "GABAA_RECEPTOR_POSITIVE_ALLOSTERIC_MODULATION",
                      "indications": {"anxiety","insomnia","seizure","sedation"},
                      "nice": ["CG113"]},
    "diazepam":      {"class": "BENZODIAZEPINE", "moa": "GABAA_RECEPTOR_POSITIVE_ALLOSTERIC_MODULATION",
                      "indications": {"anxiety","muscle_spasm","seizure"},
                      "nice": ["CG113"]},
    "clonazepam":    {"class": "BENZODIAZEPINE", "moa": "GABAA_RECEPTOR_POSITIVE_ALLOSTERIC_MODULATION",
                      "indications": {"anxiety","seizure","panic_disorder"},
                      "nice": ["CG113"]},
    "alprazolam":    {"class": "BENZODIAZEPINE", "moa": "GABAA_RECEPTOR_POSITIVE_ALLOSTERIC_MODULATION",
                      "indications": {"anxiety","panic_disorder"},
                      "nice": ["CG113"]},

    # ── Opioids ──────────────────────────────────────────────────────────────
    "morphine":      {"class": "OPIOID_ANALGESIC", "moa": "MU_OPIOID_RECEPTOR_AGONISM",
                      "indications": {"pain","palliative_care"},
                      "nice": ["NG180"]},
    "oxycodone":     {"class": "OPIOID_ANALGESIC", "moa": "MU_OPIOID_RECEPTOR_AGONISM",
                      "indications": {"pain"},
                      "nice": ["NG180"]},
    "codeine":       {"class": "OPIOID_ANALGESIC", "moa": "MU_OPIOID_RECEPTOR_AGONISM",
                      "indications": {"pain","cough"},
                      "nice": ["NG180"]},
    "tramadol":      {"class": "OPIOID_ANALGESIC", "moa": "MU_OPIOID_RECEPTOR_AGONISM",
                      "indications": {"pain"},
                      "nice": ["NG180"]},
    "fentanyl":      {"class": "OPIOID_ANALGESIC", "moa": "MU_OPIOID_RECEPTOR_AGONISM",
                      "indications": {"pain","palliative_care","anaesthesia"},
                      "nice": ["NG180"]},
}

# Brand-name → generic mapping
_BRAND_TO_GENERIC: dict[str, str] = {
    "tritace": "ramipril", "zestril": "lisinopril", "carace": "lisinopril",
    "innovace": "enalapril", "coversyl": "perindopril",
    "cozaar": "losartan", "amias": "candesartan", "diovan": "valsartan",
    "entresto": "sacubitril/valsartan",
    "cardicor": "bisoprolol", "emcor": "bisoprolol",
    "betaloc": "metoprolol", "lopressor": "metoprolol",
    "lipitor": "atorvastatin", "crestor": "rosuvastatin", "zocor": "simvastatin",
    "lustral": "sertraline", "prozac": "fluoxetine", "cipramil": "citalopram",
    "cipralex": "escitalopram", "seroxat": "paroxetine",
    "efexor": "venlafaxine", "cymbalta": "duloxetine",
    "nurofen": "ibuprofen", "ponstan": "mefenamic acid",
    "celebrex": "celecoxib", "arcoxia": "etoricoxib",
    "jardiance": "empagliflozin", "forxiga": "dapagliflozin", "invokana": "canagliflozin",
    "ozempic": "semaglutide", "wegovy": "semaglutide", "victoza": "liraglutide",
    "januvia": "sitagliptin",
    "losec": "omeprazole", "prilosec": "omeprazole",
    "prevacid": "lansoprazole", "protium": "pantoprazole",
    "norvasc": "amlodipine", "istin": "amlodipine",
    "lasix": "furosemide", "frusemide": "furosemide",
    "aldactone": "spironolactone", "inspra": "eplerenone",
    "ativan": "lorazepam", "valium": "diazepam", "rivotril": "clonazepam",
}

# Regex to strip dose / dosage form from drug name strings
_DOSE_RE = re.compile(
    r"\s+\d[\d.,]*\s*(?:mg|mcg|μg|g|ml|%|iu|units?|tablet|capsule|oral|injection|solution|suspension|"
    r"patch|cream|gel|drops?|spray|inhaler|puff)[\w\s/]*",
    re.IGNORECASE,
)


def _strip_dose(name: str) -> str:
    return _DOSE_RE.sub("", name).strip()


def _canonical(name: str) -> str:
    """Lowercase + strip dose → canonical lookup key."""
    return _strip_dose(name).lower()


# ---------------------------------------------------------------------------
# HTTP helpers  (stdlib only, no requests dependency)
# ---------------------------------------------------------------------------

def _http_get_json(url: str, timeout: int = 8) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BRA-Engine/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        log.debug("HTTP GET failed for %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# FDA resolver
# ---------------------------------------------------------------------------

class _FDAResolver:
    """
    Queries OpenFDA /drug/label to extract pharmacological class & MOA.
    Maps FDA pharm_class strings → our canonical class/MOA identifiers.
    """

    _BASE = "https://api.fda.gov/drug/label.json"

    # FDA pharm class substring → (class_id, moa_id)
    _CLASS_MAP: list[tuple[str, str, str]] = [
        ("angiotensin converting enzyme inhibitor", "ACE_INHIBITOR", "RAAS_INHIBITION_ACEi"),
        ("angiotensin receptor blocker",            "ARB",           "RAAS_INHIBITION_ARB"),
        ("angiotensin receptor-neprilysin inhibitor","ARNI",         "RAAS_INHIBITION_ARNI"),
        ("beta-adrenergic blocker",                 "BETA_BLOCKER",  "BETA_ADRENERGIC_BLOCKADE"),
        ("beta adrenergic blocker",                 "BETA_BLOCKER",  "BETA_ADRENERGIC_BLOCKADE"),
        ("hmg-coa reductase inhibitor",             "STATIN",        "HMG_COA_REDUCTASE_INHIBITION"),
        ("hmg coa reductase inhibitor",             "STATIN",        "HMG_COA_REDUCTASE_INHIBITION"),
        ("selective serotonin reuptake inhibitor",  "SSRI",          "SEROTONIN_REUPTAKE_INHIBITION"),
        ("serotonin and norepinephrine reuptake inhibitor","SNRI",   "SEROTONIN_NOREPINEPHRINE_REUPTAKE_INHIBITION"),
        ("nonsteroidal anti-inflammatory",          "NSAID",         "COX_INHIBITION_NONSELECTIVE"),
        ("cox-2 inhibitor",                         "COX2_INHIBITOR","COX2_INHIBITION_SELECTIVE"),
        ("cyclooxygenase-2 inhibitor",              "COX2_INHIBITOR","COX2_INHIBITION_SELECTIVE"),
        ("vitamin k antagonist",                    "VITAMIN_K_ANTAGONIST","VITAMIN_K_CYCLE_INHIBITION"),
        ("factor xa inhibitor",                     "DOAC_FACTOR_Xa_INHIBITOR","FACTOR_Xa_INHIBITION_DIRECT"),
        ("direct thrombin inhibitor",               "DOAC_THROMBIN_INHIBITOR","DIRECT_THROMBIN_INHIBITION"),
        ("biguanide",                               "BIGUANIDE",     "AMPK_ACTIVATION_HEPATIC_GLUCOSE_REDUCTION"),
        ("sodium-glucose cotransporter 2",          "SGLT2_INHIBITOR","SGLT2_INHIBITION_RENAL_GLUCOSE_EXCRETION"),
        ("sglt2",                                   "SGLT2_INHIBITOR","SGLT2_INHIBITION_RENAL_GLUCOSE_EXCRETION"),
        ("glucagon-like peptide-1",                 "GLP1_AGONIST",  "GLP1_RECEPTOR_AGONISM"),
        ("glp-1",                                   "GLP1_AGONIST",  "GLP1_RECEPTOR_AGONISM"),
        ("dipeptidyl peptidase-4",                  "DPP4_INHIBITOR","DPP4_INHIBITION_GLP1_AUGMENTATION"),
        ("dpp-4",                                   "DPP4_INHIBITOR","DPP4_INHIBITION_GLP1_AUGMENTATION"),
        ("proton pump inhibitor",                   "PPI",           "H_K_ATPase_INHIBITION"),
        ("calcium channel blocker",                 "CALCIUM_CHANNEL_BLOCKER","VOLTAGE_GATED_CALCIUM_CHANNEL_BLOCKADE"),
        ("loop diuretic",                           "LOOP_DIURETIC", "NKCC2_INHIBITION_LOOP_OF_HENLE"),
        ("aldosterone receptor antagonist",         "MINERALOCORTICOID_RECEPTOR_ANTAGONIST","ALDOSTERONE_RECEPTOR_BLOCKADE"),
        ("mineralocorticoid receptor antagonist",   "MINERALOCORTICOID_RECEPTOR_ANTAGONIST","ALDOSTERONE_RECEPTOR_BLOCKADE"),
        ("benzodiazepine",                          "BENZODIAZEPINE","GABAA_RECEPTOR_POSITIVE_ALLOSTERIC_MODULATION"),
        ("opioid",                                  "OPIOID_ANALGESIC","MU_OPIOID_RECEPTOR_AGONISM"),
    ]

    def resolve(self, drug: str) -> Optional[tuple[str, str]]:
        """Returns (class_id, moa_id) or None."""
        url = (f"{self._BASE}?search=openfda.generic_name:\"{urllib.parse.quote(drug)}\""
               f"&limit=1")
        data = _http_get_json(url)
        if not data:
            return None
        try:
            results = data.get("results", [])
            if not results:
                return None
            # pharm_class_epc / pharm_class_moa are the relevant fields
            pharm_classes: list[str] = []
            openfda = results[0].get("openfda", {})
            pharm_classes += openfda.get("pharm_class_epc", [])
            pharm_classes += openfda.get("pharm_class_moa", [])
            pharm_classes += openfda.get("pharm_class_cs", [])
            for pc in pharm_classes:
                pc_lower = pc.lower()
                for substr, cls_id, moa_id in self._CLASS_MAP:
                    if substr in pc_lower:
                        return cls_id, moa_id
        except Exception as exc:
            log.debug("FDA parse error for %s: %s", drug, exc)
        return None


# ---------------------------------------------------------------------------
# RxNorm resolver  (fallback)
# ---------------------------------------------------------------------------

class _RxNormResolver:
    """
    Uses NLM RxNorm API to get RxCUI, then fetches drug class via RxClass.
    Maps RxClass classId/className → our canonical identifiers.
    """

    _RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
    _RXCLASS_BASE = "https://rxnav.nlm.nih.gov/REST/rxclass"

    # RxClass className fragment → (class_id, moa_id)
    _RXCLASS_MAP: list[tuple[str, str, str]] = [
        ("ace inhibitor",                           "ACE_INHIBITOR",   "RAAS_INHIBITION_ACEi"),
        ("angiotensin ii receptor antagonist",      "ARB",             "RAAS_INHIBITION_ARB"),
        ("beta blocker",                            "BETA_BLOCKER",    "BETA_ADRENERGIC_BLOCKADE"),
        ("beta-adrenergic blocking agent",          "BETA_BLOCKER",    "BETA_ADRENERGIC_BLOCKADE"),
        ("hmg coa reductase inhibitor",             "STATIN",          "HMG_COA_REDUCTASE_INHIBITION"),
        ("selective serotonin reuptake inhibitor",  "SSRI",            "SEROTONIN_REUPTAKE_INHIBITION"),
        ("serotonin norepinephrine reuptake inhibitor","SNRI",         "SEROTONIN_NOREPINEPHRINE_REUPTAKE_INHIBITION"),
        ("nonsteroidal anti-inflammatory agent",    "NSAID",           "COX_INHIBITION_NONSELECTIVE"),
        ("cyclooxygenase 2 inhibitor",              "COX2_INHIBITOR",  "COX2_INHIBITION_SELECTIVE"),
        ("vitamin k antagonist",                    "VITAMIN_K_ANTAGONIST","VITAMIN_K_CYCLE_INHIBITION"),
        ("factor xa inhibitor",                     "DOAC_FACTOR_Xa_INHIBITOR","FACTOR_Xa_INHIBITION_DIRECT"),
        ("direct thrombin inhibitor",               "DOAC_THROMBIN_INHIBITOR","DIRECT_THROMBIN_INHIBITION"),
        ("biguanide",                               "BIGUANIDE",       "AMPK_ACTIVATION_HEPATIC_GLUCOSE_REDUCTION"),
        ("sglt2",                                   "SGLT2_INHIBITOR", "SGLT2_INHIBITION_RENAL_GLUCOSE_EXCRETION"),
        ("sodium glucose cotransporter",            "SGLT2_INHIBITOR", "SGLT2_INHIBITION_RENAL_GLUCOSE_EXCRETION"),
        ("glucagon-like peptide",                   "GLP1_AGONIST",    "GLP1_RECEPTOR_AGONISM"),
        ("dipeptidyl peptidase 4 inhibitor",        "DPP4_INHIBITOR",  "DPP4_INHIBITION_GLP1_AUGMENTATION"),
        ("proton pump inhibitor",                   "PPI",             "H_K_ATPase_INHIBITION"),
        ("calcium channel blocker",                 "CALCIUM_CHANNEL_BLOCKER","VOLTAGE_GATED_CALCIUM_CHANNEL_BLOCKADE"),
        ("loop diuretic",                           "LOOP_DIURETIC",   "NKCC2_INHIBITION_LOOP_OF_HENLE"),
        ("mineralocorticoid receptor antagonist",   "MINERALOCORTICOID_RECEPTOR_ANTAGONIST","ALDOSTERONE_RECEPTOR_BLOCKADE"),
        ("aldosterone antagonist",                  "MINERALOCORTICOID_RECEPTOR_ANTAGONIST","ALDOSTERONE_RECEPTOR_BLOCKADE"),
        ("benzodiazepine",                          "BENZODIAZEPINE",  "GABAA_RECEPTOR_POSITIVE_ALLOSTERIC_MODULATION"),
        ("opioid",                                  "OPIOID_ANALGESIC","MU_OPIOID_RECEPTOR_AGONISM"),
        ("narcotic",                                "OPIOID_ANALGESIC","MU_OPIOID_RECEPTOR_AGONISM"),
    ]

    def _get_rxcui(self, drug: str) -> Optional[str]:
        url = f"{self._RXNORM_BASE}/rxcui.json?name={urllib.parse.quote(drug)}&search=1"
        data = _http_get_json(url)
        if not data:
            return None
        try:
            cui = data["idGroup"]["rxnormId"]
            return cui[0] if cui else None
        except Exception:
            return None

    def _get_classes(self, rxcui: str) -> list[tuple[str, str]]:
        """Returns list of (classId, className) tuples."""
        url = f"{self._RXCLASS_BASE}/class/byRxcui.json?rxcui={rxcui}&relaSource=MESH"
        data = _http_get_json(url)
        results = []
        if not data:
            return results
        try:
            for entry in data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []):
                ci = entry.get("rxclassMinConceptItem", {})
                results.append((ci.get("classId", ""), ci.get("className", "")))
        except Exception:
            pass
        # Also try ATC source for broader coverage
        url2 = f"{self._RXCLASS_BASE}/class/byRxcui.json?rxcui={rxcui}&relaSource=ATC1-4"
        data2 = _http_get_json(url2)
        if data2:
            try:
                for entry in data2.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []):
                    ci = entry.get("rxclassMinConceptItem", {})
                    results.append((ci.get("classId", ""), ci.get("className", "")))
            except Exception:
                pass
        return results

    def resolve(self, drug: str) -> Optional[tuple[str, str]]:
        rxcui = self._get_rxcui(drug)
        if not rxcui:
            return None
        classes = self._get_classes(rxcui)
        for _, class_name in classes:
            cn_lower = class_name.lower()
            for substr, cls_id, moa_id in self._RXCLASS_MAP:
                if substr in cn_lower:
                    return cls_id, moa_id
        return None


# ---------------------------------------------------------------------------
# Public DrugProfiler
# ---------------------------------------------------------------------------

class DrugProfiler:
    """
    Resolves a drug name → DrugProfile using a 3-layer strategy:
      1. Static NICE-aligned KB   (instant, no network)
      2. FDA OpenFDA API          (network)
      3. RxNorm/RxClass API       (network fallback)
    """

    def __init__(self):
        self._fda = _FDAResolver()
        self._rxnorm = _RxNormResolver()

    def profile(self, drug_name: str) -> DrugProfile:
        """Always returns a DrugProfile; resolved=False if unknown."""
        canonical = _canonical(drug_name)
        # Brand → generic
        generic = _BRAND_TO_GENERIC.get(canonical, canonical)

        # 1. Static KB
        if generic in _STATIC_KB:
            entry = _STATIC_KB[generic]
            return DrugProfile(
                name=generic,
                original_input=drug_name,
                drug_class=entry["class"],
                mechanism_of_action=entry["moa"],
                indications=set(entry["indications"]),
                nice_guideline_codes=list(entry["nice"]),
                resolved=True,
            )

        # 2. FDA
        log.debug("Static KB miss for '%s' → trying FDA", generic)
        fda_result = self._fda.resolve(generic)
        if fda_result:
            cls_id, moa_id = fda_result
            return DrugProfile(
                name=generic,
                original_input=drug_name,
                drug_class=cls_id,
                mechanism_of_action=moa_id,
                indications=set(),
                nice_guideline_codes=[],
                resolved=True,
            )

        # 3. RxNorm fallback
        log.debug("FDA miss for '%s' → trying RxNorm", generic)
        rxn_result = self._rxnorm.resolve(generic)
        if rxn_result:
            cls_id, moa_id = rxn_result
            return DrugProfile(
                name=generic,
                original_input=drug_name,
                drug_class=cls_id,
                mechanism_of_action=moa_id,
                indications=set(),
                nice_guideline_codes=[],
                resolved=True,
            )

        # Unresolved
        log.warning("Could not resolve drug profile for '%s'", drug_name)
        return DrugProfile(
            name=generic,
            original_input=drug_name,
            drug_class="UNKNOWN",
            mechanism_of_action="UNKNOWN",
            indications=set(),
            nice_guideline_codes=[],
            resolved=False,
        )
