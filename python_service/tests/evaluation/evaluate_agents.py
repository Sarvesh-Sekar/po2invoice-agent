"""Agent evaluation harness backed by MLflow.

Compares extracted/verified outputs against golden fixtures and logs metrics
(trace-level: parse fidelity, criteria classification) plus artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixtures() -> list[dict[str, Any]]:
    if not FIXTURES_DIR.exists():
        return []
    fixtures: list[dict[str, Any]] = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        fixtures.append(json.loads(path.read_text(encoding="utf-8")))
    return fixtures


def evaluate(
    *,
    fixture: dict[str, Any],
    extracted: dict[str, Any] | None = None,
    verified: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score a single fixture against produced extraction/verification output."""
    expected = fixture.get("expected_po") or {}
    actual = extracted or {}
    fields = [
        "po_number",
        "customer",
        "gst_no",
        "ship_to",
        "city",
        "state",
        "country",
        "zip",
        "address_1",
    ]
    matched = sum(1 for f in fields if str(expected.get(f, "")).strip() == str(actual.get(f, "")).strip())
    parse_fidelity = matched / len(fields) if fields else 0.0

    future: dict[str, Any] = {}
    try:
        import mlflow

        mlflow.set_tracking_uri(Path.cwd() / "mlruns")
        with mlflow.start_run(run_name=fixture.get("name", "unlabeled")):
            mlflow.log_metric("parse_fidelity", parse_fidelity)
            mlflow.log_param("fixture", fixture.get("name"))
            mlflow.log_dict(
                {"expected": expected, "actual": actual, "verified": verified or {}},
                artifact_file="evaluation.json",
            )
            future = {"mlflow_run": True}
    except ImportError:  # pragma: no cover - evaluation extra not installed
        future = {"mlflow_run": False}

    return {
        "fixture": fixture.get("name"),
        "parse_fidelity": round(parse_fidelity, 3),
        "criteria_classification": "BLOCKED" if verified and verified.get("has_blocking_issues") else "AUTO",
        **future,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate agents against golden fixtures")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N fixtures")
    args = parser.parse_args()

    fixtures = _load_fixtures()[: args.limit] if args.limit else _load_fixtures()
    if not fixtures:
        print("No fixtures found; create JSON files under tests/evaluation/fixtures/")
        return

    results = [evaluate(fixture=fixture) for fixture in fixtures]
    for row in results:
        print(json.dumps(row, indent=2))


if __name__ == "__main__":
    main()
