"""Properties that should hold for every score and every secret."""

from backend.agentshield.combiner import combine


def test_combined_risk_stays_inside_bounds():
    samples = [(-10, 0), (0, 0), (69, 92.49), (100, 100), (1000, -5), (30, 31)]
    for rule, ml in samples:
        assert 0 <= combine(rule, ml) <= 100


def test_weight_configuration_changes_the_blend():
    equal = combine(20, 80, 0.5, 0.5)
    rule_heavy = combine(20, 80, 0.9, 0.1)
    assert equal == 50
    assert rule_heavy < equal
