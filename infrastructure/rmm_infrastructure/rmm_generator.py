import os
import re
import time
import requests
import json
from typing import Dict, List, Any, Optional

from infrastructure.adr_infrastructure.helpers import _extract_text


class RMMGenerator:
    """
    Infrastructure service: generates Risk Minimization Measures (RMM) table.

    Corresponds to Step 4 in the original prototype.
    Accepts ADR analysis dict directly (no file I/O) and returns the rmm_table list.
    Claude client is injected so the component can stub it in tests.
    """

    _MODEL = "claude-sonnet-4-6"

    def __init__(self):
        self._fda_api_key  = os.getenv("FDA_API_KEY", "")
        self._fda_base_url = "https://api.fda.gov/drug/label.json"
        self._client       = self._init_claude()

    # ── Claude setup ─────────────────────────────────────────────────────────

    def _init_claude(self):
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            return None
        try:
            import anthropic
            return anthropic.Anthropic(api_key=anthropic_key)
        except ImportError:
            return None

    # ── FDA fetch (shared logic) ──────────────────────────────────────────────

    def _fetch_fda_sections(self, medicine_name: str) -> Optional[Dict[str, Any]]:
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

        label = all_results[0]
        for r in all_results:
            gnames = r.get("openfda", {}).get("generic_name", [])
            if len(gnames) == 1 and medicine_lower in gnames[0].lower():
                label = r
                break

        return {
            "drug_name":              medicine_name,
            "warnings_and_cautions":  _extract_text(label, "warnings_and_cautions"),
            "warnings":               _extract_text(label, "warnings"),
            "adverse_reactions":      _extract_text(label, "adverse_reactions"),
            "drug_interactions":      _extract_text(label, "drug_interactions"),
            "dosage_and_administration": _extract_text(label, "dosage_and_administration"),
        }

    # ── Patient context builder ───────────────────────────────────────────────

    def build_patient_context(self, patient_data: dict, drug_data: dict) -> str:
        """Builds plain-text patient context string for Claude prompts."""
        from infrastructure.adr_infrastructure.patient_adapter import to_adr_patient_data
        adapted     = to_adr_patient_data(patient_data, drug_data)
        patient     = adapted["patient"]
        age         = patient.get("age", "unknown")
        gender      = patient.get("gender", "unknown")
        diagnosis   = patient.get("diagnosis", "")
        is_pregnant = patient.get("is_pregnant", False)
        trimester   = patient.get("trimester")
        is_lactating = patient.get("is_lactating", False)
        
        # New field from Flutter PatientModel
        menstrual_history = patient.get("menstrual_history") 
        
        medical_history = adapted.get("MedicalHistory", [])
        active_conditions = [h["diagnosisName"] for h in medical_history if h.get("status") == "Active"]

        age_val = age if age != "unknown" else 0
        is_elderly    = isinstance(age_val, int) and age_val >= 65
        is_pediatric  = isinstance(age_val, int) and age_val < 18
        is_immuno     = "transplant" in diagnosis.lower() or "immunosuppressed" in diagnosis.lower()
        age_category  = "geriatric" if is_elderly else ("pediatric" if is_pediatric else "adult")

        lines = [
            f"Patient Profile:",
            f"- Age: {age} years ({age_category})",
            f"- Gender: {gender}",
            f"- Primary Diagnosis: {diagnosis}",
            f"- Immunosuppressed: {'Yes' if is_immuno else 'No'}",
        ]

        # Added female-specific patient context
        if gender.lower() in ("female", "f"):
            lines.append(f"- Pregnancy Status: {'Pregnant' if is_pregnant else 'Not Pregnant'}")
            
            if is_pregnant:
                lines.append(f"- Trimester: {trimester or 'Unknown'}")
            
            # Added Menstrual History from PatientModel
            if menstrual_history:
                lines.append(f"- Menstrual History: {menstrual_history}")
                
            if is_lactating:
                lines.append("- Lactation: Active")

        if active_conditions:
            lines.append(f"- Active Comorbidities: {', '.join(active_conditions)}")

        lines.append("\nPATIENT-SPECIFIC MONITORING CONSIDERATIONS:")
        if is_elderly:
            lines.append("- Elderly: Requires more frequent monitoring (reduced organ reserve, polypharmacy)")

    # ── Section 5 monitoring extraction ──────────────────────────────────────

    def _extract_section5_monitoring(self, adr_name: str, section5_text: str) -> str:
        if not section5_text:
            return "NA"
        adr_lower = adr_name.lower()
        s5_lower  = section5_text.lower()

        variations = [adr_lower]
        if any(t in adr_lower for t in ["hepat", "liver"]):
            variations += ["hepat", "liver", "lft", "alt", "ast"]
        elif any(t in adr_lower for t in ["pulmonary", "lung"]):
            variations += ["pulmonary", "chest x-ray", "respiratory"]
        elif any(t in adr_lower for t in ["renal", "kidney"]):
            variations += ["renal", "kidney", "creatinine", "egfr"]
        elif any(t in adr_lower for t in ["cardiac", "heart"]):
            variations += ["cardiac", "ecg", "qt", "arrhythmia"]
        elif "thyroid" in adr_lower:
            variations += ["thyroid", "tsh", "t4"]
        elif "lactic acidosis" in adr_lower:
            variations += ["lactic", "lactate", "acidosis", "renal function"]

        relevant = ""
        for v in variations:
            pos = s5_lower.find(v)
            if pos != -1:
                start = max(0, pos - 250)
                end   = min(len(section5_text), pos + 250)
                relevant = section5_text[start:end]
                break
        if not relevant:
            return "NA"

        monitor_kw = ["monitor", "obtain", "measure", "check", "assess", "evaluate",
                      "baseline", "periodic", "regularly", "every", "before", "during", "test"]
        sentences = re.split(r"[.!?]\s+", relevant)
        hits = [s.strip() for s in sentences if any(k in s.lower() for k in monitor_kw) and len(s.strip()) > 20]
        return ". ".join(hits[:2]) if hits else "NA"

    # ── Claude: proactive symptoms ────────────────────────────────────────────

    def _generate_proactive_actions(
        self, medicine: str, adr_name: str, fda_sections: dict, patient_context: str = ""
    ) -> str:
        if not self._client:
            return f"Monitor patient for signs and symptoms of {adr_name}"

        s5 = fda_sections.get("warnings_and_cautions") or fda_sections.get("warnings", "")
        s6 = fda_sections.get("adverse_reactions", "")
        pt = f"\n\n{patient_context}" if patient_context else ""

        prompt = (
            f"You are a clinical pharmacovigilance expert. For {medicine}, identify clinical signs "
            f"and symptoms to monitor for the ADR: {adr_name}.\n\n"
            f"FDA Section 5 (excerpt):\n{s5[:2500] if s5 else 'Not available'}\n\n"
            f"FDA Section 6 (excerpt):\n{s6[:2500] if s6 else 'Not available'}"
            f"{pt}\n\n"
            "Return ONLY a comma-separated list of symptoms. No preamble, no explanations."
        )
        try:
            response = self._client.messages.create(
                model=self._MODEL,
                max_tokens=1000,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip().replace("\n", ", ")
            text = re.sub(r"^(symptoms?|signs?|monitor):\s*", "", text, flags=re.IGNORECASE)
            return text
        except Exception as exc:
            print(f"  [RMMGenerator] Claude error (proactive): {exc}")
            return f"Monitor patient for signs and symptoms of {adr_name}"

    # ── Claude: immediate actions ─────────────────────────────────────────────

    _STRICT_RULES = {
        "lactic acidosis":          "Discontinuation with initiation of better alternatives in safety and efficacy",
        "stevens-johnson syndrome":  "Discontinuation with initiation of better alternatives in safety and efficacy AND/OR initiation of required supplementations",
        "toxic epidermal necrolysis":"Discontinuation with initiation of better alternatives in safety and efficacy AND/OR initiation of required supplementations",
        "anaphylaxis":               "Discontinuation with initiation of better alternatives in safety and efficacy AND/OR initiation of required supplementations",
        "agranulocytosis":           "Discontinuation with initiation of better alternatives in safety and efficacy",
        "aplastic anemia":           "Discontinuation with initiation of better alternatives in safety and efficacy",
        "acute liver failure":       "Discontinuation with initiation of better alternatives in safety and efficacy",
        "hepatic failure":           "Discontinuation with initiation of better alternatives in safety and efficacy",
        "respiratory failure":       "Discontinuation with initiation of better alternatives in safety and efficacy",
        "cardiac arrest":            "Discontinuation with initiation of better alternatives in safety and efficacy",
        "ventricular fibrillation":  "Dose optimisation, or temporary interruption, or discontinuation with initiation of better alternatives in safety and efficacy",
    }

    def _select_immediate_actions(
        self, medicine: str, adr_name: str, risk_type: str,
        fda_sections: dict, patient_context: str = "", is_drug_interaction: bool = False
    ) -> Dict[str, str]:
        adr_lower = adr_name.lower()
        for key, action in self._STRICT_RULES.items():
            if key in adr_lower:
                return {"action": action, "reasoning": f"{adr_name} requires immediate intervention per FDA guidelines."}

        if not self._client:
            if "LT" in risk_type or "Fatal" in risk_type:
                return {"action": "Discontinuation with initiation of better alternatives in safety and efficacy",
                        "reasoning": f"Life-threatening nature of {adr_name} requires immediate cessation"}
            return {"action": "Dose optimisation, or temporary interruption",
                    "reasoning": f"Serious ADR requiring clinical monitoring and possible intervention"}

        s5    = fda_sections.get("warnings_and_cautions") or fda_sections.get("warnings", "")
        dosage = fda_sections.get("dosage_and_administration", "")
        pt    = f"\n\n{patient_context}" if patient_context else ""

        prompt = (
            f"Medicine: {medicine}\nADR: {adr_name}\nRisk Type: {risk_type}\n"
            f"Drug Interaction: {is_drug_interaction}\n\n"
            f"FDA Section 5 (excerpt):\n{s5[:1800] if s5 else 'Not available'}\n\n"
            f"FDA Dosage (excerpt):\n{dosage[:800] if dosage else 'Not available'}"
            f"{pt}\n\n"
            "Select one or more actions from: Dose optimisation | Temporary interruption | "
            "Discontinuation with initiation of better alternatives in safety and efficacy | "
            "Initiation of required supplementations\n\n"
            "Respond EXACTLY:\nACTION: <action>\nREASONING: <one sentence>"
        )
        try:
            response = self._client.messages.create(
                model=self._MODEL,
                max_tokens=1000,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            action_m    = re.search(r"ACTION:\s*(.+?)(?:\n|REASONING:)", text, re.IGNORECASE | re.DOTALL)
            reasoning_m = re.search(r"REASONING:\s*(.+?)(?:\n|$)", text, re.IGNORECASE | re.DOTALL)
            action    = action_m.group(1).strip()    if action_m    else "Discontinuation with initiation of better alternatives in safety and efficacy"
            reasoning = reasoning_m.group(1).strip() if reasoning_m else f"Based on severity of {adr_name}"
            return {"action": action, "reasoning": reasoning}
        except Exception as exc:
            print(f"  [RMMGenerator] Claude error (actions): {exc}")
            return {"action": "Discontinuation with initiation of better alternatives in safety and efficacy",
                    "reasoning": f"Based on severity of {adr_name}"}

    # ── Main entrypoint ───────────────────────────────────────────────────────

    def generate(
        self,
        adr_analysis: Dict[str, Any],
        patient_data: dict,
        drug_data: dict,
    ) -> List[Dict[str, Any]]:
        """
        Accepts the structured dict from ADRAnalyzer.analyze() + patient/drug context.
        Returns rmm_table list — no file I/O.
        """
        medications     = adr_analysis.get("medications", [])
        patient_context = self.build_patient_context(patient_data, drug_data)

        # Fetch FDA sections for all medications
        fda_data: Dict[str, Any] = {}
        for med in medications:
            print(f"  [RMMGenerator] Fetching FDA data for '{med}'...")
            fda_data[med] = self._fetch_fda_sections(med)
            time.sleep(0.3)

        rmm_entries: List[Dict[str, Any]] = []

        # ── LT ADRs ──────────────────────────────────────────────────────────
        lt_adrs = adr_analysis.get("factor_3_2", {}).get("LT_ADRs", {})
        for medicine, data in lt_adrs.items():
            fda = fda_data.get(medicine)
            if not fda:
                continue
            all_adrs = data.get("with_risk_factors", []) + data.get("without_risk_factors", [])
            for adr in all_adrs:
                adr_name = adr["adr_name"]
                s5_text  = fda.get("warnings_and_cautions") or fda.get("warnings", "")
                entry    = {
                    "medicine":                                medicine,
                    "risk_type":                               "LT/Fatal ADR",
                    "risk_description":                        adr_name,
                    "section_5_warnings_and_precautions_extract": self._extract_section5_monitoring(adr_name, s5_text),
                    "proactive_actions_symptoms_to_monitor":   self._generate_proactive_actions(medicine, adr_name, fda, patient_context),
                    **self._prefix_immediate(self._select_immediate_actions(medicine, adr_name, "LT/Fatal ADR", fda, patient_context)),
                }
                rmm_entries.append(entry)
                time.sleep(1)

        # ── Serious ADRs ──────────────────────────────────────────────────────
        serious_adrs = adr_analysis.get("factor_3_2", {}).get("Serious_ADRs", {})
        for medicine, data in serious_adrs.items():
            fda = fda_data.get(medicine)
            if not fda:
                continue
            all_adrs = data.get("with_risk_factors", []) + data.get("without_risk_factors", [])
            for adr in all_adrs:
                adr_name = adr["adr_name"]
                s5_text  = fda.get("warnings_and_cautions") or fda.get("warnings", "")
                entry    = {
                    "medicine":                                medicine,
                    "risk_type":                               "Non-LT/Fatal, But Serious ADR",
                    "risk_description":                        adr_name,
                    "section_5_warnings_and_precautions_extract": self._extract_section5_monitoring(adr_name, s5_text),
                    "proactive_actions_symptoms_to_monitor":   self._generate_proactive_actions(medicine, adr_name, fda, patient_context),
                    **self._prefix_immediate(self._select_immediate_actions(medicine, adr_name, "Non-LT/Fatal, But Serious ADR", fda, patient_context)),
                }
                rmm_entries.append(entry)
                time.sleep(1)

        # ── Drug Interactions ─────────────────────────────────────────────────
        interactions = adr_analysis.get("factor_3_3", {}).get("interactions", {})
        for medicine, data in interactions.items():
            fda = fda_data.get(medicine)
            if not fda:
                continue
            all_inter = (
                data.get("contraindicated", []) +
                data.get("lt_interactions", []) +
                data.get("serious_interactions", []) +
                data.get("non_serious_interactions", [])
            )
            for inter in all_inter:
                interacting = inter["interacting_drug"]
                itype       = inter["interaction_type"]
                risk_type   = {
                    "contraindicated":  "Contraindicated Drug-Drug Interaction",
                    "life-threatening": "LT Drug-Drug Interaction",
                    "serious":          "Serious Drug-Drug Interaction",
                }.get(itype, "Non-serious Drug-Drug Interaction")

                s7_text = fda.get("drug_interactions", "")
                s5_ext  = self._extract_section5_monitoring(interacting, s7_text)
                if s5_ext == "NA" and s7_text:
                    pos = s7_text.lower().find(interacting.lower())
                    if pos != -1:
                        s5_ext = s7_text[max(0, pos - 150): min(len(s7_text), pos + 150)].strip()

                inter_fda = {
                    "warnings_and_cautions": f"Drug Interaction Context: {inter['context']}",
                    "adverse_reactions":     "",
                    "drug_interactions":     s7_text,
                    "dosage_and_administration": fda.get("dosage_and_administration", ""),
                }
                entry = {
                    "medicine":                                medicine,
                    "risk_type":                               risk_type,
                    "risk_description":                        f"Drug interaction: {medicine} + {interacting}",
                    "section_5_warnings_and_precautions_extract": s5_ext,
                    "proactive_actions_symptoms_to_monitor":   self._generate_proactive_actions(medicine, f"interaction with {interacting}", inter_fda, patient_context),
                    **self._prefix_immediate(self._select_immediate_actions(medicine, f"interaction with {interacting}", risk_type, inter_fda, patient_context, is_drug_interaction=True)),
                }
                rmm_entries.append(entry)
                time.sleep(1)

        return rmm_entries

    @staticmethod
    def _prefix_immediate(result: Dict[str, str]) -> Dict[str, str]:
        return {
            "immediate_actions_required": result["action"],
            "immediate_actions_reasoning": result["reasoning"],
        }