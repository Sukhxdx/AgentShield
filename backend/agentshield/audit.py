"""Append-only SQLite audit trail and the human-approval queue.

Rows are inserted and never updated. A human decision is a new audit event
plus a status change on the queue row. The queue is operational state; the
audit table is the record.
"""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.agentshield.masking import mask_text, mask_value
from backend.agentshield.models import GovernanceResult


class AuditStore:
    """SQLite persistence for audit events, permits, and approvals."""

    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_id TEXT,
                    user_role TEXT,
                    user_request TEXT,
                    phase TEXT,
                    tool TEXT,
                    arguments_json TEXT,
                    injection_score INTEGER,
                    sensitive_info_score INTEGER,
                    attack_type TEXT,
                    policy_authorized INTEGER,
                    violations_json TEXT,
                    rule_risk INTEGER,
                    ml_risk REAL,
                    ml_fallback INTEGER,
                    combined_risk INTEGER,
                    risk_level TEXT,
                    decision TEXT,
                    explanation TEXT,
                    approver TEXT,
                    tool_executed INTEGER,
                    tool_result_summary TEXT,
                    latency_ms REAL
                );
                CREATE TABLE IF NOT EXISTS consumed_permits (
                    request_id TEXT PRIMARY KEY,
                    consumed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    user_id TEXT,
                    user_role TEXT,
                    user_request TEXT,
                    tool TEXT,
                    arguments_json TEXT,
                    governance_json TEXT,
                    approver TEXT,
                    resolved_at TEXT,
                    tool_result_json TEXT,
                    reason TEXT
                );
                """
            )
            self._conn.commit()

    def append(
        self,
        *,
        user_id: str,
        user_role: str,
        user_request: str,
        governance: GovernanceResult,
        tool: str,
        arguments: dict[str, Any],
        tool_executed: bool = False,
        tool_result: dict[str, Any] | None = None,
        approver: str | None = None,
        latency_ms: float | None = None,
        decision_override: str | None = None,
    ) -> None:
        """Insert one audit event. Secret-shaped text is masked first."""
        summary = ""
        if tool_result is not None:
            summary = mask_text(json.dumps(mask_value(tool_result), default=str))[:500]
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO audit_events (
                    request_id, timestamp, user_id, user_role, user_request, phase,
                    tool, arguments_json, injection_score, sensitive_info_score,
                    attack_type, policy_authorized, violations_json, rule_risk,
                    ml_risk, ml_fallback, combined_risk, risk_level, decision,
                    explanation, approver, tool_executed, tool_result_summary, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    governance.request_id,
                    governance.timestamp,
                    user_id,
                    user_role,
                    mask_text(user_request),
                    governance.phase,
                    tool,
                    json.dumps(mask_value(arguments), default=str),
                    governance.prompt_analysis.injection_score,
                    governance.prompt_analysis.sensitive_info_score,
                    governance.prompt_analysis.attack_type,
                    int(governance.policy_result.authorized),
                    json.dumps(governance.policy_result.violations),
                    governance.rule_risk.score,
                    governance.ml_risk,
                    int(governance.ml_fallback),
                    governance.combined_risk,
                    governance.risk_level,
                    decision_override or governance.decision,
                    governance.explanation,
                    approver,
                    int(tool_executed),
                    summary,
                    latency_ms,
                ),
            )
            self._conn.commit()

    def consume_permit(self, request_id: str) -> None:
        """Record a one-time permit use."""
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO consumed_permits (request_id, consumed_at) VALUES (?, ?)",
                    (request_id, datetime.now(UTC).isoformat()),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as exc:
                raise PermissionError(f"permit already used: {request_id}") from exc

    def list_events(
        self,
        *,
        decision: str | None = None,
        tool: str | None = None,
        role: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Return audit events, newest first, with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []
        if decision:
            clauses.append("decision = ?")
            params.append(decision)
        if tool:
            clauses.append("tool = ?")
            params.append(tool)
        if role:
            clauses.append("user_role = ?")
            params.append(role)
        if date_from:
            clauses.append("timestamp >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("timestamp <= ?")
            params.append(date_to)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM audit_events {where} ORDER BY id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def summary(self) -> dict[str, Any]:
        """Aggregate decision counts, average risk, and average latency."""
        with self._lock:
            counts = self._conn.execute(
                "SELECT decision, COUNT(*) AS n FROM audit_events GROUP BY decision"
            ).fetchall()
            averages = self._conn.execute(
                """
                SELECT COUNT(*) AS n,
                       AVG(combined_risk) AS avg_risk,
                       AVG(latency_ms) AS avg_latency
                FROM audit_events
                """
            ).fetchone()
        by_decision = {row["decision"]: row["n"] for row in counts}
        return {
            "total_requests": averages["n"] or 0,
            "counts_by_decision": by_decision,
            "average_combined_risk": averages["avg_risk"],
            "average_latency_ms": averages["avg_latency"],
        }

    def enqueue(
        self,
        *,
        approval_id: str,
        user_id: str,
        user_role: str,
        user_request: str,
        tool: str,
        arguments: dict[str, Any],
        governance: GovernanceResult,
    ) -> None:
        """Hold a proposal until a person approves or rejects it."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO approvals (
                    id, created_at, status, user_id, user_role, user_request,
                    tool, arguments_json, governance_json
                ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    datetime.now(UTC).isoformat(),
                    user_id,
                    user_role,
                    user_request,
                    tool,
                    json.dumps(arguments, default=str),
                    governance.model_dump_json(),
                ),
            )
            self._conn.commit()

    def list_approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        """Return queued proposals, optionally filtered by status."""
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM approvals WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM approvals ORDER BY created_at DESC"
                ).fetchall()
        return [dict(row) for row in rows]

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        """Return one queue row."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)
            ).fetchone()
        return dict(row) if row else None

    def resolve_approval(
        self,
        approval_id: str,
        *,
        status: str,
        approver: str,
        reason: str = "",
        tool_result: dict[str, Any] | None = None,
    ) -> None:
        """Mark a queue row approved or rejected."""
        with self._lock:
            self._conn.execute(
                """
                UPDATE approvals
                SET status = ?, approver = ?, resolved_at = ?, reason = ?, tool_result_json = ?
                WHERE id = ?
                """,
                (
                    status,
                    approver,
                    datetime.now(UTC).isoformat(),
                    reason,
                    json.dumps(mask_value(tool_result), default=str) if tool_result else None,
                    approval_id,
                ),
            )
            self._conn.commit()
