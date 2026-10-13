"""Loader for the published InjecAgent benchmark.

InjecAgent (Zhan et al., 2024, https://arxiv.org/abs/2403.02691) is a real
indirect-prompt-injection dataset for tool-using agents. The files under
``data/injecagent/`` are the upstream base-setting release: 510 direct-harm
cases and 544 data-stealing cases (1,054 total). They keep the authors' tool
names (Amazon, August Smart Lock, and so on). Those tools are not AgentShield's
six sandbox tools, and the files do not contain the synthetic ``risk_score``
labels used to train the forest.

Source: https://github.com/uiuc-kang-lab/InjecAgent (MIT, see ``data/injecagent/LICENCE``).
"""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2] / "data" / "injecagent"
_FILES = {
    "direct_harm": "test_cases_dh_base.json",
    "data_stealing": "test_cases_ds_base.json",
}


@dataclass(frozen=True)
class InjecAgentCase:
    """One published base-setting test case."""

    case_id: str
    attack_family: str
    attack_type: str
    user_tool: str
    user_instruction: str
    attacker_tools: tuple[str, ...]
    attacker_instruction: str
    tool_response: str
    expected_achievements: str


def dataset_dir() -> Path:
    """Return the directory that holds the vendored InjecAgent files."""
    return _ROOT


def load_injecagent(root: Path | None = None) -> list[InjecAgentCase]:
    """Load the 1,054 base-setting cases from the vendored JSON files."""
    base = root or _ROOT
    cases: list[InjecAgentCase] = []
    for family, filename in _FILES.items():
        path = base / filename
        rows = json.loads(path.read_text(encoding="utf-8"))
        prefix = "dh" if family == "direct_harm" else "ds"
        for index, row in enumerate(rows, start=1):
            tools = row.get("Attacker Tools") or []
            cases.append(
                InjecAgentCase(
                    case_id=f"injecagent-{prefix}-{index:04d}",
                    attack_family=family,
                    attack_type=str(row.get("Attack Type", "")),
                    user_tool=str(row.get("User Tool", "")),
                    user_instruction=str(row.get("User Instruction", "")),
                    attacker_tools=tuple(str(tool) for tool in tools),
                    attacker_instruction=str(row.get("Attacker Instruction", "")),
                    tool_response=str(row.get("Tool Response", "")),
                    expected_achievements=str(row.get("Expected Achievements", "")),
                )
            )
    return cases


def summarize(cases: list[InjecAgentCase] | None = None) -> dict[str, object]:
    """Count cases by family and by the authors' attack-type labels."""
    rows = cases if cases is not None else load_injecagent()
    by_family = Counter(case.attack_family for case in rows)
    by_type = Counter(case.attack_type for case in rows)
    return {
        "dataset": "InjecAgent",
        "paper": "https://arxiv.org/abs/2403.02691",
        "setting": "base",
        "n_cases": len(rows),
        "by_family": dict(by_family),
        "by_attack_type": dict(by_type),
    }
