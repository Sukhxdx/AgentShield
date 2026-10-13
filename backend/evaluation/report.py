"""Write CSV and PNG charts for the baseline-versus-protected comparison.

Charts are labeled ToolEmu-style. They are not upstream ToolEmu results.

Run from the repo root::

    python -m backend.evaluation.report
"""

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from backend.config import get_settings


def _load() -> dict:
    settings = get_settings()
    path = Path(settings.results_dir) / "comparison.json"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run python -m backend.evaluation.run_comparison")
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(report: dict, destination: Path) -> None:
    """Write one row per case for the first seed."""
    fieldnames = [
        "case_id",
        "category",
        "expected_decision",
        "is_harmful",
        "protected_decision",
        "protected_executed",
        "baseline_harmful_execution",
        "protected_harmful_execution",
        "combined_risk",
        "rule_risk",
        "ml_risk",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["cases"])


def write_charts(report: dict, directory: Path) -> None:
    """Write grouped bar charts and a confusion-matrix heatmap."""
    baseline = report["modes"]["baseline"]
    protected = report["modes"]["protected"]
    labels = ["Unsafe execution", "Attack success", "Over-blocking"]
    keys = ["unsafe_action_execution_rate", "attack_success_rate", "over_blocking_rate"]
    base_values = [baseline[key] * 100 for key in keys]
    prot_values = [protected[key] * 100 for key in keys]
    positions = np.arange(len(labels))
    width = 0.36
    figure, axis = plt.subplots(figsize=(8.2, 4.6))
    axis.bar(positions - width / 2, base_values, width, label="Baseline", color="#9f1239")
    axis.bar(positions + width / 2, prot_values, width, label="AgentShield", color="#1f7a4d")
    axis.set_ylabel("Rate (%)")
    axis.set_xticks(positions, labels)
    axis.set_ylim(0, 100)
    axis.set_title("ToolEmu-style comparison: baseline vs AgentShield")
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(directory / "comparison_rates.png", dpi=140)
    plt.close(figure)

    matrix = np.array(report["confusion_matrix"]["matrix"], dtype=float)
    figure, axis = plt.subplots(figsize=(5.6, 4.8))
    image = axis.imshow(matrix, cmap="YlOrBr")
    axis.set_xticks(range(3), report["confusion_matrix"]["labels"], rotation=20, ha="right")
    axis.set_yticks(range(3), report["confusion_matrix"]["labels"])
    axis.set_xlabel("Actual")
    axis.set_ylabel("Expected")
    axis.set_title("Protected decisions")
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            axis.text(col, row, int(matrix[row, col]), ha="center", va="center")
    figure.colorbar(image, ax=axis, fraction=0.046)
    figure.tight_layout()
    figure.savefig(directory / "confusion_matrix.png", dpi=140)
    plt.close(figure)


def main() -> None:
    """Write comparison.csv and the PNG charts next to comparison.json."""
    settings = get_settings()
    directory = Path(settings.results_dir)
    report = _load()
    write_csv(report, directory / "comparison.csv")
    write_charts(report, directory)
    print(f"wrote {directory / 'comparison.csv'}")
    print(f"wrote {directory / 'comparison_rates.png'}")
    print(f"wrote {directory / 'confusion_matrix.png'}")


if __name__ == "__main__":
    main()
