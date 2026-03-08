from domain.enums import AlternativeScoreCategory
from domain.results.alternatives_result import COMPONENT_NAME
from scoring.weighted_score_rule import WeightedScoreRule


class AlternativesRule(WeightedScoreRule):
    """
    Contributes to the primary drug's score based on whether viable
    alternatives were found and scored. A low alternatives score signals
    the primary drug has fewer substitutes, increasing its relative value.
    """

    def __init__(self):
        super().__init__(
            name="AlternativesRule",
            component_name=COMPONENT_NAME,
            score_map={
                AlternativeScoreCategory.SCORED:    1,
                AlternativeScoreCategory.FAILED:    0,
                AlternativeScoreCategory.NOT_FOUND: 0,
            },
            weight_map={
                AlternativeScoreCategory.SCORED:    10,
                AlternativeScoreCategory.FAILED:    0,
                AlternativeScoreCategory.NOT_FOUND: 0,
            },
        )
