"""Feature columns shared by dataset generation and ML inference.

``scenario_type`` is derived from observables (attack type, policy violation,
tool). The generator and the runtime use this same function so the model is
not asked for a label that only exists in the training spreadsheet.
"""

from typing import Any

FEATURE_COLUMNS = [
    "scenario_type",
    "attack_type",
    "user_role",
    "tool",
    "data_sensitivity",
    "action_impact",
    "amount_bucket",
    "external_recipient",
]

TOOL_IMPACT = {
    "none": "low",
    "search_documents": "low",
    "read_file": "low",
    "send_email": "medium",
    "update_record": "medium",
    "delete_file": "high",
    "make_payment": "high",
}


def action_impact(tool: str) -> str:
    """Map a tool name to a coarse impact bucket."""
    return TOOL_IMPACT.get(tool, "medium")


def amount_bucket(amount: float | None) -> str:
    """Bucket a payment amount. ``None`` means the tool is not a payment."""
    if amount is None:
        return "none"
    if amount < 100:
        return "small"
    if amount < 1000:
        return "medium"
    if amount < 10000:
        return "large"
    return "very_large"


def derive_scenario_type(attack_type: str, tool: str, policy_violation: bool) -> str:
    """Derive the scenario feature the random forest was trained on."""
    if attack_type in {"direct_injection", "jailbreak"}:
        return "direct_injection"
    if attack_type == "indirect_injection":
        return "indirect_injection"
    if attack_type in {"data_exfiltration", "privilege_escalation"} or policy_violation:
        return "unauthorized"
    if tool in {"delete_file", "make_payment"}:
        return "legitimate_high_impact"
    return "safe"


def payment_amount(tool: str, arguments: dict[str, Any]) -> float | None:
    """Return a payment amount when the tool is ``make_payment``."""
    if tool != "make_payment":
        return None
    raw = arguments.get("amount")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def is_external_recipient(tool: str, arguments: dict[str, Any], internal_domains: list[str]) -> bool:
    """Return True when an email recipient is outside the company domains."""
    if tool != "send_email":
        return False
    recipient = str(arguments.get("to", "")).lower()
    if "@" not in recipient:
        return False
    domain = recipient.rsplit("@", 1)[-1]
    return not any(domain == item or domain.endswith("." + item) for item in internal_domains)
