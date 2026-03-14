"""
infrastructure/fda_mme_checker.py

FDA Market Experience (MME) infrastructure service.
Wraps the drugsfda.json API — single responsibility: HTTP + data extraction only.
No domain logic, no scoring, no enums.

Original prototype: fda/mme_checker.py
Ported to infrastructure layer: file I/O and scoring references removed,
logic moved to free functions, class kept as thin HTTP wrapper.
"""

import requests
from datetime import datetime
from typing import Optional, Dict


class FDAMMEChecker:
    """
    Queries the FDA drugsfda.json endpoint to find the earliest NDA/BLA
    approval date for a drug, then calculates years on market.

    Filters applied (matching original prototype logic):
      - Excludes ANDA applications (generic drugs) — keeps NDA/BLA only
      - Excludes entries where ALL products are DISCONTINUED
      - Uses the ORIG submission date as the approval reference date
    """

    BASE_URL = "https://api.fda.gov/drug/drugsfda.json"

    def __init__(self, timeout: int = 15):
        self._session = requests.Session()
        self._timeout = timeout

    def fetch(self, drug_name: str) -> Optional[Dict]:
        """
        Fetches and processes FDA market experience data for a drug.

        Returns
        -------
        {
            "generic_name":   str,   # comma-separated active ingredients
            "approval_date":  str,   # "DD-Mon-YYYY"
            "years":          int,   # years since first approval
        }
        or None if no matching NDA/BLA found.
        """
        try:
            params = {
                "search": (
                    f'products.brand_name:"{drug_name}" '
                    f'products.active_ingredients.name:"{drug_name}"'
                ),
                "limit": 50,
            }
            response = self._session.get(self.BASE_URL, params=params, timeout=self._timeout)
            if response.status_code != 200:
                return None
            results = response.json().get("results", [])
            return self._process_results(results,drug_name=drug_name)
        except Exception as exc:
            print(f"  [FDAMMEChecker] API error for '{drug_name}': {exc}")
            return None

    def _process_results(self, results: list,drug_name:str) -> Optional[Dict]:
        earliest_date = None
        best_match    = None

        for res in results:
            app_num = res.get("application_number", "")

            # Keep only NDA / BLA — exclude generics (ANDA)
            if app_num.startswith("ANDA") or not (
                app_num.startswith("NDA") or app_num.startswith("BLA")
            ):
                continue

            # Skip if all products are discontinued
            products = res.get("products", [])
            if all(
                "DISCONTINUED" in p.get("marketing_status", "").upper()
                for p in products
            ):
                continue

            # Find the ORIG submission date
            subs = res.get("submissions", [])
            orig = next(
                (s for s in subs if s.get("submission_type") == "ORIG"), None
            )
            date_str = orig.get("submission_status_date") if orig else None
            if not date_str:
                continue

            try:
                date_obj = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                continue

            if earliest_date is None or date_obj < earliest_date:
                earliest_date = date_obj
                generic_name  = ", ".join(
                    i.get("name", "")
                    for p in products
                    for i in p.get("active_ingredients", [])
                    if i.get("name")
                )
                best_match = {
                    "generic_name": generic_name or drug_name,
                    "date":         date_obj,
                }

        if not best_match:
            return None

        years = int((datetime.now() - best_match["date"]).days / 365.25)
        return {
            "generic_name":  best_match["generic_name"],
            "approval_date": best_match["date"].strftime("%d-%b-%Y"),
            "years":         years,
        }
