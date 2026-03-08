from typing import List
from execution_context import ExecutionContext
from scoring.base_rule import ScoreRule


class ScoringEngine:
    """
    Evaluates benefit and risk rules separately per the iBR sheet:

        iBR score = sum(benefit weighted scores) - sum(risk weighted scores)
        > 6   → Favorable
        2–6   → Conditional
        < 2   → Unfavourable

    R1 (Contraindication) is an override rule — if triggered, it immediately
    returns an Unfavourable result without evaluating any other rules.

    Sheet reference:
        Max benefit score = 1210  |  Min benefit score = 110
        Max risk score    = 1425  |  Min risk score    = 140
    """

    def __init__(
        self,
        benefit_rules: List[ScoreRule],
        risk_rules: List[ScoreRule],
        override_rules: List[ScoreRule] = None,
    ):
        self._benefit_rules  = benefit_rules
        self._risk_rules     = risk_rules
        self._override_rules = override_rules or []

    def evaluate(self, context: ExecutionContext) -> dict:
        # ── R1 override pass (Absolute Contraindication) ──────────────────
        for rule in self._override_rules:
            score = rule.evaluate(context)
            if score > 0:
                return {
                    "ibr_score":            -score,          # negative: risk overrides
                    "benefit_total":        0.0,
                    "risk_total":           score,
                    "benefit_breakdown":    {},
                    "risk_breakdown":       {rule.name: score},
                    "override_triggered":   True,
                    "override_rule":        rule.name,
                    "ibr_outcome":          "Unfavourable",
                    "max_benefit":          self._max_benefit(),
                    "max_risk":             rule.max_score(),
                }

        # ── Benefit pass ──────────────────────────────────────────────────
        benefit_breakdown: dict[str, float] = {}
        benefit_total = 0.0
        max_benefit   = 0.0
        for rule in self._benefit_rules:
            score = rule.evaluate(context)
            benefit_breakdown[rule.name] = score
            benefit_total += score
            max_benefit   += rule.max_score()

        # ── Risk pass ─────────────────────────────────────────────────────
        risk_breakdown: dict[str, float] = {}
        risk_total = 0.0
        max_risk   = 0.0
        for rule in self._risk_rules:
            score = rule.evaluate(context)
            risk_breakdown[rule.name] = score
            risk_total += score
            max_risk   += rule.max_score()

        ibr_score = benefit_total - risk_total

        return {
            "ibr_score":          ibr_score,
            "benefit_total":      benefit_total,
            "risk_total":         risk_total,
            "benefit_breakdown":  benefit_breakdown,
            "risk_breakdown":     risk_breakdown,
            "override_triggered": False,
            "override_rule":      None,
            "ibr_outcome":        _ibr_outcome(ibr_score),
            "max_benefit":        max_benefit,
            "max_risk":           max_risk,
        }

    def _max_benefit(self) -> float:
        return sum(r.max_score() for r in self._benefit_rules)


def _ibr_outcome(score: float) -> str:
    if score > 6:
        return "Favorable"
    elif score >= 2:
        return "Conditional"
    else:
        return "Unfavourable"
