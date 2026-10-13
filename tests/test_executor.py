"""The executor refuses every call that is not a signed APPROVE permit."""

import pytest
from backend.agentshield.models import ExecutionPermit
from backend.agentshield.permits import mint_permit
from backend.tools.executor import ExecutionDenied, PermitLedger, execute
from backend.tools.sandbox_store import SandboxStore
from pydantic import ValidationError


def test_block_shaped_object_cannot_execute():
    with pytest.raises(ValidationError):
        ExecutionPermit(
            request_id="1",
            decision="BLOCK",  # type: ignore[arg-type]
            tool="delete_file",
            arguments={"path": "confidential/employee_database.db"},
            signature="forged",
        )


def test_forged_approve_is_denied(tmp_path):
    store = SandboxStore(str(tmp_path / "sandbox.db"))
    permit = ExecutionPermit(
        request_id="1",
        decision="APPROVE",
        tool="delete_file",
        arguments={"path": "confidential/employee_database.db"},
        signature="forged",
    )
    with pytest.raises(ExecutionDenied):
        execute(permit, store, secret="test-secret", ledger=PermitLedger(lambda _id: None))
    assert store.get_file("confidential/employee_database.db") is not None


def test_valid_permit_runs_once(tmp_path):
    store = SandboxStore(str(tmp_path / "sandbox.db"))
    used: set[str] = set()

    def consume(request_id: str) -> None:
        if request_id in used:
            raise PermissionError("replay")
        used.add(request_id)

    permit = mint_permit(
        "test-secret",
        request_id="once",
        tool="read_file",
        arguments={"path": "guidelines/public_handbook.md"},
    )
    result = execute(permit, store, secret="test-secret", ledger=PermitLedger(consume))
    assert result["simulated"] is True
    assert result["found"] is True
    with pytest.raises(PermissionError):
        execute(permit, store, secret="test-secret", ledger=PermitLedger(consume))
