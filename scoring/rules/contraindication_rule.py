from domain.enums import ContraindicationCategory
from domain.results.contraindication_result import COMPONENT_NAME
from scoring.weighted_score_rule import WeightedScoreRule


class ContraindicationRule(WeightedScoreRule):
    """
    Scoring rule for contraindication findings.

    Registered as an OVERRIDE rule in ScoringEngine — if this returns > 0
    the engine stops and returns only this score (pipeline was already halted
    by the component itself, but the override ensures no partial score leaks).

    Score semantics
    ---------------
    SAFE          → 0   (no contribution; normal rules proceed)
    ABSOLUTE      → negative signal via weight=0 but override fires on score>0,
                    so we assign a non-zero sentinel only for non-safe states.
    """

    def __init__(self):
        super().__init__(
            name="ContraindicationRule",
            component_name=COMPONENT_NAME,
            score_map={
                ContraindicationCategory.SAFE:          0,
                ContraindicationCategory.ABSOLUTE:      1,
                ContraindicationCategory.BOXED_WARNING: 1,
                ContraindicationCategory.PREGNANCY:     1,
            },
            weight_map={
                ContraindicationCategory.SAFE:          0,
                ContraindicationCategory.ABSOLUTE:      100,
                ContraindicationCategory.BOXED_WARNING: 80,
                ContraindicationCategory.PREGNANCY:     90,
            },
        )