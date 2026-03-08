from domain.enums import SeverityCategory
from scoring.weighted_score_rule import WeightedScoreRule

COMPONENT_NAME = "DiseaseSeverity"

class SeverityRule(WeightedScoreRule):
    """B6 — Severity of Disease / Consequence of non-treatment."""
    def __init__(self):
        super().__init__(
            name="B6_DiseaseSeverity",
            component_name=COMPONENT_NAME,
            score_map={
                SeverityCategory.ACUTE_LIFE_THREATENING:      3,
                SeverityCategory.ACUTE_NON_LIFE_THREATENING:  3,
                SeverityCategory.CHRONIC_LIFE_THREATENING:    3,
                SeverityCategory.CHRONIC_NON_LIFE_THREATENING:2,
                SeverityCategory.QUALITY_OF_LIFE:             1,
                SeverityCategory.SIGNS_SYMPTOMS:              1,
            },
            weight_map={
                SeverityCategory.ACUTE_LIFE_THREATENING:      100,
                SeverityCategory.ACUTE_NON_LIFE_THREATENING:  90,
                SeverityCategory.CHRONIC_LIFE_THREATENING:    80,
                SeverityCategory.CHRONIC_NON_LIFE_THREATENING:60,
                SeverityCategory.QUALITY_OF_LIFE:             40,
                SeverityCategory.SIGNS_SYMPTOMS:              20,
            },
        )
