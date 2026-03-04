# scoring/approval_rule.py
from scoring.base_rule import ScoreRule
from domain.enums import ApprovalCategory
# engine/bra_engine.py
# scoring/engine.py
from execution_context import ExecutionContext
class ScoringEngine:

    def __init__(self, rules: list, override_rules: list):
        self.rules = rules
        self.override_rules = override_rules

    def evaluate(self, context: ExecutionContext):
        
        breakdown = {}
        total_score = 0

        # 1️⃣ Overrides
        for rule in self.override_rules:
            score = rule.evaluate(context)   # ✅ FIXED
            if score > 0:
                breakdown[rule.name] = score
                return {
                    "total_score": score,
                    "breakdown": breakdown,
                    "override_triggered": True
                }

        # 2️⃣ Normal rules
        for rule in self.rules:
            score = rule.evaluate(context)   # ✅ FIXED
            breakdown[rule.name] = score
            total_score += score

        return {
            "total_score": total_score,
            "breakdown": breakdown,
            "override_triggered": False
        }