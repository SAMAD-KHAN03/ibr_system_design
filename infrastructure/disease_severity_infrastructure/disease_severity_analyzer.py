import json
import time
import os
from typing import Dict, List, Any, Optional


class DiseaseSeverityAnalyzer:
    """
    Infrastructure service: uses Gemini to classify the severity of untreated disease.
    Corresponds to Factor 2.6 in the original prototype.

    Accepts patient_data + drug_data directly (no file I/O).
    Returns structured dict keyed by disease name.
    """

    _MODEL = "gemini-2.0-flash"

    def __init__(self):
        self._client = self._init_gemini()

    def _init_gemini(self):
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            return None
        try:
            from google import genai
            return genai.Client(api_key=key)
        except ImportError:
            return None

    # ── Diagnosis extraction ──────────────────────────────────────────────────

    def _extract_diagnoses(self, patient_data: dict, drug_data: dict) -> List[str]:
        """Collects all distinct diagnoses from patient_data and drug_data."""
        from infrastructure.adr_infrastructure.patient_adapter import to_adr_patient_data
        adapted  = to_adr_patient_data(patient_data, drug_data)
        patient  = adapted["patient"]

        diagnosis_text = patient.get("diagnosis", "")
        condition_text = patient.get("condition", "")
        full           = f"{diagnosis_text}, {condition_text}".strip(", ")

        raw = [d.strip() for d in full.split(",") if d.strip()]
        seen, unique = set(), []
        for d in raw:
            if d.lower() not in seen:
                seen.add(d.lower())
                unique.append(d)
        return unique

    # ── Patient context builder ───────────────────────────────────────────────

    def _build_patient_context(self, patient_data: dict, drug_data: dict) -> str:
        from infrastructure.adr_infrastructure.patient_adapter import to_adr_patient_data
        adapted   = to_adr_patient_data(patient_data, drug_data)
        patient   = adapted["patient"]
        age       = patient.get("age", "unknown")
        gender    = patient.get("gender", "unknown")
        diagnosis = patient.get("diagnosis", "")
        is_pregnant = patient.get("is_pregnant", False)
        trimester   = patient.get("trimester")
        is_lactating = patient.get("is_lactating", False)
        medical_history = adapted.get("MedicalHistory", [])
        active_conditions = [h["diagnosisName"] for h in medical_history if h.get("status") == "Active"]

        age_val      = age if isinstance(age, int) else 0
        is_elderly   = age_val >= 65
        is_pediatric = 0 < age_val < 18
        is_immuno    = "transplant" in diagnosis.lower() or "immunosuppressed" in diagnosis.lower()
        age_cat      = "geriatric" if is_elderly else ("pediatric" if is_pediatric else "adult")

        lines = [
            f"PATIENT CONTEXT:",
            f"- Age: {age} ({age_cat})",
            f"- Gender: {gender}",
            f"- Diagnosis: {diagnosis}",
            f"- Immunosuppressed: {'Yes' if is_immuno else 'No'}",
        ]
        if gender.lower() in ("female", "f"):
            if is_pregnant:
                lines.append(f"- Pregnant (Trimester {trimester or 'Unknown'}): consequences affect mother and fetus")
            if is_lactating:
                lines.append("- Lactating: Active")
        if active_conditions:
            lines.append(f"- Active Comorbidities: {', '.join(active_conditions)}")
        return "\n".join(lines)

    # ── Gemini consequence analysis ───────────────────────────────────────────

    def _analyze_disease(self, disease: str, patient_context: str) -> Dict[str, Any]:
        fallback = {
            "disease": disease,
            "classifications": [{
                "category": "Unable to determine",
                "timeframe": "Unknown",
                "consequences_if_untreated": f"Unable to analyze consequences for {disease}",
                "severity": "Unknown",
                "specific_outcomes": [],
                "reliable_sources_used": [],
            }],
        }

        if not self._client:
            return fallback

        prompt = (
            f"You are a medical expert. Classify untreated {disease} consequences.\n"
            f"{patient_context}\n\n"
            "CATEGORIES (choose exactly one):\n"
            "1. Acute, life-threatening\n"
            "2. Acute, non-life-threatening\n"
            "3. Chronic, life-threatening\n"
            "4. Chronic, non-life-threatening\n\n"
            "RULES:\n"
            "- Type 2 Diabetes = Chronic, life-threatening\n"
            "- Hypertension = Chronic, life-threatening\n"
            "- CKD = Chronic, life-threatening\n"
            "- If death within hours-days without treatment → Acute, life-threatening\n\n"
            "DISEASE: {disease}\n\n"
            "Return ONLY valid JSON:\n"
            "{"
            '"disease":"...",'
            '"classifications":[{"category":"...","timeframe":"...","consequences_if_untreated":"• ...\n• ...","severity":"...","specific_outcomes":["..."],"reliable_sources_used":["..."]}]'
            "}"
        ).replace("{disease}", disease)

        try:
            resp = self._client.models.generate_content(model=self._MODEL, contents=prompt)
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as exc:
            print(f"  [DiseaseSeverityAnalyzer] Error for {disease}: {exc}")
            return fallback

    # ── Main entrypoint ───────────────────────────────────────────────────────

    def analyze(self, patient_data: dict, drug_data: dict) -> Dict[str, Any]:
        """
        Analyzes all diagnoses found in patient_data/drug_data.
        Returns dict with factor_2_6_consequences_of_non_treatment keyed by disease.
        No file I/O.
        """
        diagnoses       = self._extract_diagnoses(patient_data, drug_data)
        patient_context = self._build_patient_context(patient_data, drug_data)

        if not diagnoses:
            return {
                "diagnoses_analyzed": [],
                "factor_2_6_consequences_of_non_treatment": {},
                "total_diagnoses_analyzed": 0,
            }

        results: Dict[str, Any] = {}
        for i, disease in enumerate(diagnoses):
            print(f"  [DiseaseSeverityAnalyzer] Analyzing disease '{disease}' ({i+1}/{len(diagnoses)})...")
            results[disease] = self._analyze_disease(disease, patient_context)
            if i < len(diagnoses) - 1:
                time.sleep(1)

        return {
            "diagnoses_analyzed":                         diagnoses,
            "factor_2_6_consequences_of_non_treatment":   results,
            "total_diagnoses_analyzed":                   len(diagnoses),
        }
