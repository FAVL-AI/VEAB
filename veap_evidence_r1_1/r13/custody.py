"""VEAP R1.3 separated reference custody, HMAC submission receipts, and external scene-pack loader.

Provides cryptographic and path-level separation between:
1. Evaluator execution workspace (observations + contracts only; no reference labels or keys).
2. Custodian vault (reference labels + HMAC signing key).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from veap_evidence.verdict import canonical, canonical_hash
from .split_integrity import audit_split_integrity
from .study_schema import (
    SUBMISSION_SCHEMA,
    validate_evaluator_bundle,
    validate_sealed_reference,
)

RECEIPT_SCHEMA = "veap.r13.submission_receipt/1"


class CustodySeparationError(RuntimeError):
    """Raised when evaluator and custodian paths or permissions overlap."""


class CustodyVerificationError(ValueError):
    """Raised when a submission receipt or HMAC signature fails verification."""


def assert_disjoint_custody_paths(evaluator_dir: Path, custodian_dir: Path) -> None:
    """Fail closed if evaluator workspace and custodian vault share or nest paths."""
    ev_real = evaluator_dir.resolve()
    cu_real = custodian_dir.resolve()
    if ev_real == cu_real:
        raise CustodySeparationError("Evaluator directory and custodian directory must be distinct")
    if ev_real in cu_real.parents or cu_real in ev_real.parents:
        raise CustodySeparationError("Evaluator directory and custodian vault must not be nested")


def _case_inventory_sha256(case_ids: list[str] | set[str]) -> str:
    return canonical_hash(sorted(str(c) for c in case_ids))


def _submission_predictions_inventory(submission: dict[str, Any]) -> set[str]:
    preds_by_method = submission.get("predictions_by_method", {})
    if not isinstance(preds_by_method, dict) or not preds_by_method:
        raise CustodyVerificationError("Submission contains no method predictions")
    inventories = [set(m_preds.keys()) for m_preds in preds_by_method.values() if isinstance(m_preds, dict)]
    if not inventories:
        raise CustodyVerificationError("Submission method predictions are malformed")
    first = inventories[0]
    if any(inv != first for inv in inventories[1:]):
        raise CustodyVerificationError("Inconsistent case_id inventory across methods in submission")
    cert_ids = set(submission.get("veap_certificates", {}).keys())
    if cert_ids != first:
        raise CustodyVerificationError("VEAP certificate case_id inventory does not match predictions")
    return first


def issue_submission_receipt(
    submission: dict[str, Any],
    evaluator_bundle: dict[str, Any],
    custody_key: str,
) -> dict[str, Any]:
    """Issue an HMAC-SHA256 receipt binding a frozen submission to an evaluator bundle."""
    if not isinstance(custody_key, str) or len(custody_key.strip()) < 16:
        raise CustodyVerificationError("Custody signing key must be at least 16 characters")
    validate_evaluator_bundle(evaluator_bundle)
    if not isinstance(submission, dict) or submission.get("schema") != SUBMISSION_SCHEMA:
        raise CustodyVerificationError(f"Expected submission schema {SUBMISSION_SCHEMA}")

    sub_copy = dict(submission)
    declared_sub_sha = sub_copy.pop("submission_sha256", None)
    if not declared_sub_sha or canonical_hash(sub_copy) != declared_sub_sha:
        raise CustodyVerificationError("Submission self-digest is invalid or missing")

    bundle_sha = canonical_hash(evaluator_bundle)
    if submission.get("evaluator_bundle_sha256") != bundle_sha:
        raise CustodyVerificationError("Submission evaluator_bundle_sha256 mismatch")

    expected_cases = {item["case_id"] for item in evaluator_bundle["cases"]}
    submitted_cases = _submission_predictions_inventory(submission)
    if submitted_cases != expected_cases:
        raise CustodyVerificationError("Submission case inventory does not match evaluator bundle")

    inv_sha = _case_inventory_sha256(expected_cases)
    body = {
        "schema": RECEIPT_SCHEMA,
        "study_id": evaluator_bundle["study_id"],
        "evaluator_bundle_sha256": bundle_sha,
        "submission_sha256": declared_sub_sha,
        "case_inventory_sha256": inv_sha,
        "n_cases": len(expected_cases),
        "algorithm": "HMAC-SHA256",
    }
    mac = hmac.new(custody_key.encode("utf-8"), canonical(body), hashlib.sha256).hexdigest()
    return {**body, "hmac_sha256": mac}


def verify_submission_receipt(
    submission: dict[str, Any],
    evaluator_bundle: dict[str, Any],
    receipt: dict[str, Any],
    custody_key: str,
) -> None:
    """Verify an HMAC-SHA256 submission receipt against the submission and evaluator bundle."""
    if not isinstance(receipt, dict) or receipt.get("schema") != RECEIPT_SCHEMA:
        raise CustodyVerificationError(f"Expected receipt schema {RECEIPT_SCHEMA}")
    expected = issue_submission_receipt(submission, evaluator_bundle, custody_key)
    provided_mac = str(receipt.get("hmac_sha256", ""))
    if not hmac.compare_digest(provided_mac, expected["hmac_sha256"]):
        raise CustodyVerificationError("Receipt HMAC-SHA256 verification failed")
    for k in ("study_id", "evaluator_bundle_sha256", "submission_sha256", "case_inventory_sha256", "n_cases"):
        if receipt.get(k) != expected[k]:
            raise CustodyVerificationError(f"Receipt field mismatch: {k}")


def load_external_scene_pack(
    evaluator_dir: Path,
    custodian_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Load an externally authored scene pack from disjoint evaluator and custodian directories."""
    assert_disjoint_custody_paths(evaluator_dir, custodian_dir)
    bundle_path = evaluator_dir / "evaluator_bundle.json"
    ref_path = custodian_dir / "sealed_reference.json"
    key_path = custodian_dir / "custody.key"

    if not bundle_path.is_file():
        raise FileNotFoundError(f"Missing evaluator_bundle.json in {evaluator_dir}")
    if not ref_path.is_file() or not key_path.is_file():
        raise FileNotFoundError(f"Missing sealed_reference.json or custody.key in {custodian_dir}")

    # Ensure no custodian files exist in evaluator_dir
    for p in evaluator_dir.iterdir():
        if p.name in ("sealed_reference.json", "custody.key"):
            raise CustodySeparationError(f"Custodian artifact {p.name} leaked into evaluator directory")

    evaluator_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    sealed_reference = json.loads(ref_path.read_text(encoding="utf-8"))
    custody_key = key_path.read_text(encoding="utf-8").strip()

    validate_evaluator_bundle(evaluator_bundle)
    audit_split_integrity(evaluator_bundle)
    validate_sealed_reference(sealed_reference, evaluator_bundle)
    return evaluator_bundle, sealed_reference, custody_key
