"""Map a combined score and a policy result to a decision.

Thresholds (configurable, defaults in parentheses):

- 0–30 APPROVE, risk level LOW
- 31–70 HUMAN_APPROVAL, risk level MEDIUM
- 71–100 BLOCK, risk level HIGH

Policy is applied after the threshold and can only tighten the outcome.
An authorization violation forces BLOCK. ``required_approval`` forces at
least HUMAN_APPROVAL. The explanation is a template, not an LLM completion.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.agentshield.combiner import combine
from backend.agentshield.models import (
    DecisionName,
    GovernanceResult,
    PolicyResult,
    PromptAnalysis,
    RiskLevel,
    RuleRisk,
)
from backend.agentshield.permits import mint_permit, sign_payload

_ORDER = {"APPROVE": 0, "HUMAN_APPROVAL": 1, "BLOCK": 2}


def risk_level_for(score: int) -> RiskLevel:
    """Return the band name for a combined score."""
    if score <= 30:
        return "LOW"
    if score <= 70:
        return "MEDIUM"
    return "HIGH"


def threshold_decision(
    score: int,
    *,
    approve_max: int = 30,
    human_max: int = 70,
) -> DecisionName:
    """Return the decision implied by the numeric thresholds alone."""
    if score <= approve_max:
        return "APPROVE"
    if score <= human_max:
        return "HUMAN_APPROVAL"
    return "BLOCK"


def tighten(current: DecisionName, floor: DecisionName) -> DecisionName:
    """Return the stricter of two decisions."""
    if _ORDER[floor] > _ORDER[current]:
        return floor
    return current


def apply_policy_overrides(
    numeric: DecisionName,
    policy: PolicyResult,
) -> DecisionName:
    """Tighten ``numeric`` according to authorization rules."""
    if not policy.authorized:
        return "BLOCK"
    if policy.required_approval:
        return tighten(numeric, "HUMAN_APPROVAL")
    return numeric


def _explanation(
    *,
    decision: DecisionName,
    numeric: DecisionName,
    tool: str,
    combined_risk: int,
    level: RiskLevel,
    rule: RuleRisk,
    ml_risk: float,
    ml_fallback: bool,
    analysis: PromptAnalysis,
    policy: PolicyResult,
) -> str:
    ranked = sorted(rule.breakdown.items(), key=lambda item: item[1], reverse=True)
    top = [f"{name.replace('_', ' ')} ({points})" for name, points in ranked if points > 0][:3]
    factor_text = ", ".join(top) if top else "no elevated factor"
    ml_text = f"{ml_risk:.2f}"
    if ml_fallback:
        ml_text += " (model unavailable, rule score used)"
    text = (
        f"AgentShield decided {decision} for {tool}. Combined risk is "
        f"{combined_risk}/100 ({level}). The largest rule factors were {factor_text}. "
        f"Prompt analysis classified the attack type as {analysis.attack_type} "
        f"(injection {analysis.injection_score}, sensitive information "
        f"{analysis.sensitive_info_score}). Rule risk was {rule.score} and the "
        f"ML estimate was {ml_text}."
    )
    if policy.violations:
        text += " Authorization violations: " + "; ".join(policy.violations) + "."
    elif policy.required_approval:
        text += " Policy requires a human before this tool can run."
    if decision != numeric:
        text += f" The numeric band was {numeric}; policy made the outcome stricter."
    return text


def decide(
    *,
    tool: str,
    arguments: dict[str, Any],
    rule: RuleRisk,
    ml_risk: float,
    ml_fallback: bool,
    analysis: PromptAnalysis,
    policy: PolicyResult,
    secret: str,
    w_rule: float = 0.5,
    w_ml: float = 0.5,
    approve_max: int = 30,
    human_max: int = 70,
    phase: str = "primary",
    request_id: str | None = None,
) -> GovernanceResult:
    """Build a governance result, including an APPROVE permit when allowed."""
    combined_risk = combine(rule.score, ml_risk, w_rule, w_ml)
    level = risk_level_for(combined_risk)
    numeric = threshold_decision(combined_risk, approve_max=approve_max, human_max=human_max)
    if tool == "none" and analysis.injection_score >= 50:
        numeric = tighten(numeric, "BLOCK")
    decision = apply_policy_overrides(numeric, policy)
    if tool == "none" and decision == "APPROVE":
        decision = "APPROVE"
    request_id = request_id or str(uuid4())
    timestamp = datetime.now(UTC).isoformat()
    reasons = [
        f"Combined risk {combined_risk} is in the {level} band ({numeric}).",
        *policy.reasons,
    ]
    if ml_fallback:
        reasons.append("ML model was missing; the rule score was copied into the ML slot.")
    explanation = _explanation(
        decision=decision,
        numeric=numeric,
        tool=tool,
        combined_risk=combined_risk,
        level=level,
        rule=rule,
        ml_risk=ml_risk,
        ml_fallback=ml_fallback,
        analysis=analysis,
        policy=policy,
    )
    signature = sign_payload(
        secret,
        f"{request_id}|{decision}|{combined_risk}|{timestamp}",
    )
    permit = None
    if decision == "APPROVE" and tool != "none":
        permit = mint_permit(
            secret,
            request_id=request_id,
            tool=tool,
            arguments=arguments,
            approver=None,
        )
    return GovernanceResult(
        decision=decision,
        combined_risk=combined_risk,
        risk_level=level,
        rule_risk=rule,
        ml_risk=ml_risk,
        ml_fallback=ml_fallback,
        prompt_analysis=analysis,
        policy_result=policy,
        explanation=explanation,
        reasons=reasons,
        timestamp=timestamp,
        request_id=request_id,
        signature=signature,
        permit=permit,
        phase=phase,  # type: ignore[arg-type]
    )
