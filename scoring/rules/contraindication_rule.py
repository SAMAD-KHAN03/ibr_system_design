from domain.enums import ContraindicationCategory
from domain.results.contraindication_result import COMPONENT_NAME
from scoring.weighted_score_rule import WeightedScoreRule

class ContraindicationRule(WeightedScoreRule):
    """R1 — Contraindication Check. Absolute=3×100=300 (OVERRIDE). Safe=0×10=0"""
    def __init__(self):
        super().__init__(
            name="R1_Contraindication",
            component_name=COMPONENT_NAME,
            score_map={
                ContraindicationCategory.ABSOLUTE:      3,
                ContraindicationCategory.BOXED_WARNING: 3,
                ContraindicationCategory.PREGNANCY:     3,
                ContraindicationCategory.SAFE:          0,
            },
            weight_map={
                ContraindicationCategory.ABSOLUTE:      100,
                ContraindicationCategory.BOXED_WARNING: 100,
                ContraindicationCategory.PREGNANCY:     100,
                ContraindicationCategory.SAFE:          10,
            },
        )
