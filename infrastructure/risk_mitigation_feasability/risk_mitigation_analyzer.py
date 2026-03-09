import os
import re
import time
import json
import requests
from typing import Dict, List, Any, Optional

from infrastructure.adr_infrastructure.helpers import _extract_text


class RiskMitigationAnalyzer:
    """
    Infrastructure service: classifies ADRs by reversibility (R5) and
    preventability (R4). Corresponds to Factor 3.4 in the original prototype.

    Accepts ADR analysis dict directly (no file I/O).
    Returns structured dict with reversibility and preventability results.
    """

    _MODEL = "gemini-2.0-flash"

    STRICT_IRREVERSIBLE = [
        "stevens-johnson syndrome", "stevens johnson", "sjs",
        "toxic epidermal necrolysis", "ten",
        "hearing loss", "ototoxicity", "pulmonary fibrosis", "hepatic fibrosis",
        "cardiomyopathy", "optic neuropathy", "peripheral neuropathy",
        "teratogenicity", "congenital malformations",
        "aplastic anemia", "agranulocytosis", "acute liver failure", "hepatic failure",
    ]

    STRICT_NON_PREVENTABLE = [
        "stevens-johnson syndrome", "stevens johnson", "sjs",
        "toxic epidermal necrolysis", "ten",
        "anaphylaxis", "anaphylactic", "idiosyncratic reaction",
    ]

    IRREVERSIBLE_KW = [
        "irreversible", "permanent", "may not be reversible",
        "persistent after discontinuation", "cumulative and irreversible",
        "progressive", "did not resolve", "fibrosis", "organ failure",
        "structural damage", "malformation", "teratogenic", "carcinogenic",
        "cardiomyopathy", "neuropathy", "ototoxicity",
    ]

    REVERSIBLE_KW = [
        "reversible", "resolved after discontinuation",
        "improved after stopping", "transient", "self-limited",
        "dose-related", "resolved in most patients",
        "normalized", "temporary", "returned to baseline",
        "reversible upon interruption",
    ]

    PREVENTABLE_KW = [
        "monitor", "avoid", "baseline", "periodic", "lab test",
        "dose reduction", "contraindicated", "screening",
        "early detection", "proactive", "warning signs",
    ]

    def __init__(self):
        self._fda_api_key  = os.getenv("FDA_API_KEY", "")
        self._fda_base_url = "https://api.fda.gov/drug/label.json"
        self._client       = self._init_gemini()

    def _init_gemini(self):
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            return None
        try:
            from google import genai
            return genai.Client(api_key=key)
        except ImportError:
            return None

    # ── FDA fetch ─────────────────────────────────────────────────────────────

    def _fetch_fda_sections(self, medicine_name: str) -> Optional[Dict[str, Any]]:
        medicine_lower = medicine_name.lower()
        variants = [medicine_name]
        if "lithium"    in medicine_lower: variants = ["lithium", "lithium carbonate"]
        elif "metformin" in medicine_lower: variants = ["metformin", "metformin hydrochloride"]
        elif "warfarin"  in medicine_lower: variants = ["warfarin", "warfarin sodium"]
        elif "amiodarone" in medicine_lower: variants = ["amiodarone", "amiodarone hydrochloride"]

        all_results = []
        for variant in variants:
            params = {"search": f'openfda.generic_name:"{variant}" OR openfda.brand_name:"{variant}"', "limit": 5}
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
        label = all_results[0]
        return {
            "drug_name":             medicine_name,
            "boxed_warning":         _extract_text(label, "boxed_warning"),
            "warnings_and_cautions": _extract_text(label, "warnings_and_cautions"),
            "warnings":              _extract_text(label, "warnings"),
            "adverse_reactions":     _extract_text(label, "adverse_reactions"),
            "dosage_and_administration": _extract_text(label, "dosage_and_administration"),
        }

    # ── ADR extraction from ADRAnalyzer output ────────────────────────────────

    def _extract_all_adrs(self, adr_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        adrs = []
        for medicine, data in adr_analysis.get("factor_3_2", {}).get("LT_ADRs", {}).items():
            for adr in data.get("with_risk_factors", []) + data.get("without_risk_factors", []):
                adrs.append({"medicine": medicine, "adr_name": adr["adr_name"],
                              "adr_type": "LT/Fatal ADR", "fda_context": adr.get("fda_context", "")})
        for medicine, data in adr_analysis.get("factor_3_2", {}).get("Serious_ADRs", {}).items():
            for adr in data.get("with_risk_factors", []) + data.get("without_risk_factors", []):
                adrs.append({"medicine": medicine, "adr_name": adr["adr_name"],
                              "adr_type": "Serious ADR", "fda_context": adr.get("fda_context", "")})
        return adrs

    # ── Reversibility classification ──────────────────────────────────────────

    def _classify_reversibility(
        self, adr: Dict[str, Any], fda_sections: Optional[Dict[str, Any]], patient_context: str = ""
    ) -> Dict[str, Any]:
        adr_lower = adr["adr_name"].lower()

        # Strict rules first
        for strict in self.STRICT_IRREVERSIBLE:
            if strict in adr_lower:
                return {
                    "classification": "Irreversible ADR",
                    "reasoning": f"{adr['adr_name']} is a known irreversible condition.",
                    "fda_evidence": "Documented as irreversible in medical literature",
                    "keywords_found": [strict],
                }

        fda_text = ""
        if fda_sections:
            fda_text = " ".join(filter(None, [
                fda_sections.get("warnings_and_cautions", ""),
                fda_sections.get("adverse_reactions", ""),
                fda_sections.get("boxed_warning", ""),
            ]))

        fda_lower = fda_text.lower()
        irrev_hits = [k for k in self.IRREVERSIBLE_KW if k in fda_lower]
        rev_hits   = [k for k in self.REVERSIBLE_KW   if k in fda_lower]

        if not self._client:
            if irrev_hits:
                return {"classification": "Irreversible ADR",   "reasoning": "Irreversibility keywords in FDA text", "fda_evidence": ", ".join(irrev_hits[:3]), "keywords_found": irrev_hits[:3]}
            if rev_hits:
                return {"classification": "Reversible ADR",     "reasoning": "Reversibility keywords in FDA text",   "fda_evidence": ", ".join(rev_hits[:3]),   "keywords_found": rev_hits[:3]}
            return {"classification": "Reversible ADR", "reasoning": "Default classification", "fda_evidence": "Limited FDA information", "keywords_found": []}

        pt = f"\n\n{patient_context}" if patient_context else ""
        prompt = (
            f"Medicine: {adr['medicine']}\nADR: {adr['adr_name']}\n\n"
            f"FDA USPI (excerpt):\n{fda_text[:2500]}\n{pt}\n\n"
            "Classify as exactly ONE of: Irreversible ADR | Reversible ADR | Tolerable ADR\n"
            "Return ONLY valid JSON:\n"
            '{"classification":"...","reasoning":"...","fda_evidence":"...","keywords_found":[]}'
        )
        try:
            resp = self._client.models.generate_content(model=self._MODEL, contents=prompt)
            text = resp.text.strip().replace("```json", "").replace("```", "")
            return json.loads(text)
        except Exception as exc:
            print(f"  [RiskMitigationAnalyzer] Gemini reversibility error: {exc}")
            return {"classification": "Reversible ADR", "reasoning": "Fallback", "fda_evidence": "API error", "keywords_found": []}

    # ── Preventability classification ─────────────────────────────────────────

    def _classify_preventability(
        self, adr: Dict[str, Any], fda_sections: Optional[Dict[str, Any]], patient_context: str = ""
    ) -> Dict[str, Any]:
        adr_lower = adr["adr_name"].lower()

        # Strict rules first
        for strict in self.STRICT_NON_PREVENTABLE:
            if strict in adr_lower:
                return {
                    "classification": "Non-preventable ADR",
                    "reasoning": f"{adr['adr_name']} is an idiosyncratic/unpredictable reaction.",
                    "fda_evidence": "Documented as unpredictable",
                    "prevention_measures": [],
                }

        fda_text = ""
        if fda_sections:
            fda_text = " ".join(filter(None, [
                fda_sections.get("warnings_and_cautions", ""),
                fda_sections.get("adverse_reactions", ""),
                fda_sections.get("dosage_and_administration", ""),
            ]))

        fda_lower   = fda_text.lower()
        prev_hits   = [k for k in self.PREVENTABLE_KW if k in fda_lower]

        if not self._client:
            if prev_hits:
                return {"classification": "Preventable ADR", "reasoning": "Prevention measures in FDA text", "fda_evidence": ", ".join(prev_hits[:3]), "prevention_measures": prev_hits[:3]}
            return {"classification": "Non-preventable ADR", "reasoning": "No specific prevention measures", "fda_evidence": "Limited information", "prevention_measures": []}

        pt = f"\n\n{patient_context}" if patient_context else ""
        prompt = (
            f"Medicine: {adr['medicine']}\nADR: {adr['adr_name']}\n\n"
            f"FDA USPI (excerpt):\n{fda_text[:2500]}\n{pt}\n\n"
            "Classify as exactly ONE of: Non-Tolerable ADR | Non-preventable ADR | Preventable ADR\n"
            "Return ONLY valid JSON:\n"
            '{"classification":"...","reasoning":"...","fda_evidence":"...","prevention_measures":[]}'
        )
        try:
            resp = self._client.models.generate_content(model=self._MODEL, contents=prompt)
            text = resp.text.strip().replace("```json", "").replace("```", "")
            return json.loads(text)
        except Exception as exc:
            print(f"  [RiskMitigationAnalyzer] Gemini preventability error: {exc}")
            return {"classification": "Non-preventable ADR", "reasoning": "Fallback", "fda_evidence": "API error", "prevention_measures": []}

    # ── Main entrypoint ───────────────────────────────────────────────────────

    def analyze(
        self,
        adr_analysis: Dict[str, Any],
        patient_data: dict,
        drug_data: dict,
    ) -> Dict[str, Any]:
        """
        Accepts ADRAnalyzer.analyze() output + patient/drug context.
        Returns dict with reversibility_results and preventability_results.
        No file I/O.
        """
        from infrastructure.adr_infrastructure.patient_adapter import to_adr_patient_data
        from infrastructure.rmm_infrastructure.rmm_generator import RMMGenerator

        adapted         = to_adr_patient_data(patient_data, drug_data)
        patient_context = RMMGenerator().build_patient_context(patient_data, drug_data)
        all_adrs        = self._extract_all_adrs(adr_analysis)

        if not all_adrs:
            return {"reversibility_results": {}, "preventability_results": {}, "total_adrs_analyzed": 0}

        # Fetch FDA sections for unique medicines
        medicines = list({a["medicine"] for a in all_adrs})
        fda_data: Dict[str, Any] = {}
        for med in medicines:
            print(f"  [RiskMitigationAnalyzer] Fetching FDA data for '{med}'...")
            fda_data[med] = self._fetch_fda_sections(med)
            time.sleep(0.3)

        reversibility_results:   Dict[str, Any] = {}
        preventability_results:  Dict[str, Any] = {}

        for adr in all_adrs:
            med     = adr["medicine"]
            name    = adr["adr_name"]
            key     = f"{med} - {name}"
            fda     = fda_data.get(med)

            rev  = self._classify_reversibility(adr, fda, patient_context)
            prev = self._classify_preventability(adr, fda, patient_context)

            reversibility_results[key]  = {"medicine": med, "adr_name": name, "adr_type": adr["adr_type"], **rev}
            preventability_results[key] = {"medicine": med, "adr_name": name, "adr_type": adr["adr_type"], **prev}
            time.sleep(1)

        return {
            "reversibility_results":  reversibility_results,
            "preventability_results": preventability_results,
            "total_adrs_analyzed":    len(all_adrs),
        }
