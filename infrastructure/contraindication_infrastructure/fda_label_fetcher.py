import os
import requests
from typing import Optional


class FDALabelFetcher:
    """
    Infrastructure-layer service: fetches raw FDA label sections for a drug.

    Single Responsibility: only HTTP + JSON extraction.
    Returns raw text strings — zero domain logic lives here.
    """

    BASE_URL = "https://api.fda.gov/drug/label.json"

    _SECTION_KEYS = {
        "contraindications": ["contraindications"],
        "boxed_warning":     ["boxed_warning"],
        "warnings":          ["warnings_and_cautions", "warnings"],
        "pregnancy":         ["pregnancy", "teratogenic_effects"],
    }

    def __init__(self, timeout: int = 15):
        self._timeout = timeout
        self._api_key = os.getenv("FDA_API_KEY", "")
        self._session = requests.Session()

    def fetch_sections(self, drug_name: str) -> Optional[dict[str, str]]:
        """
        Returns a dict with keys: contraindications, boxed_warning, warnings, pregnancy.
        Returns None if the API call fails or returns no results.
        """
        raw = self._call_api(drug_name)
        if not raw:
            return None
        return self._extract_sections(raw)

    # ── Private ──────────────────────────────────────────────────────────────

    def _call_api(self, drug_name: str) -> Optional[dict]:
        try:
            params: dict = {
                "search": (
                    f'openfda.generic_name:"{drug_name}" '
                    f'OR openfda.brand_name:"{drug_name}"'
                ),
                "limit": 1,
            }
            if self._api_key:
                params["api_key"] = self._api_key

            resp = self._session.get(self.BASE_URL, params=params, timeout=self._timeout)
            if resp.status_code != 200:
                return None
            results = resp.json().get("results", [])
            return results[0] if results else None
        except Exception as exc:
            print(f"  [FDALabelFetcher] API error for '{drug_name}': {exc}")
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