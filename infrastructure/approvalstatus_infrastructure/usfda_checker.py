import requests
import re
import logging
from time import sleep

log = logging.getLogger(__name__)

class USFDAChecker:
    """
    Infrastructure-layer service: wraps the OpenFDA HTTP API.
    Updated for EC2 stability: includes API Key, extended timeout, and retries.
    """

    LABEL_URL = "https://api.fda.gov/drug/label.json"
    API_KEY = "9YewXTTqM2xa5qM5cD9s4BE8T9aupHlaNhGWgYOx"
    _INDICATION_FIELDS = ("indications_and_usage", "purpose", "use")

    def __init__(self, timeout: int = 30): 
        self._session = requests.Session()
        self._timeout = timeout
        self._session.headers.update({"X-Api-Key": self.API_KEY})

    def check_approval(self, drug: str, condition: str) -> bool:
        """Return True if the FDA label mentions *condition* for *drug*."""
        labels = self._fetch_labels(drug)
        indications = self._extract_indications(labels)
        return any(self._matches(condition, ind) for ind in indications)

    def _normalize_drug_name(self, drug_name: str) -> str:
        """
        Removes dosage (MG, ML, etc.) and forms (Tablet, Oral, etc.) 
        to ensure the FDA search finds a match.
        """
        # Remove strengths: e.g., "50 MG", "10%", "5ml/10ml"
        name = re.sub(r'\d+(\.\d+)?\s*(mg|ml|g|%|mcg|units)', '', drug_name, flags=re.IGNORECASE)
        # Remove forms and routes: e.g., "Oral Tablet", "Injection", "Cream"
        name = re.sub(r'(oral|tablet|capsule|injection|cream|ointment|gel|solution|suspension)', '', name, flags=re.IGNORECASE)
        # Clean up double spaces and trailing punctuation
        name = re.sub(r'\s+', ' ', name).strip().strip(',')
        return name

    def _fetch_labels(self, drug_name: str, retries: int = 2) -> dict:
        """Fetch labels with normalization to prevent 404 errors."""
        # Normalize: "Diclofenac 50 MG Oral Tablet" -> "Diclofenac"
        clean_name = self._normalize_drug_name(drug_name)
        
        params = {
            "search": (
                f'openfda.brand_name:"{clean_name}" '
                f'openfda.generic_name:"{clean_name}"'
            ),
            "limit": 5, 
        }
        
        for attempt in range(retries + 1):
            try:
                response = self._session.get(
                    self.LABEL_URL, 
                    params=params, 
                    timeout=self._timeout
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    log.warning(f"FDA API: No records found for normalized name '{clean_name}'")
                    return {}
                log.error(f"FDA API HTTP Error for '{clean_name}': {e}")
                break
            except requests.exceptions.Timeout:
                log.warning(f"FDA API Timeout for '{clean_name}' (Attempt {attempt + 1})")
                if attempt < retries:
                    sleep(1)
                    continue
            except Exception as e:
                log.error(f"FDA API Error for '{clean_name}': {str(e)}")
                break
        return {}

    def _extract_indications(self, payload: dict) -> list[str]:
        if not payload or "results" not in payload:
            return []

        indications: list[str] = []
        for result in payload["results"]:
            for field in self._INDICATION_FIELDS:
                raw = result.get(field)
                if not raw:
                    continue
                texts = raw if isinstance(raw, list) else [raw]
                for t in texts:
                    cleaned = self._clean(t)
                    if cleaned:
                        indications.append(cleaned)
        return indications

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _matches(condition: str, indication: str) -> bool:
        cond = condition.lower()
        txt = indication.lower()
        if cond in txt:
            return True
        words = cond.split()
        return len(words) > 1 and all(w in txt for w in words)