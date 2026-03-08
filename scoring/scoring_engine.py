from typing import List
from execution_context import ExecutionContext
from scoring.base_rule import ScoreRule


class ScoringEngine:
    """
    Evaluates a list of rules against the populated context.

    Override rules are evaluated first; if any returns > 0, the pipeline
    short-circuits and returns only that score (e.g. hard contraindication).

    Open/Closed: new rules are registered at construction time — this class
    never needs editing when rules are added or removed.
    """

    def __init__(self, rules: List[ScoreRule], override_rules: List[ScoreRule] = None):
        self._rules = rules
        self._override_rules = override_rules or []

    def evaluate(self, context: ExecutionContext) -> dict:
        breakdown: dict[str, float] = {}

        # ── Override pass ──────────────────────────────────────────────────
        for rule in self._override_rules:
            score = rule.evaluate(context)
            if score > 0:
                breakdown[rule.name] = score
                return {
                    "total_score": score,
                    "breakdown": breakdown,
                    "override_triggered": True,
                    "max_possible": rule.max_score(),
                }

        # ── Normal pass ────────────────────────────────────────────────────
        total = 0.0
        max_possible = 0.0
        for rule in self._rules:
            score = rule.evaluate(context)
            breakdown[rule.name] = score
            total += score
            max_possible += rule.max_score()

        return {
            "total_score": total,
            "breakdown": breakdown,
            "override_triggered": False,
            "max_possible": max_possible,
        }