"""
domain/components/mme_component.py

B2 — Molecule Market Experience component.

Checks the primary drug under review against the FDA drugsfda.json API
to determine how long it has been on the market.

Scoring (MMERule):
  ESTABLISHED (> 5 years) → 2 × 60 = 120
  NEW         (≤ 5 years) → 1 × 40 = 40

Only the PRIMARY drug is checked — background medications (ongoing, past)
are not assessed for market experience since only the new medication's
experience is relevant to the prescribing decision.
"""

from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.results.mme_result import MMEResult
from infrastructure.mme.fda_mme_checker import FDAMMEChecker
from infrastructure.approvalstatus_infrastructure.usfda_checker import _extract_active_ingredient


class MMEComponent(Component):
    """
    Queries FDA drugsfda.json for the primary drug's first NDA/BLA approval
    date and calculates years of post-market experience.

    Pipeline behaviour
    ------------------
    * Found, established (>5y) → ExecutionResult.ok()  — ESTABLISHED
    * Found, new (≤5y)         → ExecutionResult.ok()  — NEW
    * Not found                → ExecutionResult.ok()  — NEW (conservative)
    * API error                → ExecutionResult.fail() with warning

    Never halts the pipeline — a missing MME result is a soft failure.
    """

    NAME = "MME"

    def __init__(self, checker: FDAMMEChecker = None):
        self._checker = checker or FDAMMEChecker()

    @property
    def component_name(self) -> str:
        return self.NAME

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        drug_name = context.drug_name

        if not drug_name:
            context.add_warning("MME: no primary drug name found — skipped.")
            result = MMEResult.build(
                drug_name="unknown", generic_name=None,
                approval_date=None, years=None, found=False,
            )
            context.add_result(result)
            return ExecutionResult.fail("No drug name available")

        # Normalise name — strip dosage/form e.g. "Furosemide 40 MG Oral Tablet" → "Furosemide"
        clean_name = _extract_active_ingredient(drug_name)
        if clean_name != drug_name:
            print(f"  [MME] Normalised '{drug_name}' → '{clean_name}'")

        print(f"  [MME] Checking market experience for '{clean_name}'...")

        fda_data = self._checker.fetch(clean_name)

        if fda_data:
            result = MMEResult.build(
                drug_name=drug_name,
                generic_name=fda_data["generic_name"],
                approval_date=fda_data["approval_date"],
                years=fda_data["years"],
                found=True,
            )
            print(
                f"  ✓ [MME] {clean_name} — {fda_data['years']}y on market "
                f"({result.category.value})"
            )
        else:
            context.add_warning(
                f"MME: no NDA/BLA data found for '{clean_name}' — defaulting to NEW."
            )
            result = MMEResult.build(
                drug_name=drug_name,
                generic_name=None,
                approval_date=None,
                years=None,
                found=False,
            )
            print(f"  ⚠  [MME] No FDA data for '{clean_name}' — category=NEW")

        context.add_result(result)
        return ExecutionResult.ok(data=result.metadata)
