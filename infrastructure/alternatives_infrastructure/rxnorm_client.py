import requests
from typing import Optional


class RxNormClient:
    """
    Fetches drug class (MOA) from the RxNorm / RxClass APIs.
    Called as fallback when FDA returns unknown/null for drug class.
    """

    RXNORM_BASE  = "https://rxnav.nlm.nih.gov/REST"
    RXCLASS_BASE = "https://rxnav.nlm.nih.gov/REST/rxclass"

    def __init__(self, timeout: int = 10):
        self._timeout = timeout
        self._session = requests.Session()

    def get_drug_class(self, drug_name: str) -> Optional[str]:
        """
        Returns a drug class / MOA string for drug_name, or None if not found.
        Tries MOA first, falls back to EPC (Established Pharmacologic Class).
        """
        rxcui = self._get_rxcui(drug_name)
        if not rxcui:
            return None

        for class_type in ("MOA", "EPC", "PE"):
            result = self._get_class_by_rxcui(rxcui, class_type)
            if result:
                return result

        return None

    # ── Private ──────────────────────────────────────────────────────────────

    def _get_rxcui(self, drug_name: str) -> Optional[str]:
        try:
            resp = self._session.get(
                f"{self.RXNORM_BASE}/rxcui.json",
                params={"name": drug_name, "search": 1},
                timeout=self._timeout,
            )
            data = resp.json()
            ids  = data.get("idGroup", {}).get("rxnormId", [])
            return ids[0] if ids else None
        except Exception:
            return None

    def _get_class_by_rxcui(self, rxcui: str, class_type: str) -> Optional[str]:
        try:
            resp = self._session.get(
                f"{self.RXCLASS_BASE}/class/byRxcui.json",
                params={"rxcui": rxcui, "relaSource": "MEDRT", "relas": class_type},
                timeout=self._timeout,
            )
            data      = resp.json()
            concepts  = (
                data.get("rxclassDrugInfoList", {})
                    .get("rxclassDrugInfo", [])
            )
            if concepts:
                return concepts[0].get("rxclassMinConceptItem", {}).get("className")
            return None
        except Exception:
            return None
