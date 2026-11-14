"""Tests for VEAP R1.3 separated reference custody and HMAC-bound submission receipts."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from r13.blinded_runner import run_blinded_evaluation
from r13.custody import (
    CustodySeparationError,
    CustodyVerificationError,
    assert_disjoint_custody_paths,
    issue_submission_receipt,
    load_external_scene_pack,
    verify_submission_receipt,
)
from r13.reference_scorer import ScoringIntegrityError, score_submission
from r13.study_schema import generate_r13_pilot_split
from veap_evidence.verdict import canonical_hash


class R13CustodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle, self.reference = generate_r13_pilot_split(n_scenes=5)
        self.submission = run_blinded_evaluation(self.bundle)
        self.key = "test-custodian-secret-signing-key-2026"

    def test_valid_hmac_receipt_verifies_and_scores(self) -> None:
        receipt = issue_submission_receipt(self.submission, self.bundle, self.key)
        verify_submission_receipt(self.submission, self.bundle, receipt, self.key)
        report = score_submission(
            self.bundle,
            self.submission,
            self.reference,
            receipt=receipt,
            custody_key=self.key,
            require_receipt=True,
        )
        self.assertTrue(report["custody_receipt_verified"])

    def test_wrong_custody_key_is_rejected(self) -> None:
        receipt = issue_submission_receipt(self.submission, self.bundle, self.key)
        with self.assertRaises(CustodyVerificationError):
            verify_submission_receipt(self.submission, self.bundle, receipt, "wrong-custodian-signing-key-0000")

    def test_short_custody_key_is_rejected(self) -> None:
        with self.assertRaises(CustodyVerificationError):
            issue_submission_receipt(self.submission, self.bundle, "short-key")

    def test_post_receipt_prediction_edit_even_if_rehashed_fails_receipt_check(self) -> None:
        receipt = issue_submission_receipt(self.submission, self.bundle, self.key)
        tampered = deepcopy(self.submission)
        first_cid = self.bundle["cases"][0]["case_id"]
        tampered["predictions_by_method"]["goal_only"][first_cid] = "VIOLATING"
        tampered.pop("submission_sha256", None)
        tampered["submission_sha256"] = canonical_hash(tampered)
        with self.assertRaises(ScoringIntegrityError):
            score_submission(
                self.bundle,
                tampered,
                self.reference,
                receipt=receipt,
                custody_key=self.key,
                require_receipt=True,
            )

    def test_missing_case_in_submission_inventory_is_rejected(self) -> None:
        incomplete = deepcopy(self.submission)
        first_cid = self.bundle["cases"][0]["case_id"]
        for m in incomplete["predictions_by_method"]:
            incomplete["predictions_by_method"][m].pop(first_cid, None)
        incomplete["veap_certificates"].pop(first_cid, None)
        incomplete.pop("submission_sha256", None)
        incomplete["submission_sha256"] = canonical_hash(incomplete)
        with self.assertRaises(CustodyVerificationError):
            issue_submission_receipt(incomplete, self.bundle, self.key)

    def test_nested_or_identical_custody_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "vault"
            nested.mkdir()
            with self.assertRaises(CustodySeparationError):
                assert_disjoint_custody_paths(root, root)
            with self.assertRaises(CustodySeparationError):
                assert_disjoint_custody_paths(root, nested)

    def test_external_scene_pack_loader_enforces_disjoint_directories(self) -> None:
        with tempfile.TemporaryDirectory() as ev_tmp, tempfile.TemporaryDirectory() as cu_tmp:
            ev_dir = Path(ev_tmp)
            cu_dir = Path(cu_tmp)
            (ev_dir / "evaluator_bundle.json").write_text(json.dumps(self.bundle), encoding="utf-8")
            (cu_dir / "sealed_reference.json").write_text(json.dumps(self.reference), encoding="utf-8")
            (cu_dir / "custody.key").write_text(self.key, encoding="utf-8")
            b, r, k = load_external_scene_pack(ev_dir, cu_dir)
            self.assertEqual(b["study_id"], self.bundle["study_id"])
            self.assertEqual(r["evaluator_bundle_sha256"], self.reference["evaluator_bundle_sha256"])
            self.assertEqual(k, self.key)


if __name__ == "__main__":
    unittest.main()
