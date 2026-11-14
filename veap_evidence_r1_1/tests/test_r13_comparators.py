"""Tests for VEAP R1.3 comparator scoring, scene-cluster statistics, and power analysis."""
from __future__ import annotations

import unittest

from r13.blinded_runner import run_blinded_evaluation
from r13.reference_scorer import score_submission
from r13.statistics import prospective_scene_sample_size, wilson_ci_95
from r13.study_schema import generate_r13_pilot_split


class R13ComparatorAndStatisticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle, self.reference = generate_r13_pilot_split(n_scenes=10)
        self.submission = run_blinded_evaluation(self.bundle)
        self.report = score_submission(self.bundle, self.submission, self.reference)

    def test_veap_and_separate_reachability_monitor_tie_at_100pct(self) -> None:
        self.assertTrue(self.report["strong_monitor_verdict_tie_preserved"])
        veap = self.report["metrics_by_method"]["veap"]
        mon = self.report["metrics_by_method"]["separate_reachability_monitor"]
        self.assertEqual(veap["overall_case_accuracy"], 1.0)
        self.assertEqual(mon["overall_case_accuracy"], 1.0)
        self.assertEqual(veap["false_decisive_count"], 0)
        self.assertEqual(mon["false_decisive_count"], 0)

    def test_naive_sampled_safety_exhibits_false_decisive_verdicts_on_condition_c(self) -> None:
        sampled = self.report["metrics_by_method"]["sampled_safety"]
        self.assertEqual(sampled["accuracy_by_condition"]["C_CRITICAL_OMISSION"], 0.0)
        self.assertGreater(sampled["false_decisive_rate"], 0.20)

    def test_naive_gap_aware_exhibits_unnecessary_abstention_on_condition_d(self) -> None:
        gap = self.report["metrics_by_method"]["gap_aware"]
        self.assertEqual(gap["accuracy_by_condition"]["D_IRRELEVANT_OMISSION"], 0.0)
        self.assertGreater(gap["unnecessary_abstention_rate"], 0.25)

    def test_scene_clustered_comparisons_and_power_analysis(self) -> None:
        paired = self.report["scene_clustered_paired_comparisons"]
        self.assertEqual(
            paired["veap_vs_separate_reachability_monitor"]["mean_paired_difference"],
            0.0,
        )
        self.assertGreater(
            paired["veap_vs_sampled_safety"]["mean_paired_difference"],
            0.20,
        )
        power = prospective_scene_sample_size(pilot_sd=0.25, minimum_detectable_effect=0.10)
        self.assertGreaterEqual(power["recommended_confirmatory_scenes"], 50)
        lo, hi = wilson_ci_95(0, 120)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.04)


if __name__ == "__main__":
    unittest.main()
