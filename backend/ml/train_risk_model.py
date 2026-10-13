"""Train a RandomForestRegressor on the synthetic scenario table.

Split is 80/20 (240/60) with ``random_state=42``. Metrics are computed on the
held-out split and written to ``metrics.json``. They are not hard-coded.

Run from the repo root::

    python -m backend.ml.train_risk_model
"""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from backend.agentshield.features import FEATURE_COLUMNS
from backend.config import get_settings

CATEGORICAL = [
    "scenario_type",
    "attack_type",
    "user_role",
    "tool",
    "data_sensitivity",
    "action_impact",
    "amount_bucket",
]
NUMERIC = ["external_recipient"]


def build_pipeline(random_state: int = 42) -> Pipeline:
    """Return an unfitted preprocessing and forest pipeline."""
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categories",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL,
            ),
            ("numbers", "passthrough", NUMERIC),
        ]
    )
    model = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=1,
        random_state=random_state,
    )
    return Pipeline([("prep", preprocessor), ("model", model)])


def train(frame: pd.DataFrame, random_state: int = 42) -> tuple[Pipeline, dict[str, object]]:
    """Fit on 240 rows and score the remaining 60."""
    features = frame[FEATURE_COLUMNS]
    target = frame["risk_score"].astype(float)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=random_state,
    )
    if len(x_train) != 240 or len(x_test) != 60:
        raise RuntimeError(f"unexpected split sizes {len(x_train)}/{len(x_test)}")
    pipeline = build_pipeline(random_state)
    cv_mae = -cross_val_score(
        pipeline, x_train, y_train, cv=5, scoring="neg_mean_absolute_error"
    )
    cv_rmse = -cross_val_score(
        pipeline, x_train, y_train, cv=5, scoring="neg_root_mean_squared_error"
    )
    pipeline.fit(x_train, y_train)
    predicted = pipeline.predict(x_test)
    names = pipeline.named_steps["prep"].get_feature_names_out()
    importances = pipeline.named_steps["model"].feature_importances_
    ranked = sorted(
        (
            {"feature": str(name), "importance": round(float(value), 6)}
            for name, value in zip(names, importances, strict=True)
        ),
        key=lambda item: item["importance"],
        reverse=True,
    )
    metrics: dict[str, object] = {
        "mae": round(float(mean_absolute_error(y_test, predicted)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_test, predicted))), 4),
        "r2": round(float(r2_score(y_test, predicted)), 4),
        "cv_mae_mean": round(float(cv_mae.mean()), 4),
        "cv_mae_std": round(float(cv_mae.std()), 4),
        "cv_rmse_mean": round(float(cv_rmse.mean()), 4),
        "n_train": int(len(x_train)),
        "n_test": int(len(x_test)),
        "n_samples": int(len(frame)),
        "random_state": random_state,
        "model": "RandomForestRegressor",
        "feature_importances": ranked[:15],
    }
    return pipeline, metrics


def main() -> None:
    """Train and write the joblib artifact plus metrics.json."""
    settings = get_settings()
    frame = pd.read_csv(settings.dataset_path)
    pipeline, metrics = train(frame)
    destination = settings.resolved_model_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "feature_columns": FEATURE_COLUMNS, "version": 1}, destination)
    metrics_path = destination.with_name("metrics.json")
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({key: metrics[key] for key in ("mae", "rmse", "r2", "n_train", "n_test")}, indent=2))
    print(f"wrote {destination}")
    print(f"wrote {metrics_path}")


if __name__ == "__main__":
    main()
