"""Rule-based score, including the documented reference total of 69."""

from backend.agentshield.risk_rule_based import rule_risk


def test_confidential_database_deletion_scores_69():
    scored = rule_risk(
        tool="delete_file",
        sensitivity="confidential",
        role="employee",
        injection_score=0,
        sensitive_info_score=40,
        policy_violations=["delete_not_permitted_for_role"],
        arguments={"path": "confidential/employee_database.db"},
        external_recipient=False,
    )
    assert scored.breakdown == {
        "tool_impact": 32,
        "data_sensitivity": 15,
        "role_context": 0,
        "prompt_injection": 0,
        "sensitive_information": 4,
        "policy_pressure": 8,
        "irreversibility": 10,
        "transaction_amount": 0,
        "external_exposure": 0,
    }
    assert scored.score == 69
    assert sum(scored.breakdown.values()) == scored.score


def test_breakdown_stays_aligned_when_clamped():
    scored = rule_risk(
        tool="delete_file",
        sensitivity="restricted",
        role="guest",
        injection_score=100,
        sensitive_info_score=100,
        policy_violations=["tool_not_allowed_for_role"],
        arguments={},
        external_recipient=True,
    )
    assert 0 <= scored.score <= 100
    assert sum(scored.breakdown.values()) == scored.score


def test_public_read_is_low():
    scored = rule_risk(
        tool="read_file",
        sensitivity="public",
        role="employee",
        injection_score=0,
        sensitive_info_score=0,
        policy_violations=[],
        arguments={"path": "guidelines/public_handbook.md"},
        external_recipient=False,
    )
    assert scored.score == 10
    assert scored.level == "LOW"
