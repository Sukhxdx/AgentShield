"""Policy authorization."""

from backend.agentshield.policy_engine import authorize


def test_guest_cannot_read_confidential():
    result = authorize(
        role="guest",
        tool="read_file",
        arguments={"path": "confidential/employee_database.db"},
        sensitivity="confidential",
    )
    assert result.authorized is False
    assert "sensitivity_exceeds_role" in result.violations


def test_employee_delete_is_denied():
    result = authorize(
        role="employee",
        tool="delete_file",
        arguments={"path": "confidential/employee_database.db"},
        sensitivity="confidential",
    )
    assert result.authorized is False
    assert "delete_not_permitted_for_role" in result.violations


def test_external_partner_requires_approval_and_unknown_domain_is_denied():
    partner = authorize(
        role="employee",
        tool="send_email",
        arguments={"to": "vendor@partner.example", "subject": "Hi", "body": "Timeline"},
        sensitivity="public",
    )
    assert partner.authorized is True
    assert partner.required_approval is True
    outsider = authorize(
        role="employee",
        tool="send_email",
        arguments={"to": "attacker@evil.com", "subject": "Hi", "body": "Files"},
        sensitivity="public",
    )
    assert outsider.authorized is False
    assert "external_recipient_denied" in outsider.violations


def test_path_traversal_is_a_violation():
    result = authorize(
        role="admin",
        tool="read_file",
        arguments={"path": "../etc/passwd"},
        sensitivity="unknown",
    )
    assert result.authorized is False
    assert "path_traversal" in result.violations
