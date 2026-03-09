from domain.enums import ReversibilityCategory
from scoring.weighted_score_rule import WeightedScoreRule
from execution_context import ExecutionContext

COMPONENT_NAME = "RiskMitigation"


class ReversibilityRule(WeightedScoreRule):
    """
    R5 — Risk Reversibility. Irreversible=3×95=285, Reversible=1×40=40
    Reads reversibility_category from RiskMitigationResult.
    """

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

    def evaluate(self, context: ExecutionContext) -> float:
        """Override to read reversibility_category, not the default .category field."""
        result = context.get_result(self._component_name)
        if result is None:
            return 0.0
        category = getattr(result, "reversibility_category", ReversibilityCategory.REVERSIBLE)
        base   = self._score_map.get(category, 0.0)
        weight = self._weight_map.get(category, 0.0)
        return base * weight