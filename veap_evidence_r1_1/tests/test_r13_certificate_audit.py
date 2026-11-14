"""Tests for VEAP R1.3 independent certificate auditing and citation verification."""
from __future__ import annotations

from copy import deepcopy
import unittest

from r13.blinded_runner import run_blinded_evaluation
from r13.certificate_audit import (
    CertificateAuditError,
    audit_single_certificate,
    audit_submission_certificates,
)
from r13.study_schema import generate_r13_pilot_split
from veap_evidence.verdict import canonical_hash


class R13CertificateAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle, _ = generate_r13_pilot_split(n_scenes=5)
        self.submission = run_blinded_evaluation(self.bundle)

    def test_all_pilot_certificates_pass_independent_audit(self) -> None:
        report = audit_submission_certificates(self.bundle, self.submission)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["all_certificate_check_rate"], 1.0)
        self.assertEqual(report["conclusive_certificate_check_rate"], 1.0)
        self.assertLess(report["mean_localized_sample_fraction"], 0.75)

    def test_rehashed_certificate_with_nonexistent_witness_ref_fails(self) -> None:
        case = self.bundle["cases"][0]
        cert = deepcopy(self.submission["veap_certificates"][case["case_id"]])
        cert["evidence_witnesses"][0]["evidence_refs"] = ["obs-999-forged"]
        cert.pop("certificate_sha256", None)
        cert["certificate_sha256"] = canonical_hash(cert)
        res = audit_single_certificate(case["contract"], case["trace"], cert)
        self.assertEqual(res["certificate_check"], "FAIL")

    def test_rehashed_certificate_with_dropped_coverage_refs_fails(self) -> None:
        case = self.bundle["cases"][0]
        cert = deepcopy(self.submission["veap_certificates"][case["case_id"]])
        # Keep only the first observation ref, which cannot cover the full mission window
        cert["evidence_witnesses"][0]["evidence_refs"] = ["obs-000"]
        cert["requirements"]["keepout_continuous"]["witnesses"][0]["evidence_refs"] = ["obs-000"]
        cert.pop("certificate_sha256", None)
        cert["certificate_sha256"] = canonical_hash(cert)
        res = audit_single_certificate(case["contract"], case["trace"], cert)
        self.assertEqual(res["certificate_check"], "FAIL")

    def test_submission_audit_fails_closed_when_any_certificate_corrupted(self) -> None:
        bad_sub = deepcopy(self.submission)
        first_cid = self.bundle["cases"][0]["case_id"]
        bad_sub["veap_certificates"][first_cid]["verdict"] = "VIOLATING"
        with self.assertRaises(CertificateAuditError):
            audit_submission_certificates(self.bundle, bad_sub, fail_closed=True)


if __name__ == "__main__":
    unittest.main()
