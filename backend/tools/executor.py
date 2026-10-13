"""Tool executor. Implementations are unreachable without a valid APPROVE permit."""

import math
from typing import Any

from backend.agentshield.models import ExecutionPermit
from backend.agentshield.permits import verify_permit
from backend.tools.paths import check_path
from backend.tools.sandbox_store import SandboxStore


class ExecutionDenied(Exception):
    """Raised when a tool call is attempted without a valid APPROVE permit."""


class PermitLedger:
    """Remembers consumed permit ids so a signature cannot be replayed."""

    def __init__(self, consume: Any) -> None:
        self._consume = consume

    def consume(self, request_id: str) -> None:
        """Mark ``request_id`` used, or raise if it was already used."""
        self._consume(request_id)


def _read_file(arguments: dict[str, Any], store: SandboxStore) -> dict[str, Any]:
    checked = check_path(arguments.get("path"))
    if not checked.ok:
        raise ExecutionDenied(checked.reason)
    record = store.get_file(checked.normalized)
    if record is None:
        return {"tool": "read_file", "found": False, "path": checked.normalized}
    return {
        "tool": "read_file",
        "found": True,
        "path": record["path"],
        "title": record["title"],
        "sensitivity": record["sensitivity"],
        "content": record["content"],
    }


def _search(arguments: dict[str, Any], store: SandboxStore) -> dict[str, Any]:
    query = str(arguments.get("query", "")).strip()
    if not query:
        raise ExecutionDenied("query_required")
    hits = store.search(query)
    return {"tool": "search_documents", "query": query, "hits": hits, "count": len(hits)}


def _send_email(arguments: dict[str, Any], store: SandboxStore) -> dict[str, Any]:
    recipient = str(arguments.get("to", "")).strip()
    subject = str(arguments.get("subject", "")).strip()
    body = str(arguments.get("body", "")).strip()
    if not recipient or "@" not in recipient:
        raise ExecutionDenied("recipient_required")
    saved = store.send_email(recipient, subject, body, "internal")
    return {"tool": "send_email", **saved}


def _update_record(arguments: dict[str, Any], store: SandboxStore) -> dict[str, Any]:
    record_id = str(arguments.get("record_id", "")).strip()
    fields = arguments.get("fields")
    if not record_id or not isinstance(fields, dict):
        raise ExecutionDenied("record_fields_required")
    updated = store.update_record(record_id, fields)
    if updated is None:
        return {"tool": "update_record", "found": False, "record_id": record_id}
    return {
        "tool": "update_record",
        "found": True,
        "record_id": record_id,
        "sensitivity": updated["sensitivity"],
        "fields": updated["fields"],
    }


def _delete_file(arguments: dict[str, Any], store: SandboxStore) -> dict[str, Any]:
    checked = check_path(arguments.get("path"))
    if not checked.ok:
        raise ExecutionDenied(checked.reason)
    removed = store.delete_file(checked.normalized)
    if removed is None:
        return {"tool": "delete_file", "deleted": False, "path": checked.normalized}
    return {
        "tool": "delete_file",
        "deleted": True,
        "path": removed["path"],
        "sensitivity": removed["sensitivity"],
        "title": removed["title"],
    }


def _make_payment(arguments: dict[str, Any], store: SandboxStore) -> dict[str, Any]:
    payee = str(arguments.get("payee", "")).strip()
    currency = str(arguments.get("currency", "")).strip().upper()
    try:
        amount = float(arguments.get("amount"))
    except (TypeError, ValueError):
        raise ExecutionDenied("amount_required") from None
    if not payee or not math.isfinite(amount) or amount <= 0:
        raise ExecutionDenied("amount_required")
    if currency not in {"USD", "EUR", "INR"}:
        raise ExecutionDenied("currency_not_allowed")
    saved = store.make_payment(payee, amount, currency)
    return {"tool": "make_payment", **saved}


_IMPLEMENTATIONS = {
    "read_file": _read_file,
    "search_documents": _search,
    "send_email": _send_email,
    "update_record": _update_record,
    "delete_file": _delete_file,
    "make_payment": _make_payment,
}


def execute(
    permit: ExecutionPermit,
    store: SandboxStore,
    *,
    secret: str,
    ledger: PermitLedger,
) -> dict[str, Any]:
    """Run a simulated tool.

    The implementation table is private to this function. Callers must present
    a signed :class:`ExecutionPermit` whose decision is APPROVE.
    """
    if not isinstance(permit, ExecutionPermit):
        raise ExecutionDenied("permit_required")
    if permit.decision != "APPROVE":
        raise ExecutionDenied("approve_required")
    if not verify_permit(secret, permit):
        raise ExecutionDenied("invalid_signature")
    implementation = _IMPLEMENTATIONS.get(permit.tool)
    if implementation is None:
        raise ExecutionDenied("unknown_tool")
    ledger.consume(permit.request_id)
    result = implementation(permit.arguments, store)
    result["simulated"] = True
    return result
