import os
import requests
import re
from typing import Optional

class FDALabelFetcher:
    """
    Infrastructure-layer service: fetches raw FDA label sections for a drug.
    Updated for EC2: handles drug name normalization, hardcoded API key, 
    and extended timeouts.
    """

    BASE_URL = "https://api.fda.gov/drug/label.json"
    # Hardcoded key as requested for EC2 stability
    API_KEY = "9YewXTTqM2xa5qM5cD9s4BE8T9aupHlaNhGWgYOx"

    _SECTION_KEYS = {
        "contraindications": ["contraindications"],
        "boxed_warning":     ["boxed_warning"],
        "warnings":          ["warnings_and_cautions", "warnings"],
        "pregnancy":         ["pregnancy", "teratogenic_effects"],
    }

    def __init__(self, timeout: int = 30): # Increased from 15 to 30 for EC2
        self._timeout = timeout
        self._session = requests.Session()
        # Ensure the API key is always used
        self._session.headers.update({"X-Api-Key": self.API_KEY})

    def fetch_sections(self, drug_name: str) -> Optional[dict[str, str]]:
        raw = self._call_api(drug_name)
        if not raw:
            return None
        return self._extract_sections(raw)

    # ── Private ──────────────────────────────────────────────────────────────

    def _normalize_name(self, name: str) -> str:
        """Removes dosage and form specifications to prevent 404/Timeouts."""
        # Remove strengths (mg, ml, etc.)
        clean = re.sub(r'\d+(\.\d+)?\s*(mg|ml|g|%|mcg|units)', '', name, flags=re.IGNORECASE)
        # Remove forms (tablet, oral, etc.)
        clean = re.sub(r'(oral|tablet|capsule|injection|cream|ointment|solution)', '', clean, flags=re.IGNORECASE)
        return clean.strip().strip(',')

    def _call_api(self, drug_name: str) -> Optional[dict]:
        clean_name = self._normalize_name(drug_name)
        try:
            params: dict = {
                "search": (
                    f'openfda.generic_name:"{clean_name}" '
                    f'OR openfda.brand_name:"{clean_name}"'
                ),
                "limit": 1,
            }

            resp = self._session.get(self.BASE_URL, params=params, timeout=self._timeout)
            
            if resp.status_code != 200:
                # Log the failure but don't crash
                return None
                
            results = resp.json().get("results", [])
            return results[0] if results else None
        except Exception as exc:
            # Detailed error logging for EC2 debugging
            print(f"  [FDALabelFetcher] API error for '{clean_name}': {exc}")
            return None

    def _extract_sections(self, label: dict) -> dict[str, str]:
        out: dict[str, str] = {}
        for section, keys in self._SECTION_KEYS.items():
            for key in keys:
                value = label.get(key)
                if value:
                    out[section] = "\n".join(value) if isinstance(value, list) else value
                    break
            else:
                out[section] = ""
        return out