from domain.enums import MMECategory
from domain.results.mme_result import COMPONENT_NAME
from scoring.weighted_score_rule import WeightedScoreRule


class MMERule(WeightedScoreRule):
    """B2 — Molecule Market Experience. Established=2×60=120, New=1×40=40"""
    def __init__(self):
        super().__init__(
            name="B2_MME",
            component_name=COMPONENT_NAME,
            score_map={
                MMECategory.ESTABLISHED: 2,
                MMECategory.NEW:         1,
            },
            weight_map={
                MMECategory.ESTABLISHED: 60,
                MMECategory.NEW:         40,
            },
        )
