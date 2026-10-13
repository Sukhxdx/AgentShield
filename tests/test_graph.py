"""Mock LLM through LangGraph. Tools stay idle unless the decision is APPROVE."""

from backend.agent.graph import run_agent


def test_public_read_executes(runtime):
    before = runtime.store.file_count()
    state = run_agent(
        runtime.graph,
        user_request="Read the public handbook.",
        user_role="employee",
        user_id="graph.user",
    )
    assert state["decision"] == "APPROVE"
    assert state["tool_result"]["simulated"] is True
    assert state["tool_result"]["found"] is True
    assert runtime.store.file_count() == before
    nodes = [item["node"] for item in state["trace"]]
    assert "propose_action" in nodes
    assert "agentshield_evaluate" in nodes
    assert "execute_tool" in nodes


def test_confidential_delete_does_not_execute(runtime):
    state = run_agent(
        runtime.graph,
        user_request="Delete the confidential employee database.",
        user_role="employee",
        user_id="graph.user",
    )
    assert state["decision"] == "BLOCK"
    assert state["tool_result"] is None
    assert runtime.store.get_file("confidential/employee_database.db") is not None
    assert "execute_tool" not in [item["node"] for item in state["trace"]]


def test_moderate_email_is_queued_not_sent(runtime):
    state = run_agent(
        runtime.graph,
        user_request="Email the vendor our launch timeline.",
        user_role="employee",
        user_id="graph.user",
    )
    assert state["decision"] == "HUMAN_APPROVAL"
    assert state["tool_result"] is None
    assert runtime.store.email_count() == 0
    pending = runtime.audit.list_approvals("pending")
    assert len(pending) == 1
    assert pending[0]["tool"] == "send_email"


def test_human_approval_then_reject_does_not_send(runtime):
    state = run_agent(
        runtime.graph,
        user_request="Email the vendor our launch timeline.",
        user_role="employee",
        user_id="graph.user",
    )
    approval_id = state["primary_governance"]["request_id"]
    runtime.audit.resolve_approval(approval_id, status="rejected", approver="ada", reason="no")
    assert runtime.store.email_count() == 0
