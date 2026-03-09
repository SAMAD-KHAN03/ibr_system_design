from domain.enums import PreventabilityCategory
from scoring.weighted_score_rule import WeightedScoreRule

COMPONENT_NAME = "RiskMitigation"

class PreventabilityRule(WeightedScoreRule):
    """R4 — Risk Preventability. Non-preventable=3×80=240, Preventable=2×50=100"""
    def __init__(self):
        super().__init__(
            name="R4_RiskPreventability",
            component_name=COMPONENT_NAME,
            score_map={
                PreventabilityCategory.NON_PREVENTABLE: 3,
                PreventabilityCategory.PREVENTABLE:     2,
            },
            weight_map={
                PreventabilityCategory.NON_PREVENTABLE: 80,
                PreventabilityCategory.PREVENTABLE:     50,
            },
        )