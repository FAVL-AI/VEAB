"""Tests for VEAP R1.3 scene-independence and split-integrity auditing."""
from __future__ import annotations

from copy import deepcopy
import unittest

from r13.split_integrity import SplitIntegrityError, audit_split_integrity
from r13.study_schema import generate_r13_pilot_split
from veap_evidence.verdict import canonical_hash


class R13SplitIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle, _ = generate_r13_pilot_split(n_scenes=8)

    def test_pilot_split_passes_scene_independence_audit(self) -> None:
        report = audit_split_integrity(self.bundle)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["n_scenes"], 8)
        self.assertEqual(report["n_cases"], 32)
        self.assertEqual(report["duplicate_trace_pairs"], [])
        self.assertEqual(report["translated_or_duplicate_scenes"], [])

    def test_duplicate_observation_trace_across_cases_is_rejected(self) -> None:
        bad = deepcopy(self.bundle)
        bad["cases"][1]["trace"] = deepcopy(bad["cases"][0]["trace"])
        bad["cases"][1]["contract"] = deepcopy(bad["cases"][0]["contract"])
        bad["cases"][1]["input_sha256"] = canonical_hash(
            {"contract": bad["cases"][1]["contract"], "trace": bad["cases"][1]["trace"]}
        )
        with self.assertRaises(SplitIntegrityError):
            audit_split_integrity(bad)

    def test_rigid_translated_scene_copy_is_rejected(self) -> None:
        bad = deepcopy(self.bundle)
        # Replace scene-002's first case with a rigid (+10m, +5m) translation of scene-001's first case
        src = deepcopy(bad["cases"][0])
        dx, dy = 10.0, 5.0
        kx0, ky0, kx1, ky1 = src["contract"]["keepout"]
        src["contract"]["keepout"] = [kx0 + dx, ky0 + dy, kx1 + dx, ky1 + dy]
        src["contract"]["goal"]["x"] = round(src["contract"]["goal"]["x"] + dx, 5)
        src["contract"]["goal"]["y"] = round(src["contract"]["goal"]["y"] + dy, 5)
        for s in src["trace"]["samples"]:
            s["x"] = round(s["x"] + dx, 5)
            s["y"] = round(s["y"] + dy, 5)
        src["scene_id"] = "scene-002"
        src["case_id"] = bad["cases"][4]["case_id"]
        src["input_sha256"] = canonical_hash({"contract": src["contract"], "trace": src["trace"]})
        bad["cases"][4] = src
        with self.assertRaises(SplitIntegrityError):
            audit_split_integrity(bad)


if __name__ == "__main__":
    unittest.main()
