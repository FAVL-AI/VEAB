"""VEAP R1.2 conditional-evidence stress, NOT a held-out or physical study.

15 author-coded trace fixtures x 4 declared speed bounds x 3 pose-error
bounds. This experiment tests whether widening the physically admissible
set weakens knowledge conservatively. 180 correlated tests != 180 scenes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from veap_evidence.fixtures import cases
from veap_evidence.verdict import evaluate
from external_monitor.monitor import independent_verdict, inspect

SPEED_SCALES = (1.0, 1.25, 1.5, 2.0)
POSE_ERRORS_M = (0.0, 0.02, 0.06)
DECISIVE = frozenset(("COMPLIANT", "VIOLATING"))


def run():
    results = []
    mismatches = []
    failed_checks = []
    monotonicity_failures = []
    records = cases()
    by_case = {}
    for case_id in sorted(records):
        record = records[case_id]
        for scale in SPEED_SCALES:
            for error in POSE_ERRORS_M:
                contract = deepcopy(record["contract"])
                contract["max_speed_mps"] = float(contract["max_speed_mps"] * scale)
                contract["position_uncertainty_m"] = error
                certificate = evaluate(contract, record["trace"])
                independent = independent_verdict(contract, record["trace"])
                checked = inspect(contract, record["trace"], certificate)
                label = f"{case_id}:speed={scale}:pose_error={error}"
                verdict = certificate["verdict"]
                if verdict != independent["verdict"]:
                    mismatches.append(label)
                if checked["certificate_check"] != "PASS":
                    failed_checks.append(label)
                if certificate.get("source_authenticity") != "UNATTESTED":
                    failed_checks.append(label + ":unexpected_authenticity")
                results.append({
                    "case_id": case_id,
                    "speed_multiplier": scale,
                    "position_uncertainty_m": error,
                    "verdict": verdict,
                    "independent_verdict": independent["verdict"],
                    "certificate_check": checked["certificate_check"],
                    "certificate_sha256": certificate["certificate_sha256"],
                    "source_authenticity": certificate["source_authenticity"],
                })
                by_case[(case_id, scale, error)] = verdict
    # Widening a valid uncertainty envelope cannot introduce a new decisive
    # claim from an inconclusive one. Applicable to internally consistent,
    # pinned-author fixtures only; the experiment explicitly checks this.
    for case_id in sorted(records):
        for i, speed_low in enumerate(SPEED_SCALES):
            for speed_high in SPEED_SCALES[i+1:]:
                for error in POSE_ERRORS_M:
                    lower = by_case[(case_id, speed_low, error)]
                    upper = by_case[(case_id, speed_high, error)]
                    if lower == "INCONCLUSIVE" and upper in DECISIVE:
                        monotonicity_failures.append(f"{case_id}:speed:{speed_low}->{speed_high}@{error}")
        for scale in SPEED_SCALES:
            for i, error_low in enumerate(POSE_ERRORS_M):
                for error_high in POSE_ERRORS_M[i+1:]:
                    lower = by_case[(case_id, scale, error_low)]
                    upper = by_case[(case_id, scale, error_high)]
                    if lower == "INCONCLUSIVE" and upper in DECISIVE:
                        monotonicity_failures.append(f"{case_id}:pose_error:{error_low}->{error_high}@{scale}")
    summary = {
        "n_fixtures": len(records),
        "n_cases": len(results),
        "verdict_counts": dict(Counter(x["verdict"] for x in results)),
        "independent_monitor_disagreements": len(mismatches),
        "certificate_checker_failures": len(failed_checks),
        "assumption_monotonicity_failures": len(monotonicity_failures),
    }
    return {
        "schema": "veap.r1.assumption-sensitivity/1",
        "study_type": "AUTHOR_CONSTRUCTED_CORRELATED_SOFTWARE_STRESS",
        "independent_heldout_environments": False,
        "physical_sensor_ground_truth": False,
        "source_authenticity": "UNATTESTED",
        "limitations": [
            "Shared stated kinematics, clocks, frames, and error bounds are not physically calibrated.",
            "A separate checker is implementation-independent, not organisationally independent.",
            "Fixtures are authored by the development team, not independent held-out scenes.",
            "No statistical superiority, certification or sim-to-real claim follows from these cases.",
        ],
        "parameters": {"speed_multipliers": list(SPEED_SCALES), "position_uncertainties_m": list(POSE_ERRORS_M)},
        "summary": summary,
        "failures": {"monitor_mismatches": mismatches,
                     "certificate_failures": failed_checks,
                     "monotonicity_failures": monotonicity_failures},
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    if any(report["failures"].values()):
        raise SystemExit("R1.2 stress gate FAILED: inspect report")


if __name__ == "__main__":
    main()
