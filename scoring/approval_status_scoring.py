from weight_scoring_template import WeightedScoringTemplate
# scoring/approval_rule.py
from scoring.base_rule import ScoreRule
from domain.enums import ApprovalCategory

class ApprovalStatusRule(ScoreRule):

    def __init__(self):
        super().__init__("Approval Status")

        self.score_map = {
            ApprovalCategory.APPROVED: 2,
            ApprovalCategory.OFF_LABEL: 1
        }

        self.weight_map = {
            ApprovalCategory.APPROVED: 70,
            ApprovalCategory.OFF_LABEL: 50
        }

    def evaluate(self, context):

        result = context.results.get("RegulatoryApprovalComponent")
        if not result:
            return 0

        category = result.category

        base = self.score_map.get(category, 0)
        weight = self.weight_map.get(category, 0)

        return base * weight

    def max_score(self):
        return 2 * 70