import re
import time
import requests
import os
from typing import Dict, List, Any, Optional

from infrastructure.adr_infrastructure.helpers import (
    _extract_text,
    _extract_context,
    _deduplicate_adrs,
    _can_patient_be_pregnant,
)
from infrastructure.adr_infrastructure.detectors import (
    extract_adr_name,
    clean_serious_adr_name,
    extract_interaction_risk_factors,
    match_patient_risk_factors,
    RISK_FACTOR_PATTERNS,
)


class ADRAnalyzer:
    """
    Infrastructure service: wraps all Factor 3.2 (LT ADRs, Serious ADRs)
    and Factor 3.3 (Drug Interactions) detection logic.

    No file I/O — receives patient_data dict, returns structured result dict.
    Called by ADRComponent, which is responsible for wiring into ExecutionContext.
    """

    LT_KEYWORDS = [
        "fatal", "potentially fatal", "may result in death", "death", "mortality",
        "associated with fatal outcomes", "can be fatal", "risk of death",
        "lactic acidosis", "metabolic acidosis",
    ]

    HIGH_RISK_EVENTS = [
        "anaphylaxis", "anaphylactic reaction", "anaphylactic shock",
        "stevens-johnson syndrome", "stevens johnson", "toxic epidermal necrolysis",
        "torsades de pointes", "ventricular arrhythmia", "ventricular fibrillation",
        "acute liver failure", "hepatic failure", "respiratory failure",
        "respiratory arrest", "agranulocytosis", "neutropenic sepsis",
        "bone marrow suppression", "aplastic anemia", "cardiac arrest",
        "sudden cardiac death", "heart failure", "pulmonary toxicity",
        "hepatotoxicity", "acute kidney injury", "renal failure",
        "necrotizing pancreatitis", "hemorrhagic pancreatitis",
    ]

    SERIOUS_PATTERNS = [
        r"the following serious adverse reactions are described in more detail[^:]*:([^\.]+(?:\.[^\.]{10,100})?)",
        r"serious adverse reactions include:([^\.]+(?:\.[^\.]{10,100})?)",
        r"serious side effects include:([^\.]+(?:\.[^\.]{10,100})?)",
    ]

    def __init__(self):
        self._fda_api_key  = os.getenv("FDA_API_KEY", "")
        self._fda_base_url = "https://api.fda.gov/drug/label.json"
        self._risk_factor_patterns = RISK_FACTOR_PATTERNS

    # ── FDA fetch ─────────────────────────────────────────────────────────────

    def fetch_fda_sections(self, medicine_name: str) -> Optional[Dict[str, Any]]:
        medicine_lower = medicine_name.lower()
        variants = [medicine_name]
        if "lithium"    in medicine_lower: variants = ["lithium", "lithium carbonate"]
        elif "metformin" in medicine_lower: variants = ["metformin", "metformin hydrochloride"]
        elif "warfarin"  in medicine_lower: variants = ["warfarin", "warfarin sodium"]
        elif "amiodarone" in medicine_lower: variants = ["amiodarone", "amiodarone hydrochloride"]

        all_results = []
        for variant in variants:
            params = {
                "search": f'openfda.generic_name:"{variant}" OR openfda.brand_name:"{variant}"',
                "limit": 5,
            }
            if self._fda_api_key:
                params["api_key"] = self._fda_api_key
            try:
                resp = requests.get(self._fda_base_url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                if data.get("results"):
                    all_results.extend(data["results"])
                    break
            except Exception:
                continue

        if not all_results:
            return None

        # Prefer single-ingredient product
        label = all_results[0]
        for result in all_results:
            gnames = result.get("openfda", {}).get("generic_name", [])
            if len(gnames) == 1 and medicine_lower in gnames[0].lower():
                label = result
                break

        return {
            "drug_name":              medicine_name,
            "boxed_warning":          _extract_text(label, "boxed_warning"),
            "warnings_and_cautions":  _extract_text(label, "warnings_and_cautions"),
            "warnings":               _extract_text(label, "warnings"),
            "precautions":            _extract_text(label, "precautions"),
            "adverse_reactions":      _extract_text(label, "adverse_reactions"),
            "drug_interactions":      _extract_text(label, "drug_interactions"),
            "contraindications":      _extract_text(label, "contraindications"),
        }

    # ── LT ADR detection ─────────────────────────────────────────────────────

    def find_lt_adrs(
        self, medicine: str, fda: Dict[str, Any], patient_data: Dict[str, Any]
    ) -> Dict[str, List]:
        if not fda:
            return {"with_risk_factors": [], "without_risk_factors": []}

        can_be_pregnant = _can_patient_be_pregnant(patient_data)
        all_adrs = []

        for text, section in [
            (fda.get("adverse_reactions", ""),                        "Section 6"),
            (fda.get("warnings_and_cautions") or fda.get("warnings", ""), "Section 5"),
            (fda.get("boxed_warning", ""),                            "Boxed Warning"),
        ]:
            if text:
                all_adrs.extend(self._search_lt(text, section, medicine, can_be_pregnant))

        unique = _deduplicate_adrs(all_adrs)
        with_rf, without_rf = [], []
        for adr in unique:
            rm = match_patient_risk_factors(adr, patient_data, fda)
            entry = {
                "medicine":    medicine,
                "adr_name":    adr["adr_name"],
                "section":     adr["section"],
                "risk_factors": rm["matched_factors"],
                "fda_context": adr["context"],
            }
            (with_rf if rm["has_risk_factors"] else without_rf).append(entry)

        return {"with_risk_factors": with_rf, "without_risk_factors": without_rf}

    def _search_lt(
        self, text: str, section: str, medicine: str, can_be_pregnant: bool
    ) -> List[Dict]:
        text_lower = text.lower()
        found = []
        preg_events = ["spontaneous abortion", "fetal death", "fetal harm",
                       "embryo-fetal toxicity", "fetal toxicity"]

        for event in self.HIGH_RISK_EVENTS:
            if event in text_lower:
                if any(p in event for p in preg_events) and not can_be_pregnant:
                    continue
                found.append({
                    "medicine": medicine, "adr_name": event.title(),
                    "section": section, "context": _extract_context(text, event, 300),
                    "detection_method": "high_risk_event",
                })

        for kw in self.LT_KEYWORDS:
            if kw in text_lower:
                ctx  = _extract_context(text, kw, 300)
                name = extract_adr_name(ctx, kw)
                if name and name != "None":
                    if any(t in name.lower() for t in ["fetal", "pregnancy", "embryo"]) and not can_be_pregnant:
                        continue
                    if not any(e["adr_name"].lower() == name.lower() for e in found):
                        found.append({
                            "medicine": medicine, "adr_name": name,
                            "section": section, "context": ctx,
                            "detection_method": "keyword",
                        })
        return found

    # ── Serious ADR detection ─────────────────────────────────────────────────

    def find_serious_adrs(
        self,
        medicine: str,
        fda: Dict[str, Any],
        patient_data: Dict[str, Any],
        lt_adrs: Dict[str, List],
    ) -> Dict[str, List]:
        if not fda:
            return {"with_risk_factors": [], "without_risk_factors": []}

        lt_names = {a["adr_name"].lower() for a in lt_adrs["with_risk_factors"] + lt_adrs["without_risk_factors"]}
        all_adrs = []

        for text, section in [
            (fda.get("adverse_reactions", ""),                             "Section 6"),
            (fda.get("warnings_and_cautions") or fda.get("warnings", ""), "Section 5"),
        ]:
            if text:
                all_adrs.extend(self._search_serious(text, section, medicine, lt_names))

        unique = _deduplicate_adrs(all_adrs)
        with_rf, without_rf = [], []
        for adr in unique:
            rm = match_patient_risk_factors(adr, patient_data, fda)
            entry = {
                "medicine":    medicine,
                "adr_name":    adr["adr_name"],
                "section":     adr["section"],
                "risk_factors": rm["matched_factors"],
                "fda_context": adr["context"],
            }
            (with_rf if rm["has_risk_factors"] else without_rf).append(entry)

        return {"with_risk_factors": with_rf, "without_risk_factors": without_rf}

    def _search_serious(
        self, text: str, section: str, medicine: str, lt_names: set
    ) -> List[Dict]:
        text_lower = text.lower()
        found = []
        for pattern in self.SERIOUS_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE | re.DOTALL):
                for raw in re.split(r"[,;•\n]", match.group(1)):
                    raw = raw.strip()
                    if len(raw) < 5:
                        continue
                    if any(raw.startswith(w) for w in ["see", "section", "and", "or", "the", "in", "of", "warnings"]):
                        continue
                    name = clean_serious_adr_name(raw)
                    if not name or name == "None":
                        continue
                    if name.lower() in lt_names:
                        continue
                    if any(kw in name.lower() for kw in self.LT_KEYWORDS):
                        continue
                    if any(ev in name.lower() for ev in self.HIGH_RISK_EVENTS):
                        continue
                    found.append({
                        "medicine": medicine, "adr_name": name,
                        "section": section,
                        "context": _extract_context(text, name, 300),
                        "detection_method": "serious_statement",
                    })
        return found

    # ── Drug interaction detection ────────────────────────────────────────────

    def find_drug_interactions(
        self, medicine: str, fda: Dict[str, Any], patient_data: Dict[str, Any]
    ) -> Dict[str, List]:
        empty = {"contraindicated": [], "lt_interactions": [], "serious_interactions": [], "non_serious_interactions": []}
        if not fda:
            return empty

        interactions_text  = fda.get("drug_interactions", "")
        contraind_text     = fda.get("contraindications", "")
        if not interactions_text:
            return empty

        patient_meds = [
            m.lower().strip()
            for m in patient_data.get("prescription", [])
            if m.lower().strip() != medicine.lower()
        ]

        contraindicated = []
        lt_interactions = []
        serious_interactions = []
        non_serious_interactions = []

        int_lower   = interactions_text.lower()
        contra_lower = contraind_text.lower() if contraind_text else ""

        for med in patient_meds:
            if med not in int_lower:
                continue

            ctx       = _extract_context(interactions_text, med, 500)
            ctx_lower = ctx.lower()
            is_contra = False

            if contraind_text and med in contra_lower:
                ctx       = _extract_context(contraind_text, med, 300)
                ctx_lower = ctx.lower()
                is_contra = True
            elif re.search(rf"{re.escape(med)}.*is contraindicated|concomitant use.*{re.escape(med)}.*is contraindicated", ctx_lower):
                is_contra = True

            rf = extract_interaction_risk_factors(ctx, patient_data)

            if is_contra:
                contraindicated.append({"medicine": medicine, "interacting_drug": med, "interaction_type": "contraindicated", "context": ctx, "risk_factors": rf})
            elif any(kw in ctx_lower for kw in ["fatal", "death", "life-threatening", "bleeding", "hemorrhage", "anaphylaxis"]):
                lt_interactions.append({"medicine": medicine, "interacting_drug": med, "interaction_type": "life-threatening", "context": ctx, "risk_factors": rf})
            elif "serious" in ctx_lower or any(t in ctx_lower for t in ["myopathy", "rhabdomyolysis", "toxicity", "severe"]):
                serious_interactions.append({"medicine": medicine, "interacting_drug": med, "interaction_type": "serious", "context": ctx, "risk_factors": rf})
            elif any(t in ctx_lower for t in ["efficacy", "effectiveness", "increased levels", "decreased levels"]):
                non_serious_interactions.append({"medicine": medicine, "interacting_drug": med, "interaction_type": "non-serious", "context": ctx, "risk_factors": []})

        return {
            "contraindicated":         contraindicated,
            "lt_interactions":         lt_interactions,
            "serious_interactions":    serious_interactions,
            "non_serious_interactions": non_serious_interactions,
        }

    # ── Main entrypoint ───────────────────────────────────────────────────────

    def analyze(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs full Factor 3.2 + 3.3 analysis.
        Returns structured dict — no file I/O.
        """
        medicines = patient_data.get("prescription", [])
        if not medicines:
            return {"factor_3_2": {"LT_ADRs": {}, "Serious_ADRs": {}}, "factor_3_3": {"interactions": {}}}

        fda_data = {}
        for medicine in medicines:
            print(f"  [ADRAnalyzer] Fetching FDA data for '{medicine}'...")
            fda_data[medicine] = self.fetch_fda_sections(medicine)
            time.sleep(0.3)

        results_lt, results_serious, results_interactions = {}, {}, {}

        for medicine in medicines:
            fda = fda_data.get(medicine)
            if not fda:
                continue

            lt      = self.find_lt_adrs(medicine, fda, patient_data)
            serious = self.find_serious_adrs(medicine, fda, patient_data, lt)
            inter   = self.find_drug_interactions(medicine, fda, patient_data)

            if lt["with_risk_factors"] or lt["without_risk_factors"]:
                results_lt[medicine] = lt
            if serious["with_risk_factors"] or serious["without_risk_factors"]:
                results_serious[medicine] = serious
            if any(inter.values()):
                results_interactions[medicine] = inter

        return {
            "patient":    patient_data.get("patient", {}),
            "medications": medicines,
            "factor_3_2": {"LT_ADRs": results_lt, "Serious_ADRs": results_serious},
            "factor_3_3": {"interactions": results_interactions},
        }
