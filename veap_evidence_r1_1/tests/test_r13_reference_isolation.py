"""Tests for VEAP R1.3 reference-label isolation and anti-leakage controls."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from r13.blinded_runner import ReferenceIsolationError, run_blinded_evaluation
from r13.reference_scorer import ScoringIntegrityError, score_submission
from r13.study_schema import (
    ReferenceLeakageError,
    SchemaValidationError,
    generate_r13_pilot_split,
    validate_evaluator_bundle,
)


class R13ReferenceIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle, self.reference = generate_r13_pilot_split(n_scenes=6)

    def test_clean_evaluator_bundle_contains_zero_reference_fields(self) -> None:
        validate_evaluator_bundle(self.bundle)
        raw = json.dumps(self.bundle)
        for forbidden in ("expected_verdict", "condition_code", "ground_truth", "oracle"):
            self.assertNotIn(forbidden, raw)

    def test_leaked_expected_verdict_in_case_fails_closed(self) -> None:
        bad = deepcopy(self.bundle)
        bad["cases"][0]["expected_verdict"] = "COMPLIANT"
        with self.assertRaises(ReferenceLeakageError):
            validate_evaluator_bundle(bad)

    def test_leaked_condition_in_nested_contract_fails_closed(self) -> None:
        bad = deepcopy(self.bundle)
        bad["cases"][0]["contract"]["ground_truth"] = "COMPLIANT"
        with self.assertRaises(ReferenceLeakageError):
            validate_evaluator_bundle(bad)

    def test_condition_revealing_case_id_fails_closed(self) -> None:
        bad = deepcopy(self.bundle)
        bad["cases"][0]["case_id"] = "scene-001-compliant-01"
        with self.assertRaises(ReferenceLeakageError):
            validate_evaluator_bundle(bad)

    def test_blinded_runner_rejects_reference_env_variable(self) -> None:
        with self.assertRaises(ReferenceIsolationError):
            run_blinded_evaluation(
                self.bundle,
                env={"VEAP_R13_REFERENCE_PATH": "/tmp/sealed_reference.json"},
            )

    def test_blinded_runner_rejects_workspace_containing_reference_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "sealed_reference.json").write_text(
                json.dumps(self.reference), encoding="utf-8"
            )
            with self.assertRaises(ReferenceIsolationError):
                run_blinded_evaluation(self.bundle, workspace_dir=ws)

    def test_scorer_rejects_tampered_frozen_submission(self) -> None:
        sub = run_blinded_evaluation(self.bundle)
        first_cid = self.bundle["cases"][0]["case_id"]
        sub["predictions_by_method"]["sampled_safety"][first_cid] = "INCONCLUSIVE"
        with self.assertRaises(ScoringIntegrityError):
            score_submission(self.bundle, sub, self.reference)

    def test_scorer_rejects_mismatched_reference_bundle_hash(self) -> None:
        sub = run_blinded_evaluation(self.bundle)
        bad_ref = deepcopy(self.reference)
        bad_ref["evaluator_bundle_sha256"] = "0" * 64
        with self.assertRaises(ScoringIntegrityError):
            score_submission(self.bundle, sub, bad_ref)


if __name__ == "__main__":
    unittest.main()
