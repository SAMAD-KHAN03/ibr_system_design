import re
from typing import Dict, Any, List, Optional


def _extract_text(label_data: Dict[str, Any], field_name: str) -> Optional[str]:
    field_data = label_data.get(field_name, [])
    if field_data and len(field_data) > 0:
        return "\n\n".join(field_data)
    return None


def _extract_context(text: str, keyword: str, chars: int = 300) -> str:
    if not text:
        return ""
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    pos = text_lower.find(keyword_lower)
    if pos == -1:
        return text[:chars]
    start = max(0, pos - chars // 2)
    end   = min(len(text), pos + chars // 2)
    context = text[start:end].strip()
    if start > 0:
        context = "..." + context
    if end < len(text):
        context = context + "..."
    return context


def _deduplicate_adrs(adrs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen   = set()
    unique = []
    for adr in adrs:
        if not adr.get("adr_name"):
            continue
        key = (adr["medicine"].lower(), adr["adr_name"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(adr)
    return unique


def _can_patient_be_pregnant(patient_data: Dict[str, Any]) -> bool:
    patient   = patient_data.get("patient", {})
    gender    = patient.get("gender", "").lower()
    age       = patient.get("age", 0)
    condition = patient.get("condition", "").lower()
    diagnosis = patient.get("diagnosis", "").lower()

    if "male" in gender and "female" not in gender:
        return False
    if "female" in gender or gender == "f":
        if age > 50:
            if "pregnan" not in condition and "pregnan" not in diagnosis:
                return False
    return True
