from domain.enums import InteractionCategory
from scoring.weighted_score_rule import WeightedScoreRule

COMPONENT_NAME = "DrugInteractions"

class InteractionRule(WeightedScoreRule):
    """R2 — Drug Interactions."""
    def __init__(self):
        super().__init__(
            name="R2_Interactions",
            component_name=COMPONENT_NAME,
            score_map={
                InteractionCategory.CONTRAINDICATED:  3,
                InteractionCategory.LIFE_THREATENING: 3,
                InteractionCategory.SERIOUS:          2,
                InteractionCategory.NON_SERIOUS:      1,
                InteractionCategory.NONE:             0,
            },
            weight_map={
                InteractionCategory.CONTRAINDICATED:  100,
                InteractionCategory.LIFE_THREATENING: 90,
                InteractionCategory.SERIOUS:          70,
                InteractionCategory.NON_SERIOUS:      30,
                InteractionCategory.NONE:             10,
            },
        )
