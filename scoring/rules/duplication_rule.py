from domain.enums import DuplicationCategory
from scoring.weighted_score_rule import WeightedScoreRule

COMPONENT_NAME = "TherapeuticDuplication"

class DuplicationRule(WeightedScoreRule):
    """B4 — Therapeutic Duplication. Unique=3×80=240, Overlap=2×60=120, Redundant=0×20=0"""
    def __init__(self):
        super().__init__(
            name="B4_TherapeuticDuplication",
            component_name=COMPONENT_NAME,
            score_map={
                DuplicationCategory.UNIQUE:    3,
                DuplicationCategory.OVERLAP:   2,
                DuplicationCategory.REDUNDANT: 0,
            },
            weight_map={
                DuplicationCategory.UNIQUE:    80,
                DuplicationCategory.OVERLAP:   60,
                DuplicationCategory.REDUNDANT: 20,
            },
        )
