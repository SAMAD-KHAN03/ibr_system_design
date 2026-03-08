from domain.enums import PubMedEvidenceCategory
from domain.results.pubmed_result import COMPONENT_NAME
from scoring.weighted_score_rule import WeightedScoreRule


class PubMedEvidenceRule(WeightedScoreRule):

    def __init__(self):
        super().__init__(
            name="PubMedEvidenceRule",
            component_name=COMPONENT_NAME,
            score_map={
                PubMedEvidenceCategory.HIGH:   3,
                PubMedEvidenceCategory.MEDIUM: 2,
                PubMedEvidenceCategory.LOW:    1,
            },
            weight_map={
                PubMedEvidenceCategory.HIGH:   30,
                PubMedEvidenceCategory.MEDIUM: 20,
                PubMedEvidenceCategory.LOW:    10,
            },
        )