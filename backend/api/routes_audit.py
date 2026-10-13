"""Audit log and summary metrics."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.api.deps import get_runtime, require_api_key
from backend.runtime import Runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/audit")
def list_audit(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    decision: str | None = None,
    tool: str | None = None,
    role: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Return masked audit events, newest first."""
    events = runtime.audit.list_events(
        decision=decision,
        tool=tool,
        role=role,
        date_from=date_from,
        date_to=date_to,
        limit=min(limit, 500),
    )
    return {"events": events}


@router.get("/metrics/summary")
def metrics_summary(runtime: Annotated[Runtime, Depends(get_runtime)]) -> dict[str, Any]:
    """Counts by decision, average combined risk, and average latency."""
    return runtime.audit.summary()
