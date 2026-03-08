import re
import requests


class USFDAChecker:
    """
    Infrastructure-layer service: wraps the OpenFDA HTTP API.

    Single Responsibility: HTTP calls + text extraction only.
    No domain logic lives here — callers decide what to do with the result.
    """

    LABEL_URL = "https://api.fda.gov/drug/label.json"
    _INDICATION_FIELDS = ("indications_and_usage", "purpose", "use")

    def __init__(self, timeout: int = 15):
        self._session = requests.Session()
        self._timeout = timeout

    # ── Public API ──────────────────────────────────────────────────────────

    def check_approval(self, drug: str, condition: str) -> bool:
        """Return True if the FDA label mentions *condition* for *drug*."""
        labels = self._fetch_labels(drug)
        indications = self._extract_indications(labels)
        return any(self._matches(condition, ind) for ind in indications)

    # ── Private helpers ─────────────────────────────────────────────────────

    def _fetch_labels(self, drug_name: str) -> dict:
        try:
            params = {
                "search": (
                    f'openfda.brand_name:"{drug_name}" '
                    f'openfda.generic_name:"{drug_name}"'
                ),
                "limit": 10,
            }
            response = self._session.get(self.LABEL_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
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