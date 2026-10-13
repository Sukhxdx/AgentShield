"""Transparent contextual risk score from 0 to 100.

The breakdown is integer points and sums to the clamped score. Policy can
still force a stricter decision later; this function only contributes points.

Formula (points, before the 0–100 clamp):

- tool impact: search 6, read 10, email 14, update 22, delete 32, payment 36
- data sensitivity: public 0, internal 6, unknown 8, confidential 15, restricted 20
- role context: admin -6, manager -3, employee 0, service 2, guest 10
- prompt injection: round(injection_score × 0.25), so a full injection adds 25
- sensitive information: round(sensitive_info_score × 0.10)
- policy pressure: 8 when any authorization violation exists, else 0
- irreversibility: delete 10, payment 8, otherwise 0
- transaction amount: small 2, medium 6, large 12, very large 20
- external exposure: 8 for an external email recipient

Reference case, employee ``delete_file`` on ``confidential/employee_database.db``
with a sensitive-information score of 40 and a policy violation:

32 + 15 + 0 + 0 + 4 + 8 + 10 + 0 + 0 = 69.

If the raw total falls outside 0–100, the largest positive contributors are
reduced (or negative contributors are lifted) until the parts sum to the
clamped score.
"""

from typing import Any

from backend.agentshield.features import amount_bucket
from backend.agentshield.models import RiskLevel, RuleRisk

TOOL_IMPACT = {
    "none": 0,
    "search_documents": 6,
    "read_file": 10,
    "send_email": 14,
    "update_record": 22,
    "delete_file": 32,
    "make_payment": 36,
}
SENSITIVITY_POINTS = {
    "public": 0,
    "internal": 6,
    "unknown": 8,
    "confidential": 15,
    "restricted": 20,
}
ROLE_POINTS = {
    "admin": -6,
    "manager": -3,
    "employee": 0,
    "service": 2,
    "guest": 10,
}
AMOUNT_POINTS = {"none": 0, "small": 2, "medium": 6, "large": 12, "very_large": 20}
IRREVERSIBLE = {"delete_file": 10, "make_payment": 8}


def _level(score: int) -> RiskLevel:
    if score <= 30:
        return "LOW"
    if score <= 70:
        return "MEDIUM"
    return "HIGH"


def _clamp_breakdown(parts: dict[str, int]) -> dict[str, int]:
    adjusted = dict(parts)
    total = sum(adjusted.values())
    if total > 100:
        overflow = total - 100
        for key in sorted(adjusted, key=lambda name: adjusted[name], reverse=True):
            if overflow == 0:
                break
            if adjusted[key] <= 0:
                continue
            take = min(adjusted[key], overflow)
            adjusted[key] -= take
            overflow -= take
    elif total < 0:
        deficit = -total
        for key in sorted(adjusted, key=lambda name: adjusted[name]):
            if deficit == 0:
                break
            if adjusted[key] >= 0:
                continue
            give = min(-adjusted[key], deficit)
            adjusted[key] += give
            deficit -= give
    return adjusted


def rule_risk(
    *,
    tool: str,
    sensitivity: str,
    role: str,
    injection_score: int,
    sensitive_info_score: int,
    policy_violations: list[str],
    arguments: dict[str, Any],
    external_recipient: bool,
) -> RuleRisk:
    """Score one proposed action. The returned breakdown sums to ``score``."""
    amount = None
    if tool == "make_payment":
        try:
            amount = float(arguments.get("amount"))
        except (TypeError, ValueError):
            amount = None
    parts = {
        "tool_impact": TOOL_IMPACT.get(tool, 10),
        "data_sensitivity": SENSITIVITY_POINTS.get(sensitivity, 8),
        "role_context": ROLE_POINTS.get(role, 10),
        "prompt_injection": int(round(injection_score * 0.25)),
        "sensitive_information": int(round(sensitive_info_score * 0.10)),
        "policy_pressure": 8 if policy_violations else 0,
        "irreversibility": IRREVERSIBLE.get(tool, 0),
        "transaction_amount": AMOUNT_POINTS[amount_bucket(amount)],
        "external_exposure": 8 if external_recipient else 0,
    }
    parts = _clamp_breakdown(parts)
    score = sum(parts.values())
    notes = {
        "tool_impact": f"{tool} base impact",
        "data_sensitivity": f"data labelled {sensitivity}",
        "role_context": f"caller role {role}",
        "prompt_injection": f"injection score {injection_score}",
        "sensitive_information": f"sensitive-information score {sensitive_info_score}",
        "policy_pressure": "authorization violation" if policy_violations else "no violation",
        "irreversibility": "delete or payment" if tool in IRREVERSIBLE else "reversible",
        "transaction_amount": amount_bucket(amount),
        "external_exposure": "external recipient" if external_recipient else "no external recipient",
    }
    return RuleRisk(score=score, breakdown=parts, level=_level(score), notes=notes)
