"""Weighted combination of rule-based and ML risk.

The default weights are equal, which is ``round((rule + ml) / 2)`` using
half-up rounding. The reference identity is rule 69 and ML 92.49 → 81.
"""

from decimal import ROUND_HALF_UP, Decimal


def round_half_up(value: float) -> int:
    """Round to the nearest integer, with halves away from zero."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def combine(rule_score: float, ml_score: float, w_rule: float = 0.5, w_ml: float = 0.5) -> int:
    """Return a combined risk in ``[0, 100]``."""
    rule_score = min(100.0, max(0.0, float(rule_score)))
    ml_score = min(100.0, max(0.0, float(ml_score)))
    weight_sum = w_rule + w_ml
    if weight_sum <= 0:
        w_rule, w_ml, weight_sum = 0.5, 0.5, 1.0
    blended = (w_rule * rule_score + w_ml * ml_score) / weight_sum
    return min(100, max(0, round_half_up(blended)))
