"""VEAP R1.3 30-scene x 4-condition sealed evaluation pilot runner.

Executes the blinded evaluator runner in an isolated temporary directory that
never contains the sealed reference labels, then scores the frozen submission.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from r13.blinded_runner import run_blinded_evaluation
from r13.reference_scorer import score_submission
from r13.study_schema import generate_r13_pilot_split


def run_pilot(n_scenes: int = 30) -> dict:
    evaluator_bundle, sealed_reference = generate_r13_pilot_split(n_scenes=n_scenes)
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws = Path(tmp_dir)
        (ws / "evaluator_inputs.json").write_text(
            json.dumps(evaluator_bundle, sort_keys=True), encoding="utf-8"
        )
        submission = run_blinded_evaluation(evaluator_bundle, workspace_dir=ws)
    return score_submission(evaluator_bundle, submission, sealed_reference)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", type=int, default=30)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = run_pilot(n_scenes=args.scenes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    veap_summary = report["metrics_by_method"]["veap"]
    print(
        json.dumps(
            {
                "n_scenes": veap_summary["n_scenes"],
                "n_cases": veap_summary["n_cases"],
                "veap_accuracy": veap_summary["overall_case_accuracy"],
                "false_decisive_rate": veap_summary["false_decisive_rate"],
                "certificate_check_rate": report["certificate_audit"]["conclusive_certificate_check_rate"],
                "strong_monitor_tie": report["strong_monitor_verdict_tie_preserved"],
            },
            sort_keys=True,
        )
    )
    if not all(report["kpi_gate"].values()):
        raise SystemExit("R1.3 KPI gate FAILED")


if __name__ == "__main__":
    main()
