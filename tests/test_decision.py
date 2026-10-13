"""Decision thresholds and policy tightening."""

import pytest
from backend.agentshield.combiner import combine
from backend.agentshield.decision_engine import (
    apply_policy_overrides,
    decide,
    threshold_decision,
)
from backend.agentshield.models import PolicyResult, PromptAnalysis, RuleRisk


def _analysis() -> PromptAnalysis:
    return PromptAnalysis(
        injection_score=0,
        sensitive_info_score=0,
        flags=[],
        matched_patterns=[],
        attack_type="none",
    )


def _policy(**overrides) -> PolicyResult:
    payload = {"authorized": True, "violations": [], "required_approval": False, "reasons": []}
    payload.update(overrides)
    return PolicyResult(**payload)


def _rule(score: int) -> RuleRisk:
    return RuleRisk(score=score, breakdown={"tool_impact": score}, level="LOW")


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "APPROVE"), (30, "APPROVE"), (31, "HUMAN_APPROVAL"), (70, "HUMAN_APPROVAL"), (71, "BLOCK"), (100, "BLOCK")],
)
def test_threshold_boundaries(score, expected):
    assert threshold_decision(score) == expected


def test_combiner_reference_identity():
    assert combine(69, 92.49) == 81


def test_policy_block_overrides_a_low_score():
    result = decide(
        tool="read_file",
        arguments={"path": "confidential/employee_database.db"},
        rule=_rule(10),
        ml_risk=10,
        ml_fallback=False,
        analysis=_analysis(),
        policy=_policy(authorized=False, violations=["sensitivity_exceeds_role"]),
        secret="test-secret",
    )
    assert result.decision == "BLOCK"
    assert result.permit is None


def test_required_approval_upgrades_approve():
    result = decide(
        tool="send_email",
        arguments={"to": "vendor@partner.example"},
        rule=_rule(10),
        ml_risk=10,
        ml_fallback=False,
        analysis=_analysis(),
        policy=_policy(required_approval=True, reasons=["needs a human"]),
        secret="test-secret",
    )
    assert result.decision == "HUMAN_APPROVAL"
    assert result.permit is None


def test_approve_mints_a_permit():
    result = decide(
        tool="read_file",
        arguments={"path": "guidelines/public_handbook.md"},
        rule=_rule(10),
        ml_risk=10,
        ml_fallback=False,
        analysis=_analysis(),
        policy=_policy(),
        secret="test-secret",
    )
    assert result.decision == "APPROVE"
    assert result.permit is not None
    assert result.permit.decision == "APPROVE"


def test_override_never_loosens():
    order = {"APPROVE": 0, "HUMAN_APPROVAL": 1, "BLOCK": 2}
    for score in range(0, 101):
        numeric = threshold_decision(score)
        for authorized in (True, False):
            for required in (True, False):
                policy = _policy(
                    authorized=authorized,
                    violations=[] if authorized else ["denied"],
                    required_approval=required,
                )
                actual = apply_policy_overrides(numeric, policy)
                assert order[actual] >= order[numeric]
                if not authorized:
                    assert actual == "BLOCK"
                if authorized and required:
                    assert actual != "APPROVE"
