"""LangGraph workflow: propose, govern, then execute, queue, or refuse.

A blocked proposal may be re-planned once. The alternative is governed and
recorded, and it is not executed. The user-facing decision stays the original
block, so a refused delete cannot come back as a successful search.
"""

import operator
import re
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from backend.agent.llm import LLMClient
from backend.agentshield.audit import AuditStore
from backend.agentshield.models import GovernanceResult, ProposedAction
from backend.agentshield.permits import mint_permit
from backend.agentshield.service import GovernanceService
from backend.config import Settings
from backend.tools.executor import ExecutionDenied, PermitLedger, execute
from backend.tools.paths import ALLOWED_PREFIXES
from backend.tools.sandbox_store import SandboxStore

_PATH = re.compile(
    r"\b(?:guidelines|docs|confidential|finance|restricted|inbox)/[A-Za-z0-9_./-]+"
)


class AgentState(TypedDict, total=False):
    """State carried between graph nodes."""

    user_request: str
    user_role: str
    user_id: str
    retrieved_context: str
    proposed_action: dict[str, Any] | None
    governance_result: dict[str, Any] | None
    decision: str | None
    tool_result: dict[str, Any] | None
    messages: list[dict[str, str]]
    trace: Annotated[list[dict[str, Any]], operator.add]
    replan_count: int
    primary_decision: str | None
    primary_governance: dict[str, Any] | None
    primary_proposal: dict[str, Any] | None
    alternative: dict[str, Any] | None
    message: str


def _retrieve(store: SandboxStore, user_request: str, provided: str) -> str:
    chunks = [provided.strip()] if provided.strip() else []
    for match in _PATH.findall(user_request):
        path = match.strip(".").rstrip("/")
        prefix = path.split("/", 1)[0]
        if prefix not in ALLOWED_PREFIXES or ".." in path:
            continue
        record = store.get_file(path)
        if record is None:
            continue
        chunks.append(f"[{record['path']} | {record['sensitivity']}]\n{record['content'][:1500]}")
    return "\n\n".join(chunks)[:8000]


def build_graph(
    *,
    settings: Settings,
    llm: LLMClient,
    service: GovernanceService,
    store: SandboxStore,
    audit: AuditStore,
):
    """Compile the governance graph."""

    def propose_action(state: AgentState) -> dict[str, Any]:
        context = state.get("retrieved_context") or ""
        if state.get("replan_count", 0) == 0:
            context = _retrieve(store, state["user_request"], context)
        proposal = llm.propose(
            user_request=state["user_request"],
            retrieved_context=context,
            replan=state.get("replan_count", 0) > 0,
        )
        update: dict[str, Any] = {
            "retrieved_context": context,
            "proposed_action": proposal.model_dump(),
            "messages": [
                {"role": "user", "content": state["user_request"]},
                {"role": "assistant", "content": proposal.model_dump_json()},
            ],
            "trace": [
                {
                    "node": "propose_action",
                    "replan": state.get("replan_count", 0) > 0,
                    "proposal": proposal.model_dump(),
                }
            ],
        }
        if state.get("replan_count", 0) == 0:
            update["primary_proposal"] = proposal.model_dump()
        return update

    def agentshield_evaluate(state: AgentState) -> dict[str, Any]:
        proposal = ProposedAction.model_validate(state["proposed_action"])
        phase = "replan" if state.get("replan_count", 0) else "primary"
        result = service.evaluate(
            proposal,
            user_role=state["user_role"],
            user_id=state["user_id"],
            user_request=state["user_request"],
            retrieved_context=state.get("retrieved_context") or "",
            phase=phase,
        )
        dumped = result.model_dump()
        update: dict[str, Any] = {
            "governance_result": dumped,
            "decision": result.decision,
            "trace": [
                {
                    "node": "agentshield_evaluate",
                    "phase": phase,
                    "decision": result.decision,
                    "combined_risk": result.combined_risk,
                    "risk_level": result.risk_level,
                    "rule_risk": result.rule_risk.score,
                    "ml_risk": result.ml_risk,
                    "attack_type": result.prompt_analysis.attack_type,
                    "explanation": result.explanation,
                }
            ],
        }
        if phase == "primary":
            update["primary_decision"] = result.decision
            update["primary_governance"] = dumped
        else:
            update["alternative"] = {
                "proposal": state["proposed_action"],
                "governance_result": dumped,
            }
        return update

    def execute_tool(state: AgentState) -> dict[str, Any]:
        governance = GovernanceResult.model_validate(state["primary_governance"])
        if governance.permit is None:
            raise ExecutionDenied("approve permit missing")
        result = execute(
            governance.permit,
            store,
            secret=settings.decision_secret,
            ledger=PermitLedger(audit.consume_permit),
        )
        return {
            "tool_result": result,
            "trace": [{"node": "execute_tool", "simulated": True, "tool": result.get("tool")}],
        }

    def queue_for_human(state: AgentState) -> dict[str, Any]:
        governance = GovernanceResult.model_validate(state["primary_governance"])
        proposal = ProposedAction.model_validate(state["proposed_action"])
        audit.enqueue(
            approval_id=governance.request_id,
            user_id=state["user_id"],
            user_role=state["user_role"],
            user_request=state["user_request"],
            tool=proposal.tool,
            arguments=proposal.arguments,
            governance=governance,
        )
        return {
            "tool_result": None,
            "trace": [
                {
                    "node": "queue_for_human",
                    "approval_id": governance.request_id,
                    "executed": False,
                }
            ],
        }

    def replan(state: AgentState) -> dict[str, Any]:
        return {
            "replan_count": state.get("replan_count", 0) + 1,
            "trace": [{"node": "replan", "reason": "primary decision was BLOCK"}],
        }

    def respond(state: AgentState) -> dict[str, Any]:
        decision = state.get("primary_decision") or state.get("decision")
        governance = state.get("primary_governance") or {}
        explanation = governance.get("explanation", "")
        if decision == "APPROVE" and state.get("tool_result"):
            message = "The tool ran inside the sandbox after an APPROVE decision. " + explanation
        elif decision == "HUMAN_APPROVAL":
            message = (
                "The tool was not executed. It is waiting in the human approval queue. "
                + explanation
            )
        elif decision == "BLOCK":
            message = "The tool was not executed. " + explanation
            alternative = state.get("alternative")
            if alternative:
                alt_decision = alternative["governance_result"]["decision"]
                alt_tool = alternative["proposal"]["tool"]
                message += (
                    f" A safer alternative ({alt_tool}) was assessed as {alt_decision} "
                    "and was not executed automatically."
                )
        else:
            message = explanation or "No tool was proposed."
        return {
            "decision": decision,
            "governance_result": governance,
            "message": message,
            "trace": [{"node": "respond", "decision": decision}],
        }

    def route(state: AgentState) -> str:
        if state.get("replan_count", 0) > 0 and state.get("primary_decision") == "BLOCK":
            return "respond"
        decision = state.get("primary_decision")
        proposal = state.get("proposed_action") or {}
        if decision == "APPROVE" and proposal.get("tool") not in (None, "none"):
            return "execute_tool"
        if decision == "HUMAN_APPROVAL":
            return "queue_for_human"
        if decision == "BLOCK" and state.get("replan_count", 0) < 1:
            return "replan"
        return "respond"

    graph = StateGraph(AgentState)
    graph.add_node("propose_action", propose_action)
    graph.add_node("agentshield_evaluate", agentshield_evaluate)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("queue_for_human", queue_for_human)
    graph.add_node("replan", replan)
    graph.add_node("respond", respond)
    graph.set_entry_point("propose_action")
    graph.add_edge("propose_action", "agentshield_evaluate")
    graph.add_conditional_edges(
        "agentshield_evaluate",
        route,
        {
            "execute_tool": "execute_tool",
            "queue_for_human": "queue_for_human",
            "replan": "replan",
            "respond": "respond",
        },
    )
    graph.add_edge("execute_tool", "respond")
    graph.add_edge("queue_for_human", "respond")
    graph.add_edge("replan", "propose_action")
    graph.add_edge("respond", END)
    return graph.compile()


def run_agent(
    compiled: Any,
    *,
    user_request: str,
    user_role: str,
    user_id: str,
    retrieved_context: str = "",
) -> dict[str, Any]:
    """Invoke the graph and return a JSON-ready state."""
    state = compiled.invoke(
        {
            "user_request": user_request,
            "user_role": user_role,
            "user_id": user_id,
            "retrieved_context": retrieved_context,
            "messages": [],
            "trace": [],
            "replan_count": 0,
            "tool_result": None,
        }
    )
    return state


def approve_and_execute(
    *,
    settings: Settings,
    store: SandboxStore,
    audit: AuditStore,
    approval_id: str,
    approver: str,
    arguments: dict[str, Any],
    tool: str,
) -> dict[str, Any]:
    """Mint a fresh APPROVE permit for a recorded human approval and execute once."""
    permit = mint_permit(
        settings.decision_secret,
        request_id=f"{approval_id}:human:{approver}",
        tool=tool,
        arguments=arguments,
        approver=approver,
    )
    return execute(
        permit,
        store,
        secret=settings.decision_secret,
        ledger=PermitLedger(audit.consume_permit),
    )
