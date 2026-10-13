"""Secrets do not survive into the audit log."""

from backend.agentshield.masking import mask_text
from backend.agentshield.models import ProposedAction


def test_mask_replaces_known_secret_shapes():
    raw = "email ada@company.example card 4111111111111111 key sk-live-SUPERSECRETKEY123456"
    masked = mask_text(raw)
    assert "ada@company.example" not in masked
    assert "4111111111111111" not in masked
    assert "sk-live-SUPERSECRETKEY123456" not in masked
    assert "REDACTED" in masked


def test_audit_log_does_not_store_the_secret(runtime):
    secret = "sk-live-SUPERSECRETKEY123456"
    runtime.service.evaluate(
        ProposedAction(
            tool="send_email",
            arguments={
                "to": "security@company.example",
                "subject": "key",
                "body": f"api_key={secret}",
            },
            reasoning="contains a secret",
        ),
        user_role="employee",
        user_id="mask.user",
        user_request=f"Please store {secret}",
    )
    events = runtime.audit.list_events()
    blob = " ".join(str(value) for event in events for value in event.values())
    assert secret not in blob
