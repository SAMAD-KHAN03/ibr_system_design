from domain.enums import PubMedEvidenceCategory
from domain.results.pubmed_result import COMPONENT_NAME
from scoring.weighted_score_rule import WeightedScoreRule

class PubMedEvidenceRule(WeightedScoreRule):
    """B3 — Strength of Evidence. High(>3 RCTs)=3×90=270, Low(<=2)=0×20=0"""
    def __init__(self):
        super().__init__(
            name="B3_StrengthOfEvidence",
            component_name=COMPONENT_NAME,
            score_map={
                PubMedEvidenceCategory.HIGH: 3,
                PubMedEvidenceCategory.LOW:  0,
            },
            weight_map={
                PubMedEvidenceCategory.HIGH: 90,
                PubMedEvidenceCategory.LOW:  20,
            },
        )
