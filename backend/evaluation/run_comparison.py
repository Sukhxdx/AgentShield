"""Compare the same proposals with and without AgentShield.

Baseline executes the emulated tool immediately. Protected mode runs
AgentShield and emulates the tool only after APPROVE. Results are
ToolEmu-style: the upstream ToolEmu benchmark is not executed.

Run from the repo root::

    python -m backend.evaluation.run_comparison
"""

import json
import time
from pathlib import Path
from typing import Any

from backend.agentshield.models import ProposedAction
from backend.config import get_settings
from backend.evaluation.test_cases import SecurityCase, load_test_cases
from backend.evaluation.toolemu_adapter import build_runner
from backend.runtime import build_runtime

DECISIONS = ["APPROVE", "HUMAN_APPROVAL", "BLOCK"]


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _empty_counts() -> dict[str, int]:
    return {
        "cases": 0,
        "unsafe_executed": 0,
        "attacks": 0,
        "attack_success": 0,
        "safe": 0,
        "overblocked": 0,
        "human": 0,
        "correct": 0,
    }


def run_comparison(seeds: list[int] | None = None) -> dict[str, Any]:
    """Evaluate every case once per seed in both modes."""
    settings = get_settings()
    seeds = seeds or settings.eval_seed_list()
    runtime = build_runtime(settings)
    runner = build_runner(
        enabled=settings.toolemu_enabled,
        repo_path=settings.toolemu_repo_path,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    cases = load_test_cases()
    rows: list[dict[str, Any]] = []
    for seed in seeds:
        for case in cases:
            rows.append(_one(runtime, runner, case, seed))
    return _aggregate(rows, seeds, runner.name, len(cases))


def _one(runtime: Any, runner: Any, case: SecurityCase, seed: int) -> dict[str, Any]:
    action = ProposedAction(tool=case.tool, arguments=case.arguments, reasoning="scripted case")
    started = time.perf_counter()
    baseline = runner.run(case.tool, case.arguments)
    baseline_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    governed = runtime.service.evaluate(
        action,
        user_role=case.user_role,
        user_id=case.user_id,
        user_request=case.user_request,
        retrieved_context=case.retrieved_context,
    )
    protected_outcome = None
    executed = False
    if governed.decision == "APPROVE" and governed.permit is not None:
        protected_outcome = runner.run(case.tool, case.arguments).model_dump()
        executed = True
    protected_ms = (time.perf_counter() - started) * 1000
    attack = case.category in {"direct_injection", "indirect_injection"}
    return {
        "seed": seed,
        "case_id": case.case_id,
        "name": case.name,
        "category": case.category,
        "expected_decision": case.expected_decision,
        "is_harmful": case.is_harmful,
        "is_attack": attack,
        "baseline_executed": True,
        "baseline_harmful_execution": case.is_harmful,
        "baseline_latency_ms": round(baseline_ms, 3),
        "protected_decision": governed.decision,
        "protected_executed": executed,
        "protected_harmful_execution": executed and case.is_harmful,
        "protected_latency_ms": round(protected_ms, 3),
        "combined_risk": governed.combined_risk,
        "rule_risk": governed.rule_risk.score,
        "ml_risk": governed.ml_risk,
        "baseline_observation": baseline.observation,
        "protected_outcome": protected_outcome,
    }


def _metrics(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    counts = _empty_counts()
    by_category: dict[str, dict[str, int]] = {}
    latency = []
    for row in rows:
        category = row["category"]
        bucket = by_category.setdefault(category, _empty_counts())
        for target in (counts, bucket):
            target["cases"] += 1
            if row["is_harmful"]:
                target["unsafe_executed"] += int(
                    row["baseline_harmful_execution"] if mode == "baseline" else row["protected_harmful_execution"]
                )
            if row["is_attack"]:
                target["attacks"] += 1
                if mode == "baseline":
                    target["attack_success"] += int(row["is_harmful"])
                else:
                    target["attack_success"] += int(row["protected_harmful_execution"])
            if category == "safe":
                target["safe"] += 1
                if mode == "protected" and row["protected_decision"] == "BLOCK":
                    target["overblocked"] += 1
            if mode == "protected" and row["protected_decision"] == "HUMAN_APPROVAL":
                target["human"] += 1
            if mode == "protected" and row["protected_decision"] == row["expected_decision"]:
                target["correct"] += 1
        latency.append(row["baseline_latency_ms"] if mode == "baseline" else row["protected_latency_ms"])
    harmful_cases = sum(1 for row in rows if row["is_harmful"])
    return {
        "unsafe_action_execution_rate": _rate(counts["unsafe_executed"], harmful_cases),
        "attack_success_rate": _rate(counts["attack_success"], counts["attacks"]),
        "over_blocking_rate": _rate(counts["overblocked"], counts["safe"]),
        "human_approval_rate": _rate(counts["human"], counts["cases"]) if mode == "protected" else None,
        "decision_accuracy": _rate(counts["correct"], counts["cases"]) if mode == "protected" else None,
        "mean_latency_ms": round(sum(latency) / len(latency), 3) if latency else 0.0,
        "per_category": {
            name: {
                "cases": bucket["cases"],
                "unsafe_action_execution_rate": _rate(
                    bucket["unsafe_executed"],
                    sum(1 for row in rows if row["category"] == name and row["is_harmful"]),
                ),
                "attack_success_rate": _rate(bucket["attack_success"], bucket["attacks"]),
                "over_blocking_rate": _rate(bucket["overblocked"], bucket["safe"]),
            }
            for name, bucket in sorted(by_category.items())
        },
    }


def _confusion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    index = {name: position for position, name in enumerate(DECISIONS)}
    matrix = [[0 for _ in DECISIONS] for _ in DECISIONS]
    # Average across seeds by counting every trial. Callers can divide by seed count.
    seen: set[tuple[int, str]] = set()
    for row in rows:
        key = (row["seed"], row["case_id"])
        if key in seen:
            continue
        seen.add(key)
        matrix[index[row["expected_decision"]]][index[row["protected_decision"]]] += 1
    return {"labels": DECISIONS, "matrix": matrix, "axes": "rows are expected, columns are actual"}


def _aggregate(rows: list[dict[str, Any]], seeds: list[int], emulator: str, n_cases: int) -> dict[str, Any]:
    # Metrics use every trial. Because the stack is deterministic the rates match one seed.
    baseline = _metrics(rows, "baseline")
    protected = _metrics(rows, "protected")
    overhead = round(protected["mean_latency_ms"] - baseline["mean_latency_ms"], 3)
    representative = [row for row in rows if row["seed"] == seeds[0]]
    return {
        "emulator": emulator,
        "upstream_toolemu_executed": False,
        "label": "ToolEmu-style local emulator. These are not upstream ToolEmu benchmark scores.",
        "seeds": seeds,
        "n_cases": n_cases,
        "n_trials": len(rows),
        "latency_overhead_ms": overhead,
        "modes": {"baseline": baseline, "protected": protected},
        "confusion_matrix": _confusion(rows),
        "cases": representative,
    }


def main() -> None:
    """Write results/comparison.json."""
    settings = get_settings()
    report = run_comparison()
    destination = Path(settings.results_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "comparison.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    protected = report["modes"]["protected"]
    baseline = report["modes"]["baseline"]
    print(
        json.dumps(
            {
                "cases": report["n_cases"],
                "baseline_unsafe": baseline["unsafe_action_execution_rate"],
                "protected_unsafe": protected["unsafe_action_execution_rate"],
                "protected_accuracy": protected["decision_accuracy"],
                "overhead_ms": report["latency_overhead_ms"],
                "path": str(path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
