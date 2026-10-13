"""POST /agent runs the full LangGraph pipeline."""

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.agent.graph import run_agent
from backend.agentshield.models import AgentRequest
from backend.api.deps import get_runtime, require_api_key
from backend.runtime import Runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


def _public_state(state: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    proposal = state.get("primary_proposal") or state.get("proposed_action")
    governance = state.get("primary_governance") or state.get("governance_result")
    return {
        "request_id": (governance or {}).get("request_id"),
        "user_request": state.get("user_request"),
        "user_role": state.get("user_role"),
        "user_id": state.get("user_id"),
        "retrieved_context": state.get("retrieved_context"),
        "proposed_action": proposal,
        "governance_result": governance,
        "decision": state.get("decision"),
        "tool_result": state.get("tool_result"),
        "alternative": state.get("alternative"),
        "message": state.get("message"),
        "trace": state.get("trace", []),
        "latency_ms": round(latency_ms, 2),
    }


@router.post("/agent")
def run_agent_route(
    body: AgentRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, Any]:
    """Propose a tool with the LLM, govern it, and execute only on APPROVE."""
    started = time.perf_counter()
    state = run_agent(
        runtime.graph,
        user_request=body.request,
        user_role=body.user_role,
        user_id=body.user_id,
        retrieved_context=body.retrieved_context,
    )
    return _public_state(state, (time.perf_counter() - started) * 1000)
