"""VEAP R1.3 study schemas, reference-leakage guards, and 30-scene pilot generator.

Separates blinded evaluator inputs (`veap.r13.evaluator_bundle/1`) from sealed
reference custody (`veap.r13.sealed_reference/1`).
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from veap_evidence.verdict import STATES, _validate, canonical_hash

EVALUATOR_BUNDLE_SCHEMA = "veap.r13.evaluator_bundle/1"
SEALED_REFERENCE_SCHEMA = "veap.r13.sealed_reference/1"
SUBMISSION_SCHEMA = "veap.r13.submission/1"
SCORE_REPORT_SCHEMA = "veap.r13.score_report/1"

CONDITIONS = (
    "A_COMPLETE_COMPLIANT",
    "B_ESTABLISHED_INTRUSION",
    "C_CRITICAL_OMISSION",
    "D_IRRELEVANT_OMISSION",
)

FORBIDDEN_REFERENCE_KEYS = frozenset({
    "ground_truth",
    "expected_verdict",
    "reference_verdict",
    "reference_label",
    "true_verdict",
    "hidden_trajectory",
    "reference_trajectory",
    "oracle",
    "condition_code",
    "condition",
    "author_secret",
    "is_compliant_truth",
})


class ReferenceLeakageError(ValueError):
    """Raised when evaluator-facing inputs contain reference or oracle information."""


class SchemaValidationError(ValueError):
    """Raised when an R1.3 study artifact violates schema constraints."""


def _scan_forbidden_keys(obj: Any, path: str = "root") -> list[str]:
    leaks: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_str = str(k)
            if key_str in FORBIDDEN_REFERENCE_KEYS:
                leaks.append(f"{path}.{key_str}")
            leaks.extend(_scan_forbidden_keys(v, f"{path}.{key_str}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            leaks.extend(_scan_forbidden_keys(item, f"{path}[{idx}]"))
    return leaks


def validate_evaluator_bundle(bundle: dict[str, Any]) -> None:
    """Fail closed if an evaluator bundle is malformed or leaks reference labels."""
    if not isinstance(bundle, dict) or bundle.get("schema") != EVALUATOR_BUNDLE_SCHEMA:
        raise SchemaValidationError(f"Expected schema {EVALUATOR_BUNDLE_SCHEMA}")
    leaks = _scan_forbidden_keys(bundle)
    if leaks:
        raise ReferenceLeakageError(f"Reference leakage detected in evaluator bundle: {leaks}")
    cases = bundle.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SchemaValidationError("Evaluator bundle must contain a non-empty cases list")
    allowed_case_keys = {"case_id", "scene_id", "contract", "trace", "input_sha256"}
    seen_case_ids: set[str] = set()
    for idx, item in enumerate(cases):
        if not isinstance(item, dict):
            raise SchemaValidationError(f"Case {idx} must be a dict")
        extra = set(item.keys()) - allowed_case_keys
        if extra:
            raise ReferenceLeakageError(f"Case {idx} contains unauthorized keys: {sorted(extra)}")
        cid = item.get("case_id")
        sid = item.get("scene_id")
        if not isinstance(cid, str) or not cid or cid in seen_case_ids:
            raise SchemaValidationError(f"Invalid or duplicate case_id at index {idx}: {cid}")
        for cond_token in ("complete", "intrusion", "violat", "compliant", "inconclusive", "omission", "cond_"):
            if cond_token in cid.lower():
                raise ReferenceLeakageError(f"case_id '{cid}' leaks condition identity")
        if not isinstance(sid, str) or not sid:
            raise SchemaValidationError(f"Invalid scene_id at index {idx}")
        seen_case_ids.add(cid)
        _validate(item["contract"], item["trace"])
        expected_input_sha = canonical_hash({"contract": item["contract"], "trace": item["trace"]})
        if item.get("input_sha256") != expected_input_sha:
            raise SchemaValidationError(f"Case {cid} input_sha256 mismatch")


def validate_sealed_reference(reference: dict[str, Any], evaluator_bundle: dict[str, Any] | None = None) -> None:
    """Validate sealed reference custody object and optional binding to evaluator bundle."""
    if not isinstance(reference, dict) or reference.get("schema") != SEALED_REFERENCE_SCHEMA:
        raise SchemaValidationError(f"Expected schema {SEALED_REFERENCE_SCHEMA}")
    if evaluator_bundle is not None:
        bundle_sha = canonical_hash(evaluator_bundle)
        if reference.get("evaluator_bundle_sha256") != bundle_sha:
            raise SchemaValidationError("Sealed reference does not match evaluator_bundle_sha256")
    cases = reference.get("cases")
    if not isinstance(cases, dict) or not cases:
        raise SchemaValidationError("Sealed reference must contain a non-empty cases mapping")
    for cid, meta in cases.items():
        if meta.get("condition_code") not in CONDITIONS:
            raise SchemaValidationError(f"Case {cid} has invalid condition_code: {meta.get('condition_code')}")
        if meta.get("expected_verdict") not in STATES:
            raise SchemaValidationError(f"Case {cid} has invalid expected_verdict: {meta.get('expected_verdict')}")


def _make_sample(idx: int, t: float, x: float, y: float, frame_id: str) -> dict[str, Any]:
    return {
        "event_id": f"obs-{idx:03d}",
        "t_s": round(t, 4),
        "x": round(x, 5),
        "y": round(y, 5),
        "frame_id": frame_id,
        "sensor_healthy": True,
        "topics": ["/odom", "/tf"],
    }


def generate_r13_pilot_split(n_scenes: int = 30, seed: int = 20261114) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate a 30-scene x 4-condition blinded pilot split and its sealed reference.

    Each scene has unique geometry (keepout box, goal coordinates, mission duration,
    speed bound, robot radius, and trajectory curvature) so no two scenes are rigid
    translations or rescalings of one another.
    """
    if n_scenes < 5 or n_scenes > 200:
        raise ValueError("n_scenes must be between 5 and 200")

    evaluator_cases: list[dict[str, Any]] = []
    reference_cases: dict[str, dict[str, Any]] = {}

    for s_idx in range(n_scenes):
        scene_id = f"scene-{s_idx + 1:03d}"
        frame_id = f"map_s{s_idx + 1:03d}"

        # Distinct scene parameters per scene (non-translational diversity)
        duration = round(6.0 + 0.2 * (s_idx % 7) + 0.05 * (s_idx // 7), 2)
        speed = round(1.15 + 0.04 * (s_idx % 9) + 0.01 * (s_idx // 9), 3)
        radius = round(0.18 + 0.005 * (s_idx % 6), 3)
        uncertainty = round(0.01 + 0.002 * (s_idx % 4), 4)
        max_gap_s = 0.75

        # Keepout placed near the middle-upper region, varying size and aspect ratio per scene
        kx0 = round(2.2 + 0.17 * s_idx + 0.03 * ((s_idx * 3) % 5), 3)
        ky0 = round(1.8 + 0.11 * (s_idx % 8) + 0.04 * (s_idx // 8), 3)
        kw = round(0.9 + 0.06 * (s_idx % 5), 3)
        kh = round(0.75 + 0.05 * ((s_idx * 2) % 6), 3)
        keepout = [kx0, ky0, round(kx0 + kw, 3), round(ky0 + kh, 3)]

        # Goal placed well clear of keepout in positive x, below ky0
        goal_x = round(kx0 + kw + 1.8 + 0.09 * (s_idx % 6), 3)
        goal_y = round(ky0 - 1.35 - 0.04 * (s_idx % 5), 3)
        goal_tol = round(0.32 + 0.01 * (s_idx % 4), 3)

        contract = {
            "schema": "veap.evidence.contract/1",
            "scene_id": scene_id,
            "frame_id": frame_id,
            "mission_start_s": 0.0,
            "mission_end_s": duration,
            "max_speed_mps": speed,
            "robot_radius_m": radius,
            "position_uncertainty_m": uncertainty,
            "max_gap_s": max_gap_s,
            "keepout": keepout,
            "goal": {"x": goal_x, "y": goal_y, "tolerance_m": goal_tol},
            "required_topics": ["/odom", "/tf"],
        }

        # Dense 25-step base time grid from 0.0 to duration
        n_steps = 24
        dt = duration / n_steps
        start_x = round(kx0 - 1.9 - 0.05 * (s_idx % 4), 3)
        start_y = goal_y

        # Safe trajectory stays along y = goal_y (distance >= 1.35m from keepout bottom ky0)
        # with unique nonlinear progress curve per scene so trajectories are non-isomorphic
        gamma = 0.85 + 0.015 * s_idx
        safe_samples: list[dict[str, Any]] = []
        for i in range(n_steps + 1):
            t = round(i * dt, 4) if i < n_steps else duration
            u = i / n_steps
            # Smooth progress that stays well below speed bound
            prog = 0.5 * u + 0.5 * (u ** gamma)
            x = start_x + (goal_x - start_x) * prog
            y = start_y - 0.12 * math.sin(math.pi * u * (1 + (s_idx % 3) * 0.2))
            safe_samples.append(_make_sample(i, t, x, y, frame_id))

        # Condition A: Complete compliant trajectory
        trace_a = {"schema": "veap.evidence.trace/1", "source_kind": "synthetic", "samples": safe_samples}

        # Condition B: Intrusion trajectory (passes through keepout center at mid-mission)
        intrusion_samples: list[dict[str, Any]] = []
        k_cx = 0.5 * (keepout[0] + keepout[2])
        k_cy = 0.5 * (keepout[1] + keepout[3])
        # Use a higher speed bound in contract_b so the detour into keepout is kinematically valid
        contract_b = dict(contract)
        contract_b["max_speed_mps"] = round(speed * 2.2, 3)
        for i in range(n_steps + 1):
            t = round(i * dt, 4) if i < n_steps else duration
            u = i / n_steps
            if u <= 0.5:
                w = u / 0.5
                x = start_x + (k_cx - start_x) * w
                y = start_y + (k_cy - start_y) * w
            else:
                w = (u - 0.5) / 0.5
                x = k_cx + (goal_x - k_cx) * w
                y = k_cy + (goal_y - k_cy) * w
            intrusion_samples.append(_make_sample(i, t, x, y, frame_id))
        trace_b = {"schema": "veap.evidence.trace/1", "source_kind": "synthetic", "samples": intrusion_samples}

        # Condition C: Critical omission (trajectory skirts close to keepout and drops middle samples)
        critical_samples: list[dict[str, Any]] = []
        skirt_y = ky0 - radius - uncertainty - 0.15
        for i in range(n_steps + 1):
            # Drop steps 7..17 so the unproven gap around the keepout is large
            if 7 <= i <= 17:
                continue
            t = round(i * dt, 4) if i < n_steps else duration
            u = i / n_steps
            x = start_x + (goal_x - start_x) * u
            y = skirt_y if i < 7 else goal_y
            critical_samples.append(_make_sample(i, t, x, y, frame_id))
        trace_c = {"schema": "veap.evidence.trace/1", "source_kind": "synthetic", "samples": critical_samples}

        # Condition D: Irrelevant omission (drops 3 consecutive early samples far from keepout
        # so gap > max_gap_s = 0.75s, yet clearance d > 1.8m keeps safe_radius > 1.2s covering the gap)
        irrelevant_samples = [
            row for i, row in enumerate(safe_samples) if i not in (2, 3, 4)
        ]
        trace_d = {"schema": "veap.evidence.trace/1", "source_kind": "synthetic", "samples": irrelevant_samples}

        scene_conditions = [
            ("A_COMPLETE_COMPLIANT", contract, trace_a, "COMPLIANT", "complete_safe_trajectory"),
            ("B_ESTABLISHED_INTRUSION", contract_b, trace_b, "VIOLATING", "keepout_interior_penetration"),
            ("C_CRITICAL_OMISSION", contract, trace_c, "INCONCLUSIVE", "unobserved_near_keepout_window"),
            ("D_IRRELEVANT_OMISSION", contract, trace_d, "COMPLIANT", "decidable_gap_far_from_keepout"),
        ]

        for c_idx, (cond_code, c_obj, t_obj, expected_verdict, mechanism) in enumerate(scene_conditions):
            # Blinded opaque hash-derived case ID (no condition token in ID)
            raw_token = f"{seed}:{scene_id}:{c_idx}"
            opaque_suffix = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:8]
            case_id = f"{scene_id}- item-{c_idx + 1:02d}-{opaque_suffix}".replace(" ", "")
            input_sha = canonical_hash({"contract": c_obj, "trace": t_obj})

            evaluator_cases.append({
                "case_id": case_id,
                "scene_id": scene_id,
                "contract": c_obj,
                "trace": t_obj,
                "input_sha256": input_sha,
            })
            reference_cases[case_id] = {
                "case_id": case_id,
                "scene_id": scene_id,
                "condition_code": cond_code,
                "expected_verdict": expected_verdict,
                "decisive_required": expected_verdict in ("COMPLIANT", "VIOLATING"),
                "omission_mechanism": mechanism,
                "input_sha256": input_sha,
            }

    evaluator_bundle = {
        "schema": EVALUATOR_BUNDLE_SCHEMA,
        "study_id": "veap-r13-dev-pilot-30x4",
        "study_scope": "DEVELOPMENT_PILOT_SYNTHETIC_SEALED_HARNESS",
        "independent_external_authorship": False,
        "physical_sensor_provenance": False,
        "n_scenes": n_scenes,
        "n_cases": len(evaluator_cases),
        "cases": evaluator_cases,
    }
    validate_evaluator_bundle(evaluator_bundle)

    sealed_reference = {
        "schema": SEALED_REFERENCE_SCHEMA,
        "study_id": "veap-r13-dev-pilot-30x4",
        "evaluator_bundle_sha256": canonical_hash(evaluator_bundle),
        "n_scenes": n_scenes,
        "n_cases": len(reference_cases),
        "cases": reference_cases,
    }
    validate_sealed_reference(sealed_reference, evaluator_bundle)
    return evaluator_bundle, sealed_reference
