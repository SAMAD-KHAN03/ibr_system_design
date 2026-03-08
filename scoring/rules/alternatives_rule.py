from domain.enums import AlternativeScoreCategory
from domain.results.alternatives_result import COMPONENT_NAME
from scoring.weighted_score_rule import WeightedScoreRule

class AlternativesRule(WeightedScoreRule):
    """B5 — Alternatives. None=2×70=140, Same=1×50=50, Safer=0×20=0"""
    def __init__(self):
        super().__init__(
            name="B5_Alternatives",
            component_name=COMPONENT_NAME,
            score_map={
                AlternativeScoreCategory.NONE_EXISTS:  2,
                AlternativeScoreCategory.SAME_SAFETY:  1,
                AlternativeScoreCategory.SAFER_EXISTS: 0,
                AlternativeScoreCategory.NOT_FOUND:    0,
            },
            weight_map={
                AlternativeScoreCategory.NONE_EXISTS:  70,
                AlternativeScoreCategory.SAME_SAFETY:  50,
                AlternativeScoreCategory.SAFER_EXISTS: 20,
                AlternativeScoreCategory.NOT_FOUND:    0,
            },
        )
