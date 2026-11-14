"""A deliberately bounded R1.2 software experiment, not scientific validation."""
import unittest
from copy import deepcopy

from veap_evidence.fixtures import cases
from veap_evidence.verdict import evaluate
from scripts.run_r12_assumption_sensitivity import run, SPEED_SCALES, POSE_ERRORS_M


class R12AssumptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run()

    def test_complete_grid(self):
        self.assertEqual(self.report["summary"]["n_cases"], 15 * len(SPEED_SCALES) * len(POSE_ERRORS_M))

    def test_separate_monitor_agrees_on_synthetic_grid(self):
        self.assertEqual(self.report["summary"]["independent_monitor_disagreements"], 0)

    def test_certificates_rechecked(self):
        self.assertEqual(self.report["summary"]["certificate_checker_failures"], 0)

    def test_no_new_decisive_claim_when_assumptions_relaxed(self):
        self.assertEqual(self.report["summary"]["assumption_monotonicity_failures"], 0)

    def test_source_never_upgraded_to_attested(self):
        self.assertTrue(all(v["source_authenticity"] == "UNATTESTED" for v in self.report["cases"]))

    def test_an_observed_violation_survives_an_unrelated_gap(self):
        v = cases()["violation_plus_missing"]
        for speed in SPEED_SCALES:
            c = deepcopy(v["contract"])
            c["max_speed_mps"] *= speed
            self.assertEqual(evaluate(c, v["trace"])["verdict"], "VIOLATING")

    def test_stress_does_not_claim_independent_holdout(self):
        self.assertFalse(self.report["independent_heldout_environments"])
        self.assertFalse(self.report["physical_sensor_ground_truth"])


if __name__ == "__main__":
    unittest.main()
