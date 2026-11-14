"""VEAP R1.3 30-scene x 4-condition sealed evaluation pilot runner.

Executes the blinded evaluator runner in an isolated temporary directory disjoint
from the custodian vault, issues an HMAC-SHA256 submission receipt before accessing
reference labels, and scores the frozen submission with require_receipt=True.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from r13.blinded_runner import run_blinded_evaluation
from r13.custody import issue_submission_receipt, load_external_scene_pack
from r13.reference_scorer import score_submission
from r13.study_schema import generate_r13_pilot_split

PILOT_CUSTODY_KEY = "veap-r13-pilot-local-custodian-hmac-key-2026"


def run_pilot(n_scenes: int = 30) -> dict:
    raw_bundle, raw_ref = generate_r13_pilot_split(n_scenes=n_scenes)
    with tempfile.TemporaryDirectory() as ev_tmp, tempfile.TemporaryDirectory() as cu_tmp:
        ev_dir = Path(ev_tmp)
        cu_dir = Path(cu_tmp)
        (ev_dir / "evaluator_bundle.json").write_text(
            json.dumps(raw_bundle, sort_keys=True), encoding="utf-8"
        )
        (cu_dir / "sealed_reference.json").write_text(
            json.dumps(raw_ref, sort_keys=True), encoding="utf-8"
        )
        (cu_dir / "custody.key").write_text(PILOT_CUSTODY_KEY, encoding="utf-8")

        evaluator_bundle, sealed_reference, custody_key = load_external_scene_pack(ev_dir, cu_dir)
        submission = run_blinded_evaluation(evaluator_bundle, workspace_dir=ev_dir)
        receipt = issue_submission_receipt(submission, evaluator_bundle, custody_key)
    return score_submission(
        evaluator_bundle,
        submission,
        sealed_reference,
        receipt=receipt,
        custody_key=custody_key,
        require_receipt=True,
    )


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
                "custody_receipt_verified": report["custody_receipt_verified"],
                "strong_monitor_tie": report["strong_monitor_verdict_tie_preserved"],
            },
            sort_keys=True,
        )
    )
    if not all(report["kpi_gate"].values()) or not report["custody_receipt_verified"]:
        raise SystemExit("R1.3 KPI or custody gate FAILED")


if __name__ == "__main__":
    main()
