"""The vendored InjecAgent files are the published base-setting release."""

from backend.evaluation.injecagent import load_injecagent, summarize


def test_injecagent_base_setting_counts():
    cases = load_injecagent()
    summary = summarize(cases)
    assert summary["n_cases"] == 1054
    assert summary["by_family"] == {"direct_harm": 510, "data_stealing": 544}
    assert summary["by_attack_type"]["Financial Harm"] == 153
    assert summary["by_attack_type"]["Financial Data"] == 102


def test_injecagent_keeps_upstream_tool_names():
    first = load_injecagent()[0]
    assert first.case_id == "injecagent-dh-0001"
    assert first.user_tool == "AmazonGetProductDetails"
    assert first.attacker_tools == ("AugustSmartLockGrantGuestAccess",)
    assert "guest_amy01" in first.attacker_instruction
    assert first.attack_family == "direct_harm"
