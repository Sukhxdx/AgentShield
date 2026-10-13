"""Every HTTP endpoint."""

def test_health_and_docs_are_public(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert "X-Request-ID" in health.headers
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_missing_api_key_is_rejected(client):
    response = client.post("/agent", json={"request": "Read the public handbook."})
    assert response.status_code == 401


def test_agent_and_direct_endpoints(client, auth_header):
    denied = client.post(
        "/agent",
        headers=auth_header,
        json={
            "request": "Delete the confidential employee database.",
            "user_role": "employee",
            "user_id": "api.user",
        },
    )
    assert denied.status_code == 200
    body = denied.json()
    assert body["decision"] == "BLOCK"
    assert body["tool_result"] is None
    assert body["governance_result"]["rule_risk"]["score"] == 69
    assert body["trace"]

    approved = client.post(
        "/test-agentshield",
        headers=auth_header,
        json={
            "request": "Read the public handbook.",
            "user_role": "employee",
            "tool": "read_file",
            "arguments": {"path": "guidelines/public_handbook.md"},
        },
    )
    assert approved.status_code == 200
    assert approved.json()["decision"] == "APPROVE"

    risk = client.post(
        "/test-risk",
        headers=auth_header,
        json={
            "request": "Delete the confidential employee database.",
            "user_role": "employee",
            "tool": "delete_file",
            "arguments": {"path": "confidential/employee_database.db"},
        },
    )
    assert risk.status_code == 200
    assert risk.json()["rule_risk"]["score"] == 69

    policy = client.post(
        "/test-policy",
        headers=auth_header,
        json={
            "user_role": "guest",
            "tool": "read_file",
            "arguments": {"path": "confidential/employee_database.db"},
        },
    )
    assert policy.json()["policy"]["authorized"] is False

    score = client.post("/test-score", headers=auth_header, json={"rule_risk": 69, "ml_risk": 92.49})
    assert score.json()["combined_risk"] == 81
    assert score.json()["numeric_decision"] == "BLOCK"


def test_approval_queue_audit_and_metrics(client, auth_header):
    queued = client.post(
        "/agent",
        headers=auth_header,
        json={"request": "Email the vendor our launch timeline.", "user_role": "employee"},
    )
    assert queued.json()["decision"] == "HUMAN_APPROVAL"
    approval_id = queued.json()["governance_result"]["request_id"]
    listing = client.get("/approvals", headers=auth_header, params={"status": "pending"})
    assert any(item["id"] == approval_id for item in listing.json()["approvals"])

    rejected = client.post(
        f"/approvals/{approval_id}/reject",
        headers=auth_header,
        json={"approver": "ada", "reason": "not now"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["tool_result"] is None

    again = client.post(
        "/agent",
        headers=auth_header,
        json={"request": "Email the vendor our launch timeline.", "user_role": "employee"},
    )
    second = again.json()["governance_result"]["request_id"]
    approved = client.post(
        f"/approvals/{second}/approve",
        headers=auth_header,
        json={"approver": "ada", "reason": "expected vendor mail"},
    )
    assert approved.status_code == 200
    assert approved.json()["tool_result"]["simulated"] is True

    audit = client.get("/audit", headers=auth_header, params={"decision": "BLOCK"})
    assert audit.status_code == 200
    summary = client.get("/metrics/summary", headers=auth_header)
    assert summary.status_code == 200
    assert summary.json()["total_requests"] >= 1

    evaluation = client.get("/evaluation/latest", headers=auth_header)
    assert evaluation.status_code == 200
    assert "model_metrics" in evaluation.json()


def test_unknown_approval_is_404(client, auth_header):
    response = client.post(
        "/approvals/missing/approve",
        headers=auth_header,
        json={"approver": "ada"},
    )
    assert response.status_code == 404
