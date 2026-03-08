import requests
import pandas as pd
from typing import List, Dict, Optional
from infrastructure.alternatives_infrastructure import RxNormClient


class FDAAlternativesFinder:
    """
    Find alternative medications for a given medicine and condition using FDA API.
    Falls back to RxNorm for drug class when FDA returns unknown/null.
    """

    BASE_URL = "https://api.fda.gov/drug/label.json"

    def __init__(self):
        self.session    = requests.Session()
        self._rxnorm    = RxNormClient()

    def search_by_indication(self, condition: str, limit: int = 1000) -> List[Dict]:
        search_query = f'indications_and_usage:"{condition}"'
        params = {"search": search_query, "limit": limit}

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            print(f"  [Alternatives] Found {len(results)} drug labels for '{condition}'")
            return results
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"  [Alternatives] No results for '{condition}'")
                return []
            print(f"  [Alternatives] HTTP Error: {e}")
            return []
        except Exception as e:
            print(f"  [Alternatives] Error: {e}")
            return []

    def extract_active_moieties(
        self, results: List[Dict], exclude_medicine: str = None
    ) -> pd.DataFrame:
        medications   = []
        exclude_lower = exclude_medicine.lower() if exclude_medicine else None

        for result in results:
            openfda         = result.get("openfda", {})
            brand_name      = (openfda.get("brand_name",    ["Unknown"])[0] if openfda.get("brand_name")    else "Unknown")
            generic_name    = (openfda.get("generic_name",  ["Unknown"])[0] if openfda.get("generic_name")  else "Unknown")
            substance_names = openfda.get("substance_name", [])
            manufacturer    = (openfda.get("manufacturer_name", ["Unknown"])[0] if openfda.get("manufacturer_name") else "Unknown")
            product_type    = (openfda.get("product_type",  ["Unknown"])[0] if openfda.get("product_type")  else "Unknown")
            route           = openfda.get("route", ["Unknown"])
            route_str       = ", ".join(route) if route else "Unknown"

            # Store raw FDA pharm class — RxNorm fallback applied only on top_n later
            pharm_class = openfda.get("pharm_class_epc", []) or openfda.get("pharm_class_moa", [])
            drug_class  = pharm_class[0] if pharm_class else None

            if substance_names:
                for substance in substance_names:
                    if exclude_lower and exclude_lower in substance.lower():
                        continue
                    medications.append({
                        "Active_Moiety": substance,
                        "Brand_Name":    brand_name,
                        "Generic_Name":  generic_name,
                        "Manufacturer":  manufacturer,
                        "Product_Type":  product_type,
                        "Route":         route_str,
                        "Drug_Class":    drug_class,
                    })
            else:
                if exclude_lower and (
                    exclude_lower in generic_name.lower()
                    or exclude_lower in brand_name.lower()
                ):
                    continue
                medications.append({
                    "Active_Moiety": generic_name,
                    "Brand_Name":    brand_name,
                    "Generic_Name":  generic_name,
                    "Manufacturer":  manufacturer,
                    "Product_Type":  product_type,
                    "Route":         route_str,
                    "Drug_Class":    drug_class,
                })

        df = pd.DataFrame(medications)
        if df.empty:
            return df

        df_unique = df.drop_duplicates(subset=["Active_Moiety"], keep="first")
        print(f"  [Alternatives] Unique active moieties: {len(df_unique)}")
        return df_unique

    def _enrich_drug_class(self, row: dict) -> str:
        """
        Called only on the final top_n rows.
        Returns FDA class if present, else calls RxNorm (max top_n HTTP calls).
        """
        drug_class = row.get("Drug_Class")
        if drug_class and isinstance(drug_class, str) and drug_class.lower() not in ("unknown", "none", ""):
            return drug_class
        return self._rxnorm.get_drug_class(row.get("Generic_Name", "")) or "Unknown"

    def get_top_alternatives(
        self, medicine: str, condition: str, top_n: int = 3
    ) -> List[Dict]:
        results = self.search_by_indication(condition)
        if not results:
            return []

        df_medications = self.extract_active_moieties(results, exclude_medicine=medicine)
        if df_medications.empty:
            return []

        df_rx = df_medications[
            df_medications["Product_Type"].str.contains("PRESCRIPTION", case=False, na=False)
        ]

        top_df = df_rx.head(top_n).copy()

        # RxNorm fallback — only on top_n rows (at most 3 HTTP calls)
        print(f"  [Alternatives] Enriching drug class for top {len(top_df)} alternatives...")
        top_df["Drug_Class"] = [self._enrich_drug_class(row) for row in top_df.to_dict("records")]

        alternatives_list = top_df.to_dict("records")
        print(f"  [Alternatives] Top {len(alternatives_list)} alternatives ready")
        return alternatives_list
