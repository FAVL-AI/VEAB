"""Fail-closed, evidence-scoped *software release gate* for the VEAP monorepo.

This is not an external audit, safety validation, or production certification.
No network, robot access, or simulator hardware is required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


REQUIRED_PATHS = (
    "veap/__init__.py",
    "veap/m3_replay/core.py",
    "veap_evidence_r1_1/veap_evidence/verdict.py",
    "veap_evidence_r1_1/external_monitor/possible_worlds_checker.py",
    "veap_studio_r03/veap_studio/api.py",
    "veap_studio_r03/veap_studio/workers/isaac_fall.py",
    "veap_studio_r03/veap_studio/workers/mujoco_fall.py",
    ".github/workflows/ci.yml",
)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root: Path, r12_report: Path | None = None) -> dict:
    errors = []
    evidence = {}
    for path in REQUIRED_PATHS:
        candidate = root / path
        if not candidate.is_file():
            errors.append(f"Required component absent: {path}")
        else:
            evidence[path] = file_sha(candidate)
    readme = root / "README.md"
    if not readme.exists() or not readme.read_text(encoding="utf-8").startswith(
        "# VEAP — Verifiable Embodied Agent Platform"
    ):
        errors.append("README identity is stale or missing")
    stress_path = root / "veap_evidence_r1_1/artifacts/r1_identifiability/stress_report.json"
    if not stress_path.is_file():
        errors.append("R1.1 stress report is missing")
    else:
        evidence[str(stress_path.relative_to(root))] = file_sha(stress_path)
        try:
            report = json.loads(stress_path.read_text(encoding="utf-8"))
            counts = report["summary"]["correct_by_method"]
            if report["n_cases"] != 96 or counts["veap"] != 96 or counts["separate_monitor"] != 96:
                errors.append("R1.1 stress data do not match the declared reference regression")
            if report["upstream_EAI_reproduction"] != "NOT_RUN" or report["upstream_ABC_reproduction"] != "NOT_RUN":
                errors.append("R1.1 report unexpectedly upgrades upstream reproduction status")
            if not report["no_independent_scenes"] or not report["no_experimental_p_value_or_sota_claim"]:
                errors.append("R1.1 report omits mandatory validity limitations")
            if counts["veap"] != counts["separate_monitor"]:
                errors.append("Strong monitor null/tie result no longer preserved")
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(f"Invalid R1.1 report: {exc}")
    if r12_report is not None:
        try:
            z = json.loads(r12_report.read_text(encoding="utf-8"))
            evidence["runtime_r12_report"] = file_sha(r12_report)
            summary = z["summary"]
            if z["study_type"] != "AUTHOR_CONSTRUCTED_CORRELATED_SOFTWARE_STRESS":
                errors.append("R1.2 experimental scope altered")
            if z["independent_heldout_environments"] or z["physical_sensor_ground_truth"]:
                errors.append("R1.2 cannot claim held-out scenes or physical ground truth")
            if summary["n_cases"] != 180 or summary["n_fixtures"] != 15:
                errors.append("R1.2 fixture grid incomplete")
            if any(summary[key] for key in (
                "independent_monitor_disagreements",
                "certificate_checker_failures",
                "assumption_monotonicity_failures",
            )):
                errors.append("R1.2 software control failure")
        except (ValueError, KeyError, TypeError, OSError) as exc:
            errors.append(f"R1.2 report error: {exc}")
    else:
        errors.append("A freshly regenerated R1.2 report must be supplied")
    return {
        "schema": "veap.integrated.software-release-gate/1",
        "status": "PASS_SOFTWARE_ONLY" if not errors else "BLOCKED",
        "repository_scope": "source files present in the local checkout; native engine execution not inferred",
        "native_engine_production_acceptance": "NOT_ESTABLISHED",
        "real_robot_safety": "NOT_ESTABLISHED",
        "independent_external_ground_truth": "NOT_ESTABLISHED",
        "enterprise_security_qualification": "NOT_ESTABLISHED",
        "github_ci": "checked separately; not inferred by this script",
        "tracked_evidence_sha256": evidence,
        "errors": errors,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--r12-report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    opts = p.parse_args()
    result = audit(opts.root.resolve(), opts.r12_report.resolve())
    opts.out.parent.mkdir(parents=True, exist_ok=True)
    opts.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "errors": result["errors"]}, indent=2))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
