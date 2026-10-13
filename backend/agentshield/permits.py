"""HMAC permits. Tool execution code accepts only a verified APPROVE permit."""

import hashlib
import hmac
import json
from typing import Any

from backend.agentshield.models import ExecutionPermit


def canonical_payload(
    *,
    request_id: str,
    decision: str,
    tool: str,
    arguments: dict[str, Any],
    approver: str | None,
) -> str:
    """Stable JSON used as the signature input."""
    payload = {
        "approver": approver or "",
        "arguments": arguments,
        "decision": decision,
        "request_id": request_id,
        "tool": tool,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sign_payload(secret: str, payload: str) -> str:
    """Return a hex HMAC-SHA256 for ``payload``."""
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def mint_permit(
    secret: str,
    *,
    request_id: str,
    tool: str,
    arguments: dict[str, Any],
    approver: str | None = None,
) -> ExecutionPermit:
    """Mint an APPROVE permit. Refuses to mint any other decision."""
    decision = "APPROVE"
    payload = canonical_payload(
        request_id=request_id,
        decision=decision,
        tool=tool,
        arguments=arguments,
        approver=approver,
    )
    return ExecutionPermit(
        request_id=request_id,
        decision=decision,
        tool=tool,
        arguments=arguments,
        approver=approver,
        signature=sign_payload(secret, payload),
    )


def verify_permit(secret: str, permit: ExecutionPermit) -> bool:
    """Return True when the permit signature matches and the decision is APPROVE."""
    if permit.decision != "APPROVE" or not permit.signature:
        return False
    payload = canonical_payload(
        request_id=permit.request_id,
        decision=permit.decision,
        tool=permit.tool,
        arguments=permit.arguments,
        approver=permit.approver,
    )
    expected = sign_payload(secret, payload)
    return hmac.compare_digest(expected, permit.signature)
