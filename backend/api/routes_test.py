"""Direct governance endpoints that skip the LLM."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.agentshield.models import ManualProposalRequest, ProposedAction, ScoreRequest
from backend.agentshield.policy_engine import authorize, resolve_sensitivity
from backend.api.deps import get_runtime, require_api_key
from backend.runtime import Runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


def _action(body: ManualProposalRequest) -> ProposedAction:
    return ProposedAction(tool=body.tool, arguments=body.arguments, reasoning=body.reasoning)


@router.post("/test-agentshield")
def test_agentshield(
    body: ManualProposalRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, Any]:
    """Govern a manually supplied tool proposal."""
    result = runtime.service.evaluate(
        _action(body),
        user_role=body.user_role,
        user_id=body.user_id,
        user_request=body.request,
        retrieved_context=body.retrieved_context,
    )
    return result.model_dump()


@router.post("/test-risk")
def test_risk(
    body: ManualProposalRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, Any]:
    """Return prompt analysis, rule risk, and ML risk without a final override story hidden."""
    result = runtime.service.evaluate(
        _action(body),
        user_role=body.user_role,
        user_id=body.user_id,
        user_request=body.request,
        retrieved_context=body.retrieved_context,
    )
    return {
        "prompt_analysis": result.prompt_analysis.model_dump(),
        "rule_risk": result.rule_risk.model_dump(),
        "ml_risk": result.ml_risk,
        "ml_fallback": result.ml_fallback,
        "combined_risk": result.combined_risk,
        "decision": result.decision,
    }


@router.post("/test-policy")
def test_policy(
    body: ManualProposalRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, Any]:
    """Return the policy engine result only."""
    action = _action(body)
    sensitivity = resolve_sensitivity(runtime.store, action.tool, action.arguments)
    policy = authorize(
        role=body.user_role,
        tool=action.tool,
        arguments=action.arguments,
        sensitivity=sensitivity,
        store=runtime.store,
    )
    return {"sensitivity": sensitivity, "policy": policy.model_dump()}


@router.post("/test-score")
def test_score(
    body: ScoreRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, Any]:
    """Combine a rule score and an ML score with the configured weights."""
    from backend.agentshield.combiner import combine
    from backend.agentshield.decision_engine import risk_level_for, threshold_decision

    settings = runtime.settings
    combined = combine(body.rule_risk, body.ml_risk, settings.w_rule, settings.w_ml)
    return {
        "combined_risk": combined,
        "risk_level": risk_level_for(combined),
        "numeric_decision": threshold_decision(
            combined,
            approve_max=settings.threshold_approve,
            human_max=settings.threshold_human,
        ),
    }
