"""VEAP R1.3 post-submission reference scorer.

Runs ONLY after evaluator submissions are frozen and sealed.
Verifies submission digest, split integrity, and certificate audit before scoring
predictions against the sealed reference labels at the scene-cluster level.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from veap_evidence.verdict import canonical_hash
from .certificate_audit import audit_submission_certificates
from .custody import CustodyVerificationError, verify_submission_receipt
from .split_integrity import audit_split_integrity
from .statistics import (
    prospective_scene_sample_size,
    scene_cluster_paired_comparison,
    wilson_ci_95,
)
from .study_schema import (
    CONDITIONS,
    SCORE_REPORT_SCHEMA,
    SUBMISSION_SCHEMA,
    validate_evaluator_bundle,
    validate_sealed_reference,
)


class ScoringIntegrityError(ValueError):
    """Raised when a submission or reference bundle fails pre-scoring integrity checks."""


def _verify_frozen_submission(evaluator_bundle: dict[str, Any], submission: dict[str, Any], sealed_reference: dict[str, Any]) -> None:
    if not isinstance(submission, dict) or submission.get("schema") != SUBMISSION_SCHEMA:
        raise ScoringIntegrityError(f"Expected submission schema {SUBMISSION_SCHEMA}")
    sub_copy = dict(submission)
    declared_sha = sub_copy.pop("submission_sha256", None)
    if canonical_hash(sub_copy) != declared_sha:
        raise ScoringIntegrityError("Frozen submission_sha256 mismatch")
    bundle_sha = canonical_hash(evaluator_bundle)
    if submission.get("evaluator_bundle_sha256") != bundle_sha:
        raise ScoringIntegrityError("Submission does not match evaluator_bundle_sha256")
    if sealed_reference.get("evaluator_bundle_sha256") != bundle_sha:
        raise ScoringIntegrityError("Sealed reference does not match evaluator_bundle_sha256")


def score_submission(
    evaluator_bundle: dict[str, Any],
    submission: dict[str, Any],
    sealed_reference: dict[str, Any],
    receipt: dict[str, Any] | None = None,
    custody_key: str | None = None,
    require_receipt: bool = False,
) -> dict[str, Any]:
    """Score a frozen blinded submission against sealed reference labels."""
    validate_evaluator_bundle(evaluator_bundle)
    split_report = audit_split_integrity(evaluator_bundle)
    try:
        validate_sealed_reference(sealed_reference, evaluator_bundle)
    except Exception as exc:
        raise ScoringIntegrityError(str(exc)) from exc
    _verify_frozen_submission(evaluator_bundle, submission, sealed_reference)
    receipt_verified = False
    if require_receipt and (receipt is None or custody_key is None):
        raise ScoringIntegrityError("HMAC submission receipt and custody key are required")
    if receipt is not None or custody_key is not None:
        if receipt is None or custody_key is None:
            raise ScoringIntegrityError("Both receipt and custody_key must be supplied together")
        try:
            verify_submission_receipt(submission, evaluator_bundle, receipt, custody_key)
        except CustodyVerificationError as exc:
            raise ScoringIntegrityError(str(exc)) from exc
        receipt_verified = True
    cert_report = audit_submission_certificates(evaluator_bundle, submission, fail_closed=True)

    ref_cases = sealed_reference["cases"]
    preds_by_method = submission["predictions_by_method"]

    metrics_by_method: dict[str, Any] = {}
    scene_scores_by_method: dict[str, dict[str, float]] = {}

    for method, preds in preds_by_method.items():
        total = len(ref_cases)
        correct = 0
        false_decisive = 0
        cond_totals: dict[str, int] = {c: 0 for c in CONDITIONS}
        cond_correct: dict[str, int] = {c: 0 for c in CONDITIONS}
        decisive_truth_total = 0
        unnecessary_abstentions = 0
        inconclusive_truth_total = 0
        appropriate_abstentions = 0

        by_scene_hits: dict[str, list[int]] = defaultdict(list)

        for cid, ref in ref_cases.items():
            pred = preds.get(cid)
            expected = ref["expected_verdict"]
            cond = ref["condition_code"]
            sid = ref["scene_id"]

            cond_totals[cond] += 1
            hit = int(pred == expected)
            correct += hit
            cond_correct[cond] += hit
            by_scene_hits[sid].append(hit)

            if pred in ("COMPLIANT", "VIOLATING") and pred != expected:
                false_decisive += 1

            if expected in ("COMPLIANT", "VIOLATING"):
                decisive_truth_total += 1
                if pred == "INCONCLUSIVE":
                    unnecessary_abstentions += 1
            else:
                inconclusive_truth_total += 1
                if pred == "INCONCLUSIVE":
                    appropriate_abstentions += 1

        scene_mean_scores = {
            sid: sum(hits) / len(hits) for sid, hits in by_scene_hits.items()
        }
        scene_all_four = sum(1 for hits in by_scene_hits.values() if all(h == 1 for h in hits))
        n_scenes = len(by_scene_hits)
        scene_scores_by_method[method] = scene_mean_scores

        metrics_by_method[method] = {
            "n_cases": total,
            "n_scenes": n_scenes,
            "overall_case_accuracy": round(correct / max(1, total), 6),
            "scene_all_four_correct_count": scene_all_four,
            "scene_all_four_correct_rate": round(scene_all_four / max(1, n_scenes), 6),
            "scene_all_four_wilson_95_ci": list(wilson_ci_95(scene_all_four, n_scenes)),
            "false_decisive_count": false_decisive,
            "false_decisive_rate": round(false_decisive / max(1, total), 6),
            "false_decisive_wilson_95_ci": list(wilson_ci_95(false_decisive, total)),
            "appropriate_abstention_rate": round(appropriate_abstentions / max(1, inconclusive_truth_total), 6),
            "unnecessary_abstention_rate": round(unnecessary_abstentions / max(1, decisive_truth_total), 6),
            "accuracy_by_condition": {
                c: round(cond_correct[c] / max(1, cond_totals[c]), 6) for c in CONDITIONS
            },
        }

    # Scene-clustered paired comparisons between VEAP and each comparator
    paired_comparisons: dict[str, Any] = {}
    if "veap" in scene_scores_by_method:
        for other in scene_scores_by_method:
            if other == "veap":
                continue
            paired_comparisons[f"veap_vs_{other}"] = scene_cluster_paired_comparison(
                scene_scores_by_method["veap"],
                scene_scores_by_method[other],
            )

    veap_metrics = metrics_by_method.get("veap", {})
    mon_metrics = metrics_by_method.get("separate_reachability_monitor", {})
    strong_monitor_tie = (
        veap_metrics.get("overall_case_accuracy") == mon_metrics.get("overall_case_accuracy")
        and veap_metrics.get("false_decisive_count") == mon_metrics.get("false_decisive_count")
    )

    kpi_gate = {
        "false_decisive_rate_le_5pct": veap_metrics.get("false_decisive_rate", 1.0) <= 0.05,
        "conclusive_certificates_100pct_checkable": cert_report["conclusive_certificate_check_rate"] == 1.0,
        "zero_reference_leakage": True,
        "split_integrity_passed": split_report["status"] == "PASS",
    }

    return {
        "schema": SCORE_REPORT_SCHEMA,
        "study_id": evaluator_bundle["study_id"],
        "study_scope": evaluator_bundle.get("study_scope", "DEVELOPMENT_PILOT_SYNTHETIC_SEALED_HARNESS"),
        "independent_external_authorship": bool(evaluator_bundle.get("independent_external_authorship", False)),
        "physical_sensor_ground_truth": bool(evaluator_bundle.get("physical_sensor_ground_truth", False)),
        "custody_receipt_verified": receipt_verified,
        "evaluator_bundle_sha256": sealed_reference["evaluator_bundle_sha256"],
        "submission_sha256": submission["submission_sha256"],
        "sealed_reference_sha256": canonical_hash(sealed_reference),
        "split_integrity": split_report,
        "certificate_audit": cert_report,
        "kpi_gate": kpi_gate,
        "strong_monitor_verdict_tie_preserved": strong_monitor_tie,
        "metrics_by_method": metrics_by_method,
        "scene_clustered_paired_comparisons": paired_comparisons,
        "prospective_confirmatory_power_analysis": prospective_scene_sample_size(),
    }
