"""One governance pass: analyze, authorize, score, decide, audit."""

from typing import Any

from backend.agentshield.audit import AuditStore
from backend.agentshield.decision_engine import decide
from backend.agentshield.features import (
    action_impact,
    amount_bucket,
    derive_scenario_type,
    is_external_recipient,
    payment_amount,
)
from backend.agentshield.models import GovernanceResult, ProposedAction
from backend.agentshield.policy_engine import authorize, load_policy, resolve_sensitivity
from backend.agentshield.prompt_analyzer import analyze_prompt
from backend.agentshield.risk_ml import RiskModel
from backend.agentshield.risk_rule_based import rule_risk
from backend.config import Settings
from backend.tools.sandbox_store import SandboxStore


class GovernanceService:
    """Stateless evaluation around the sandbox, model, and audit log."""

    def __init__(
        self,
        settings: Settings,
        store: SandboxStore,
        model: RiskModel,
        audit: AuditStore,
    ) -> None:
        self.settings = settings
        self.store = store
        self.model = model
        self.audit = audit

    def evaluate(
        self,
        action: ProposedAction,
        *,
        user_role: str,
        user_id: str,
        user_request: str,
        retrieved_context: str = "",
        phase: str = "primary",
        latency_ms: float | None = None,
    ) -> GovernanceResult:
        """Run every governance stage and append an audit event."""
        analysis = analyze_prompt(user_request, retrieved_context, action.arguments)
        sensitivity = resolve_sensitivity(self.store, action.tool, action.arguments)
        policy = authorize(
            role=user_role,
            tool=action.tool,
            arguments=action.arguments,
            sensitivity=sensitivity,
            store=self.store,
        )
        internal_domains = load_policy()["internal_email_domains"]
        external = is_external_recipient(action.tool, action.arguments, internal_domains)
        scored = rule_risk(
            tool=action.tool,
            sensitivity=sensitivity,
            role=user_role,
            injection_score=analysis.injection_score,
            sensitive_info_score=analysis.sensitive_info_score,
            policy_violations=policy.violations,
            arguments=action.arguments,
            external_recipient=external,
        )
        features = self._features(
            action=action,
            attack_type=analysis.attack_type,
            sensitivity=sensitivity,
            role=user_role,
            policy_violation=not policy.authorized,
            external=external,
        )
        predicted = self.model.predict(features)
        fallback = predicted is None
        ml_value = float(scored.score if predicted is None else predicted)
        result = decide(
            tool=action.tool,
            arguments=action.arguments,
            rule=scored,
            ml_risk=ml_value,
            ml_fallback=fallback,
            analysis=analysis,
            policy=policy,
            secret=self.settings.decision_secret,
            w_rule=self.settings.w_rule,
            w_ml=self.settings.w_ml,
            approve_max=self.settings.threshold_approve,
            human_max=self.settings.threshold_human,
            phase=phase,
        )
        self.audit.append(
            user_id=user_id,
            user_role=user_role,
            user_request=user_request,
            governance=result,
            tool=action.tool,
            arguments=action.arguments,
            latency_ms=latency_ms,
        )
        return result

    def _features(
        self,
        *,
        action: ProposedAction,
        attack_type: str,
        sensitivity: str,
        role: str,
        policy_violation: bool,
        external: bool,
    ) -> dict[str, Any]:
        amount = payment_amount(action.tool, action.arguments)
        return {
            "scenario_type": derive_scenario_type(attack_type, action.tool, policy_violation),
            "attack_type": attack_type,
            "user_role": role,
            "tool": action.tool,
            "data_sensitivity": sensitivity,
            "action_impact": action_impact(action.tool),
            "amount_bucket": amount_bucket(amount),
            "external_recipient": int(external),
        }
