"""Serve the latest with-versus-without comparison and model metrics."""

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.api.deps import get_runtime, require_api_key
from backend.runtime import Runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/evaluation/latest")
def latest_evaluation(runtime: Annotated[Runtime, Depends(get_runtime)]) -> dict[str, Any]:
    """Return the comparison report and the trained model's held-out metrics."""
    results = Path(runtime.settings.results_dir)
    model_metrics = _read_json(runtime.settings.resolved_model_path().with_name("metrics.json"))
    comparison = _read_json(results / "comparison.json")
    charts = sorted(item.name for item in results.glob("*.png")) if results.exists() else []
    return {
        "available": comparison is not None,
        "label": "ToolEmu-style local emulator (upstream ToolEmu was not executed)",
        "comparison": comparison,
        "model_metrics": model_metrics,
        "charts": [f"/evaluation/artifacts/{name}" for name in charts],
    }
