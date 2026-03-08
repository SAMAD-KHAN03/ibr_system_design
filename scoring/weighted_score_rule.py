from typing import Dict, Any
from scoring.base_rule import ScoreRule
from execution_context import ExecutionContext


class WeightedScoreRule(ScoreRule):
    """
    Reusable base for rules that map a domain category to (score × weight).

    Subclasses only need to provide:
      - component_name  : which ComponentResult to read
      - score_map       : category → base score
      - weight_map      : category → weight multiplier

    This keeps concrete rules tiny (Open/Closed principle).
    """

    def __init__(
        self,
        name: str,
        component_name: str,
        score_map: Dict[Any, float],
        weight_map: Dict[Any, float],
    ):
        super().__init__(name)
        self._component_name = component_name
        self._score_map = score_map
        self._weight_map = weight_map

    def evaluate(self, context: ExecutionContext) -> float:
        result = context.get_result(self._component_name)
        if result is None:
            return 0.0

        category = result.category
        base = self._score_map.get(category, 0.0)
        weight = self._weight_map.get(category, 0.0)
        return base * weight

    def max_score(self) -> float:
        if not self._score_map or not self._weight_map:
            return 0.0
        return max(
            self._score_map.get(k, 0) * self._weight_map.get(k, 0)
            for k in self._score_map
        )