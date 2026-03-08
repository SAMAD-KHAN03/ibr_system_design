from domain.enums import ReversibilityCategory
from scoring.weighted_score_rule import WeightedScoreRule

COMPONENT_NAME = "RiskReversibility"

class ReversibilityRule(WeightedScoreRule):
    """R5 — Risk Reversibility. Irreversible=3×95=285, Reversible=1×40=40"""
    def __init__(self):
        super().__init__(
            name="R5_RiskReversibility",
            component_name=COMPONENT_NAME,
            score_map={
                ReversibilityCategory.IRREVERSIBLE: 3,
                ReversibilityCategory.REVERSIBLE:   1,
            },
            weight_map={
                ReversibilityCategory.IRREVERSIBLE: 95,
                ReversibilityCategory.REVERSIBLE:   40,
            },
        )
