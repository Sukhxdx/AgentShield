"""Generate 300 synthetic governance scenarios.

The target ``risk_score`` comes from a latent function that is deliberately
different from the additive rule engine in ``risk_rule_based``:

- tool, sensitivity, role, attack, amount, and impact use their own weights
- confidential or restricted deletes/payments add an interaction term
- an attack paired with email, delete, or payment adds a second interaction
- noise is Gaussian with standard deviation 2.0, then the value is clipped

The rule engine has neither interaction term. Identical feature rows therefore
teach the forest a score the rules would not have produced on their own.

Run from the repo root::

    python -m backend.ml.generate_dataset
"""

from pathlib import Path

import numpy as np
import pandas as pd

from backend.agentshield.features import action_impact, amount_bucket, derive_scenario_type
from backend.config import get_settings

_TOOL = {
    "none": 4.0,
    "search_documents": 9.0,
    "read_file": 14.0,
    "send_email": 27.0,
    "update_record": 31.0,
    "delete_file": 52.0,
    "make_payment": 40.0,
}
_SENS = {"public": 0.0, "internal": 7.0, "confidential": 18.0, "restricted": 24.0, "unknown": 9.0}
_ROLE = {"admin": -9.0, "manager": -4.0, "employee": 1.0, "service": 3.0, "guest": 14.0}
_ATTACK = {
    "none": 0.0,
    "direct_injection": 22.0,
    "indirect_injection": 19.0,
    "jailbreak": 21.0,
    "data_exfiltration": 18.0,
    "privilege_escalation": 24.0,
}
_AMOUNT = {"none": 0.0, "small": 3.0, "medium": 5.0, "large": 10.0, "very_large": 18.0}
_IMPACT = {"low": 2.0, "medium": 6.0, "high": 9.0}


def latent_risk(rng: np.random.Generator, **row: object) -> float:
    """Return the noisy latent target for one feature row."""
    tool = str(row["tool"])
    sensitivity = str(row["data_sensitivity"])
    attack = str(row["attack_type"])
    raw = (
        _TOOL[tool]
        + _SENS[sensitivity]
        + _ROLE[str(row["user_role"])]
        + _ATTACK[attack]
        + _AMOUNT[str(row["amount_bucket"])]
        + _IMPACT[str(row["action_impact"])]
        + (13.0 if row["external_recipient"] else 0.0)
    )
    if tool in {"delete_file", "make_payment"} and sensitivity in {"confidential", "restricted"}:
        raw += 12.0
    if attack != "none" and tool in {"send_email", "delete_file", "make_payment"}:
        raw += 6.0
    # Std 7.5 keeps repeated feature cells from becoming identical labels.
    noisy = raw + float(rng.normal(0.0, 7.5))
    return float(min(100.0, max(0.0, noisy)))


def _specs() -> list[dict[str, object]]:
    """Hand-balanced catalog. Counts are checked against 300 below."""
    rows: list[dict[str, object]] = []

    def add(count: int, **fields: object) -> None:
        policy_violation = bool(fields.pop("policy_violation"))
        amount = fields.pop("amount")
        tool = str(fields["tool"])
        attack = str(fields["attack_type"])
        for _ in range(count):
            rows.append(
                {
                    "attack_type": attack,
                    "user_role": fields["user_role"],
                    "tool": tool,
                    "data_sensitivity": fields["data_sensitivity"],
                    "action_impact": action_impact(tool),
                    "amount_bucket": amount_bucket(amount if isinstance(amount, (int, float)) else None),
                    "external_recipient": int(bool(fields["external_recipient"])),
                    "scenario_type": derive_scenario_type(attack, tool, policy_violation),
                }
            )

    # Safe reads and searches. The public employee read is the APPROVE reference.
    add(28, policy_violation=False, amount=None, attack_type="none", user_role="employee", tool="read_file", data_sensitivity="public", external_recipient=False)
    add(14, policy_violation=False, amount=None, attack_type="none", user_role="employee", tool="search_documents", data_sensitivity="public", external_recipient=False)
    add(10, policy_violation=False, amount=None, attack_type="none", user_role="employee", tool="read_file", data_sensitivity="internal", external_recipient=False)
    add(8, policy_violation=False, amount=None, attack_type="none", user_role="manager", tool="read_file", data_sensitivity="internal", external_recipient=False)
    add(8, policy_violation=False, amount=None, attack_type="none", user_role="guest", tool="search_documents", data_sensitivity="public", external_recipient=False)
    add(8, policy_violation=False, amount=None, attack_type="none", user_role="admin", tool="read_file", data_sensitivity="public", external_recipient=False)
    add(6, policy_violation=False, amount=None, attack_type="none", user_role="employee", tool="send_email", data_sensitivity="public", external_recipient=False)

    # Direct injection and jailbreaks.
    add(12, policy_violation=True, amount=None, attack_type="direct_injection", user_role="employee", tool="delete_file", data_sensitivity="confidential", external_recipient=False)
    add(8, policy_violation=True, amount=None, attack_type="direct_injection", user_role="employee", tool="send_email", data_sensitivity="confidential", external_recipient=True)
    add(8, policy_violation=True, amount=None, attack_type="jailbreak", user_role="guest", tool="read_file", data_sensitivity="restricted", external_recipient=False)
    add(8, policy_violation=False, amount=None, attack_type="direct_injection", user_role="employee", tool="search_documents", data_sensitivity="public", external_recipient=False)
    add(6, policy_violation=True, amount=25000, attack_type="jailbreak", user_role="employee", tool="make_payment", data_sensitivity="confidential", external_recipient=False)

    # Indirect injection living in retrieved content.
    add(14, policy_violation=True, amount=None, attack_type="indirect_injection", user_role="employee", tool="send_email", data_sensitivity="confidential", external_recipient=True)
    add(10, policy_violation=True, amount=None, attack_type="indirect_injection", user_role="employee", tool="delete_file", data_sensitivity="confidential", external_recipient=False)
    add(8, policy_violation=False, amount=None, attack_type="indirect_injection", user_role="manager", tool="read_file", data_sensitivity="internal", external_recipient=False)
    add(6, policy_violation=True, amount=None, attack_type="data_exfiltration", user_role="employee", tool="send_email", data_sensitivity="restricted", external_recipient=True)

    # Unauthorized, including the confidential-delete reference cell.
    add(16, policy_violation=True, amount=None, attack_type="none", user_role="employee", tool="delete_file", data_sensitivity="confidential", external_recipient=False)
    add(10, policy_violation=True, amount=None, attack_type="none", user_role="guest", tool="read_file", data_sensitivity="confidential", external_recipient=False)
    add(8, policy_violation=True, amount=None, attack_type="none", user_role="employee", tool="read_file", data_sensitivity="restricted", external_recipient=False)
    add(8, policy_violation=True, amount=25000, attack_type="none", user_role="employee", tool="make_payment", data_sensitivity="confidential", external_recipient=False)
    add(8, policy_violation=True, amount=None, attack_type="privilege_escalation", user_role="guest", tool="delete_file", data_sensitivity="restricted", external_recipient=False)
    add(6, policy_violation=True, amount=None, attack_type="none", user_role="employee", tool="update_record", data_sensitivity="confidential", external_recipient=False)

    # Legitimate high-impact work that should sit near human approval.
    add(10, policy_violation=False, amount=None, attack_type="none", user_role="admin", tool="delete_file", data_sensitivity="internal", external_recipient=False)
    add(10, policy_violation=False, amount=200, attack_type="none", user_role="manager", tool="make_payment", data_sensitivity="confidential", external_recipient=False)
    add(8, policy_violation=False, amount=4000, attack_type="none", user_role="manager", tool="make_payment", data_sensitivity="confidential", external_recipient=False)
    add(8, policy_violation=False, amount=None, attack_type="none", user_role="employee", tool="update_record", data_sensitivity="internal", external_recipient=False)
    add(6, policy_violation=False, amount=1000, attack_type="none", user_role="admin", tool="make_payment", data_sensitivity="confidential", external_recipient=False)
    add(8, policy_violation=False, amount=None, attack_type="none", user_role="employee", tool="send_email", data_sensitivity="public", external_recipient=True)

    # Extra variety so one-hot columns are not single-valued.
    add(6, policy_violation=False, amount=None, attack_type="none", user_role="service", tool="read_file", data_sensitivity="internal", external_recipient=False)
    add(6, policy_violation=True, amount=None, attack_type="data_exfiltration", user_role="manager", tool="send_email", data_sensitivity="confidential", external_recipient=True)
    add(5, policy_violation=False, amount=50, attack_type="none", user_role="admin", tool="make_payment", data_sensitivity="confidential", external_recipient=False)
    add(5, policy_violation=True, amount=None, attack_type="none", user_role="guest", tool="update_record", data_sensitivity="internal", external_recipient=False)
    add(4, policy_violation=False, amount=None, attack_type="none", user_role="manager", tool="search_documents", data_sensitivity="confidential", external_recipient=False)
    add(6, policy_violation=True, amount=12000, attack_type="direct_injection", user_role="manager", tool="make_payment", data_sensitivity="restricted", external_recipient=False)
    return rows


def generate(seed: int = 42) -> pd.DataFrame:
    """Build the 300-row frame with reproducible noise."""
    specs = _specs()
    if len(specs) != 300:
        raise RuntimeError(f"expected 300 scenarios, built {len(specs)}")
    rng = np.random.default_rng(seed)
    records = []
    for index, spec in enumerate(specs, start=1):
        score = latent_risk(rng, **spec)
        records.append({"scenario_id": f"S{index:03d}", **spec, "risk_score": round(score, 4)})
    return pd.DataFrame.from_records(records)


def main() -> None:
    """Write ``data/risk_scenarios.csv``."""
    settings = get_settings()
    frame = generate()
    destination = Path(settings.dataset_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    print(f"wrote {len(frame)} rows to {destination}")
    print(frame["scenario_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
