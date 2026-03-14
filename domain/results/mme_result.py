"""
domain/results/mme_result.py

Stores the outcome of the MME (Molecule Market Experience) component — Factor B2.

B2 scoring (from iBR sheet):
  ESTABLISHED  (> 5 years) → score=2, weight=60 → weighted=120
  NEW          (≤ 5 years) → score=1, weight=40 → weighted=40
"""

from dataclasses import dataclass
from typing import Optional
from core.results.component_results import ComponentResult
from domain.enums import MMECategory

COMPONENT_NAME = "MME"
MME_THRESHOLD_YEARS = 5


@dataclass
class MMEResult(ComponentResult):
    """
    Stores B2 Molecule Market Experience result.
    category → MMECategory used by MMERule.
    """

    @classmethod
    def build(
        cls,
        drug_name:     str,
        generic_name:  Optional[str],
        approval_date: Optional[str],
        years:         Optional[int],
        found:         bool,
    ) -> "MMEResult":
        """
        Derives MMECategory from years on market.

        ESTABLISHED : found=True  AND years > MME_THRESHOLD_YEARS
        NEW         : found=True  AND years ≤ MME_THRESHOLD_YEARS
                      OR found=False (no FDA data — treated as new/unknown,
                      conservative scoring)
        """
        if found and years is not None and years > MME_THRESHOLD_YEARS:
            category = MMECategory.ESTABLISHED
            output   = (
                f"{generic_name or drug_name} is first approved by USFDA on "
                f"{approval_date} and first approved by CDSCO on "
                f"[CDSCO approval date not available]. "
                f"{generic_name or drug_name} is in the market for more than "
                f"{years} years of post-market experience."
            )
        elif found and years is not None:
            category = MMECategory.NEW
            output   = (
                f"{generic_name or drug_name} was first approved by USFDA on "
                f"{approval_date}. It has {years} year(s) of post-market "
                f"experience — classified as a newer molecule."
            )
        else:
            category = MMECategory.NEW
            output   = (
                f"No USFDA NDA/BLA approval data found for '{drug_name}'. "
                f"Classified as NEW (conservative default)."
            )

        return cls(
            name=COMPONENT_NAME,
            category=category,
            metadata={
                "mme_category":  category.value,
                "drug_name":     drug_name,
                "generic_name":  generic_name,
                "approval_date": approval_date,
                "years":         years,
                "found":         found,
                "threshold":     MME_THRESHOLD_YEARS,
                "output":        output,
            },
        )
