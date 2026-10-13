"""ML artifact shape and range."""

from backend.agentshield.features import FEATURE_COLUMNS
from backend.agentshield.risk_ml import RiskModel


def test_prediction_is_a_bounded_float():
    model = RiskModel("backend/ml/artifacts/risk_model.joblib")
    assert model.available
    features = {
        "scenario_type": "unauthorized",
        "attack_type": "none",
        "user_role": "employee",
        "tool": "delete_file",
        "data_sensitivity": "confidential",
        "action_impact": "high",
        "amount_bucket": "none",
        "external_recipient": 0,
    }
    assert list(features) == FEATURE_COLUMNS
    score = model.predict(features)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_missing_model_fails_closed(tmp_path):
    model = RiskModel(tmp_path / "missing.joblib")
    assert model.available is False
    assert model.predict({"tool": "read_file"}) is None
