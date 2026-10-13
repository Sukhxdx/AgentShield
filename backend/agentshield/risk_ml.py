"""Load the random-forest risk model and score one proposed action.

If the artifact is missing or cannot be unpickled, prediction returns None.
Callers must treat that as fail-closed and fall back to the rule score,
flagged on the governance result.
"""

import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from backend.agentshield.features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


class RiskModel:
    """Joblib-backed regressor. The pipeline is loaded once per process."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.pipeline: Any | None = None
        self.available = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            logger.error(
                "risk model missing at %s; ML risk will fall back to the rule score",
                self.path,
            )
            return
        try:
            payload = joblib.load(self.path)
        except Exception:
            logger.exception("failed to load risk model at %s", self.path)
            return
        self.pipeline = payload["pipeline"] if isinstance(payload, dict) else payload
        self.available = self.pipeline is not None
        if self.available:
            logger.info("loaded risk model from %s", self.path)

    def predict(self, features: dict[str, Any]) -> float | None:
        """Return a risk in 0–100, or None when the model cannot be used."""
        if not self.available or self.pipeline is None:
            return None
        row = {column: features[column] for column in FEATURE_COLUMNS}
        frame = pd.DataFrame([row], columns=FEATURE_COLUMNS)
        try:
            raw = float(self.pipeline.predict(frame)[0])
        except Exception:
            logger.exception("risk model prediction failed")
            return None
        return float(min(100.0, max(0.0, raw)))
