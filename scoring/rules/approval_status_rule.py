from domain.enums import ApprovalCategory
from domain.results.approval_status_result import COMPONENT_NAME
from scoring.weighted_score_rule import WeightedScoreRule

class ApprovalStatusRule(WeightedScoreRule):
    """B1 — Approval Status. score×weight: Approved=2×70=140, Off-label=1×50=50"""
    def __init__(self):
        super().__init__(
            name="B1_ApprovalStatus",
            component_name=COMPONENT_NAME,
            score_map={
                ApprovalCategory.APPROVED:  2,
                ApprovalCategory.OFF_LABEL: 1,
                ApprovalCategory.NOT_FOUND: 0,
            },
            weight_map={
                ApprovalCategory.APPROVED:  70,
                ApprovalCategory.OFF_LABEL: 50,
                ApprovalCategory.NOT_FOUND: 0,
            },
        )
