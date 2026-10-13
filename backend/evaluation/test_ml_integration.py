"""Print ML scores for the named security scenarios.

Run from the repo root::

    python -m backend.evaluation.test_ml_integration
"""

from backend.agentshield.models import ProposedAction
from backend.config import get_settings
from backend.evaluation.test_cases import named_cases
from backend.runtime import build_runtime


def main() -> None:
    """Score each named case and print the governance decision."""
    runtime = build_runtime(get_settings())
    if not runtime.model.available:
        raise SystemExit("risk model is not available")
    for case in named_cases():
        result = runtime.service.evaluate(
            ProposedAction(tool=case.tool, arguments=case.arguments, reasoning="ml integration"),
            user_role=case.user_role,
            user_id="ml.integration",
            user_request=case.user_request,
            retrieved_context=case.retrieved_context,
        )
        print(
            f"{case.case_id}: decision={result.decision} rule={result.rule_risk.score} "
            f"ml={result.ml_risk:.2f} combined={result.combined_risk} "
            f"fallback={result.ml_fallback}"
        )


if __name__ == "__main__":
    main()
