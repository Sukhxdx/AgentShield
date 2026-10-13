"""Human approval queue. Approve mints a one-time APPROVE permit and executes."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.agent.graph import approve_and_execute
from backend.agentshield.masking import mask_text, mask_value
from backend.agentshield.models import ApprovalDecision, GovernanceResult
from backend.api.deps import get_runtime, require_api_key
from backend.runtime import Runtime
from backend.tools.executor import ExecutionDenied

router = APIRouter(prefix="/approvals", dependencies=[Depends(require_api_key)])


def _public(row: dict[str, Any]) -> dict[str, Any]:
    arguments = json.loads(row["arguments_json"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "status": row["status"],
        "user_id": row["user_id"],
        "user_role": row["user_role"],
        "user_request": mask_text(row["user_request"] or ""),
        "tool": row["tool"],
        "arguments": mask_value(arguments),
        "approver": row["approver"],
        "resolved_at": row["resolved_at"],
        "reason": row["reason"],
        "governance": json.loads(row["governance_json"]),
        "tool_result": json.loads(row["tool_result_json"]) if row["tool_result_json"] else None,
    }


@router.get("")
def list_approvals(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    status: str | None = None,
) -> dict[str, Any]:
    """List queued proposals. Secrets in arguments are masked."""
    rows = runtime.audit.list_approvals(status)
    return {"approvals": [_public(row) for row in rows]}


@router.post("/{approval_id}/approve")
def approve(
    approval_id: str,
    body: ApprovalDecision,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, Any]:
    """Execute a held tool once, under the named approver."""
    row = runtime.audit.get_approval(approval_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail="Approval is already resolved")
    arguments = json.loads(row["arguments_json"])
    try:
        result = approve_and_execute(
            settings=runtime.settings,
            store=runtime.store,
            audit=runtime.audit,
            approval_id=approval_id,
            approver=body.approver,
            arguments=arguments,
            tool=row["tool"],
        )
    except (ExecutionDenied, PermissionError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    runtime.audit.resolve_approval(
        approval_id,
        status="approved",
        approver=body.approver,
        reason=body.reason,
        tool_result=result,
    )
    governance = GovernanceResult.model_validate(json.loads(row["governance_json"]))
    runtime.audit.append(
        user_id=row["user_id"],
        user_role=row["user_role"],
        user_request=row["user_request"],
        governance=governance,
        tool=row["tool"],
        arguments=arguments,
        tool_executed=True,
        tool_result=result,
        approver=body.approver,
        decision_override="APPROVE",
    )
    return {"status": "approved", "approver": body.approver, "tool_result": result}


@router.post("/{approval_id}/reject")
def reject(
    approval_id: str,
    body: ApprovalDecision,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, Any]:
    """Reject a held tool. Nothing is executed."""
    row = runtime.audit.get_approval(approval_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail="Approval is already resolved")
    runtime.audit.resolve_approval(
        approval_id,
        status="rejected",
        approver=body.approver,
        reason=body.reason or "rejected",
    )
    governance = GovernanceResult.model_validate(json.loads(row["governance_json"]))
    runtime.audit.append(
        user_id=row["user_id"],
        user_role=row["user_role"],
        user_request=row["user_request"],
        governance=governance,
        tool=row["tool"],
        arguments=json.loads(row["arguments_json"]),
        tool_executed=False,
        approver=body.approver,
        decision_override="BLOCK",
    )
    return {"status": "rejected", "approver": body.approver, "tool_result": None}
