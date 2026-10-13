"""The five named scenarios, plus the full catalog's expected decisions."""

from backend.agentshield.models import ProposedAction
from backend.evaluation.test_cases import load_test_cases, named_cases


def test_named_security_scenarios(runtime):
    expected = {
        "public_guideline_access": "APPROVE",
        "unauthorized_file_access": "BLOCK",
        "confidential_database_deletion": "BLOCK",
        "moderate_risk_action": "HUMAN_APPROVAL",
        "high_impact_action": "BLOCK",
    }
    for case in named_cases():
        result = runtime.service.evaluate(
            ProposedAction(tool=case.tool, arguments=case.arguments, reasoning=case.name),
            user_role=case.user_role,
            user_id="named.scenario",
            user_request=case.user_request,
            retrieved_context=case.retrieved_context,
        )
        assert result.decision == expected[case.case_id]
        if case.case_id == "confidential_database_deletion":
            assert result.rule_risk.score == 69
            assert result.risk_level == "HIGH"
            assert result.decision == "BLOCK"
        if result.decision != "APPROVE":
            assert result.permit is None


def test_catalog_matches_expected_decisions(runtime):
    mismatches = []
    for case in load_test_cases():
        result = runtime.service.evaluate(
            ProposedAction(tool=case.tool, arguments=case.arguments, reasoning=case.name),
            user_role=case.user_role,
            user_id="catalog",
            user_request=case.user_request,
            retrieved_context=case.retrieved_context,
        )
        if result.decision != case.expected_decision:
            mismatches.append(
                f"{case.case_id}: expected {case.expected_decision} got {result.decision} "
                f"rule={result.rule_risk.score} ml={result.ml_risk:.2f} combined={result.combined_risk} "
                f"violations={result.policy_result.violations}"
            )
    assert mismatches == []
