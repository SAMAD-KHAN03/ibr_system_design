# domain/results/regulatory_result.py
from dataclasses import dataclass
from core.component_results import ComponentResult

@dataclass
class ApprovalStatusResult(ComponentResult):
    def approval_result_more_than_five_years():
            return ComponentResult(
                  name="Approval Status",
                  metadata={
                        "description":"the medicine is approved by the us fda"
                  }
            )