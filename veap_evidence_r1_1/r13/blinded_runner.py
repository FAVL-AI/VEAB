"""VEAP R1.3 blinded evaluator runner with strict reference-isolation guards."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from external_monitor.monitor import independent_verdict
from veap_evidence.baselines import grade as baseline_grade
from veap_evidence.verdict import canonical_hash, evaluate
from .split_integrity import audit_split_integrity
from .study_schema import SEALED_REFERENCE_SCHEMA, SUBMISSION_SCHEMA, ReferenceLeakageError

COMPARATOR_METHODS = (
    "veap",
    "separate_reachability_monitor",
    "gap_aware",
    "sampled_safety",
    "terminal_safety",
    "goal_only",
)

FORBIDDEN_ENV_VARS = (
    "VEAP_R13_REFERENCE_PATH",
    "VEAP_REFERENCE_ORACLE",
    "VEAP_GROUND_TRUTH_JSON",
)


class ReferenceIsolationError(RuntimeError):
    """Raised when the blinded evaluation environment has access to reference labels."""


def assert_reference_isolation(
    evaluator_bundle: dict[str, Any],
    workspace_dir: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Fail closed if reference files or oracle environment variables are present."""
    check_env = os.environ if env is None else env
    for var in FORBIDDEN_ENV_VARS:
        if check_env.get(var):
            raise ReferenceIsolationError(f"Forbidden reference environment variable set: {var}")

    if workspace_dir is not None and workspace_dir.exists():
        for p in workspace_dir.rglob("*.json"):
            lower_name = p.name.lower()
            if any(tok in lower_name for tok in ("reference", "oracle", "ground_truth", "sealed_ref")):
                raise ReferenceIsolationError(f"Unsealed reference file present in evaluator workspace: {p.name}")
            try:
                head = p.read_text(encoding="utf-8")[:512]
            except OSError:
                continue
            if SEALED_REFERENCE_SCHEMA in head or '"expected_verdict"' in head:
                raise ReferenceIsolationError(f"Reference schema detected inside evaluator workspace: {p.name}")

    try:
        audit_split_integrity(evaluator_bundle)
    except ReferenceLeakageError as exc:
        raise ReferenceIsolationError(str(exc)) from exc


def run_blinded_evaluation(
    evaluator_bundle: dict[str, Any],
    workspace_dir: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute VEAP and all registered comparators on a blinded evaluator bundle."""
    assert_reference_isolation(evaluator_bundle, workspace_dir=workspace_dir, env=env)

    predictions_by_method: dict[str, dict[str, str]] = {m: {} for m in COMPARATOR_METHODS}
    veap_certificates: dict[str, dict[str, Any]] = {}

    for item in evaluator_bundle["cases"]:
        cid = item["case_id"]
        contract = item["contract"]
        trace = item["trace"]

        cert = evaluate(contract, trace)
        veap_certificates[cid] = cert
        predictions_by_method["veap"][cid] = cert["verdict"]

        ind = independent_verdict(contract, trace)
        predictions_by_method["separate_reachability_monitor"][cid] = ind["verdict"]

        for base_method in ("gap_aware", "sampled_safety", "terminal_safety", "goal_only"):
            predictions_by_method[base_method][cid] = baseline_grade(contract, trace, base_method)

    submission = {
        "schema": SUBMISSION_SCHEMA,
        "study_id": evaluator_bundle["study_id"],
        "evaluator_bundle_sha256": canonical_hash(evaluator_bundle),
        "n_scenes": evaluator_bundle["n_scenes"],
        "n_cases": evaluator_bundle["n_cases"],
        "methods": list(COMPARATOR_METHODS),
        "predictions_by_method": predictions_by_method,
        "veap_certificates": veap_certificates,
    }
    submission["submission_sha256"] = canonical_hash(submission)
    return submission
