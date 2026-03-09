from domain.enums import InteractionCategory
from scoring.weighted_score_rule import WeightedScoreRule
from execution_context import ExecutionContext

# ADRComponent stores both ADR severity and interaction data under this key
COMPONENT_NAME = "ADRAnalysis"


class InteractionRule(WeightedScoreRule):
    """
    R2 — Drug Interactions.
    Reads interaction_category from ADRResult (stored by ADRComponent).
    ADRResult.category holds ADR severity (R3); ADRResult.interaction_category holds this (R2).
    """

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

    def evaluate(self, context: ExecutionContext) -> float:
        """Override to read interaction_category, not the default .category field."""
        result = context.get_result(self._component_name)
        if result is None:
            return 0.0
        # ADRResult exposes interaction_category for R2
        category = getattr(result, "interaction_category", InteractionCategory.NONE)
        base   = self._score_map.get(category, 0.0)
        weight = self._weight_map.get(category, 0.0)
        return base * weight
