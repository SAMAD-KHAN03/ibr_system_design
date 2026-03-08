from domain.enums import ADRSeverityCategory
from scoring.weighted_score_rule import WeightedScoreRule

COMPONENT_NAME = "ADRSeverity"

class ADRSeverityRule(WeightedScoreRule):
    """R3 — Risk Severity (ADRs)."""
    def __init__(self):
        super().__init__(
            name="R3_ADRSeverity",
            component_name=COMPONENT_NAME,
            score_map={
                ADRSeverityCategory.LT_WITH_RISK_FACTORS: 3,
                ADRSeverityCategory.LT_NO_RISK_FACTORS:   3,
                ADRSeverityCategory.SERIOUS_WITH_RISK:    2,
                ADRSeverityCategory.SERIOUS_NO_RISK:      2,
                ADRSeverityCategory.NO_LT_SERIOUS_ADRS:   1,
                ADRSeverityCategory.NO_SERIOUS_ADRS:      0,
            },
            weight_map={
                ADRSeverityCategory.LT_WITH_RISK_FACTORS: 100,
                ADRSeverityCategory.LT_NO_RISK_FACTORS:   90,
                ADRSeverityCategory.SERIOUS_WITH_RISK:    80,
                ADRSeverityCategory.SERIOUS_NO_RISK:      60,
                ADRSeverityCategory.NO_LT_SERIOUS_ADRS:   30,
                ADRSeverityCategory.NO_SERIOUS_ADRS:      10,
            },
        )
