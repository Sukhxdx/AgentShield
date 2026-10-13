"""Deterministic role, sensitivity, path, and argument authorization."""

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.agentshield.models import PolicyResult
from backend.tools.paths import check_path
from backend.tools.registry import TOOL_SCHEMAS
from backend.tools.sandbox_store import SandboxStore

_POLICY_PATH = Path(__file__).with_name("policy.yml")
_RANK = {"public": 0, "internal": 1, "unknown": 1, "confidential": 2, "restricted": 3}


@lru_cache
def load_policy() -> dict[str, Any]:
    """Load and cache the YAML policy document."""
    return yaml.safe_load(_POLICY_PATH.read_text(encoding="utf-8"))


def _domain(address: str) -> str:
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[-1].lower().strip()


def _matches_domain(domain: str, suffixes: list[str]) -> bool:
    return any(domain == item or domain.endswith("." + item) for item in suffixes)


def resolve_sensitivity(store: SandboxStore, tool: str, arguments: dict[str, Any]) -> str:
    """Look up the data sensitivity the proposed call would touch."""
    if tool in {"read_file", "delete_file"}:
        checked = check_path(arguments.get("path"))
        if not checked.ok:
            return "unknown"
        record = store.get_file(checked.normalized)
        return record["sensitivity"] if record else "public"
    if tool == "search_documents":
        hits = store.search(str(arguments.get("query", "")))
        if not hits:
            return "public"
        return max(hits, key=lambda hit: _RANK.get(hit["sensitivity"], 0))["sensitivity"]
    if tool == "update_record":
        record = store.get_record(str(arguments.get("record_id", "")))
        return record["sensitivity"] if record else "unknown"
    if tool == "make_payment":
        return "confidential"
    return "public"


def _schema_violations(tool: str, arguments: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if tool == "none":
        return violations
    schema = TOOL_SCHEMAS.get(tool)
    if schema is None:
        return ["unknown_tool"]
    required = schema["parameters"]["required"]
    for field in required:
        if field not in arguments or arguments[field] in ("", None):
            violations.append(f"missing_argument:{field}")
    if tool in {"read_file", "delete_file"} and "path" in arguments:
        checked = check_path(arguments.get("path"))
        if not checked.ok:
            violations.append(checked.reason)
    if tool == "update_record" and "fields" in arguments and not isinstance(arguments["fields"], dict):
        violations.append("fields_must_be_object")
    if tool == "make_payment":
        try:
            amount = float(arguments.get("amount"))
        except (TypeError, ValueError):
            violations.append("amount_not_numeric")
        else:
            if not math.isfinite(amount) or amount <= 0:
                violations.append("amount_not_positive")
        currency = str(arguments.get("currency", "")).upper()
        if currency and currency not in policy["allowed_currencies"]:
            violations.append("currency_not_allowed")
    if tool == "send_email":
        recipient = str(arguments.get("to", ""))
        if recipient and "@" not in recipient:
            violations.append("recipient_not_email")
    return violations


def authorize(
    *,
    role: str,
    tool: str,
    arguments: dict[str, Any],
    sensitivity: str,
    store: SandboxStore | None = None,
) -> PolicyResult:
    """Authorize one proposed call. Unknown roles are denied."""
    del store  # sensitivity is resolved by the caller; kept for a stable signature
    policy = load_policy()
    role_policy = policy["roles"].get(role)
    if role_policy is None:
        return PolicyResult(
            authorized=False,
            violations=["unknown_role"],
            required_approval=False,
            reasons=["The role is not in the policy file."],
        )
    if tool == "none":
        return PolicyResult(
            authorized=True,
            violations=[],
            required_approval=False,
            reasons=["No tool was proposed."],
        )

    violations = _schema_violations(tool, arguments, policy)
    reasons: list[str] = []
    if tool not in role_policy["tools"]:
        violations.append("tool_not_allowed_for_role")
        reasons.append(f"{role} cannot call {tool}.")

    allowed_sensitivity = role_policy["max_sensitivity"].get(tool, "public")
    if _RANK.get(sensitivity, 3) > _RANK.get(allowed_sensitivity, 0):
        violations.append("sensitivity_exceeds_role")
        reasons.append(
            f"{tool} would touch {sensitivity} data; {role} is limited to {allowed_sensitivity}."
        )

    if tool == "delete_file":
        if not role_policy.get("allow_delete", False):
            violations.append("delete_not_permitted_for_role")
            reasons.append(f"{role} is not allowed to delete files.")
        if sensitivity in role_policy.get("delete_denied_sensitivities", []):
            violations.append("delete_forbidden_on_sensitivity")
            reasons.append(f"Deletes of {sensitivity} data are denied.")

    if tool == "make_payment":
        try:
            amount = float(arguments.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0
        limit = float(role_policy.get("payment_limit", 0))
        if amount > limit:
            violations.append("payment_over_limit")
            reasons.append(f"Amount {amount:g} exceeds the {role} limit of {limit:g}.")

    required = False
    approval_roles = policy.get("approval_tools", {}).get(tool, [])
    if role in approval_roles and tool in role_policy["tools"]:
        required = True
        reasons.append(f"{tool} requires human approval for {role}.")

    if tool == "send_email":
        domain = _domain(str(arguments.get("to", "")))
        internal = _matches_domain(domain, policy["internal_email_domains"]) if domain else False
        external = bool(domain) and not internal
        if external:
            allowed = _matches_domain(domain, policy.get("external_email_allow", []))
            mode = role_policy.get("external_email", "deny")
            if mode == "deny" or not allowed:
                violations.append("external_recipient_denied")
                reasons.append(f"Mail to {domain} is outside the approved recipient list.")
            elif mode == "approval":
                required = True
                reasons.append(f"Mail to {domain} needs human approval.")

    # Schema problems are still violations even when later rules also fire.
    authorized = not violations
    if not authorized:
        reasons.append("Authorization failed; the decision cannot be loosened by the risk score.")
    return PolicyResult(
        authorized=authorized,
        violations=list(dict.fromkeys(violations)),
        required_approval=required,
        reasons=reasons,
    )
