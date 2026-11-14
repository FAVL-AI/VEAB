"""VEAP R1.3 scene-independence and anti-contamination split auditor.

Fails closed if:
1. Evaluator inputs contain any reference labels or oracle fields.
2. Distinct cases share identical observation traces.
3. Purportedly independent scenes share duplicated or rigid-translation-equivalent
   keepout/goal geometry or displacement trajectories.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from veap_evidence.verdict import canonical_hash
from .study_schema import validate_evaluator_bundle


class SplitIntegrityError(ValueError):
    """Raised when a study split violates scene independence or anti-contamination rules."""


def _normalized_scene_geometry(contract: dict[str, Any]) -> tuple[float, ...]:
    """Return translation-invariant scene geometry signature relative to keepout origin."""
    kx0, ky0, kx1, ky1 = [float(v) for v in contract["keepout"]]
    gx = float(contract["goal"]["x"])
    gy = float(contract["goal"]["y"])
    gtol = float(contract["goal"]["tolerance_m"])
    return (
        round(kx1 - kx0, 5),
        round(ky1 - ky0, 5),
        round(gx - kx0, 5),
        round(gy - ky0, 5),
        round(gtol, 5),
        round(float(contract["mission_end_s"]) - float(contract["mission_start_s"]), 5),
        round(float(contract["max_speed_mps"]), 5),
        round(float(contract["robot_radius_m"]), 5),
    )


def _normalized_trajectory_signature(trace: dict[str, Any]) -> tuple[tuple[float, float, float], ...]:
    """Return translation-invariant (dt, dx, dy) displacement sequence from first sample."""
    samples = [s for s in trace.get("samples", []) if "t_s" in s and "x" in s and "y" in s]
    if not samples:
        return ()
    t0 = float(samples[0]["t_s"])
    x0 = float(samples[0]["x"])
    y0 = float(samples[0]["y"])
    return tuple(
        (
            round(float(s["t_s"]) - t0, 4),
            round(float(s["x"]) - x0, 4),
            round(float(s["y"]) - y0, 4),
        )
        for s in samples
    )


def audit_split_integrity(evaluator_bundle: dict[str, Any]) -> dict[str, Any]:
    """Verify scene independence, trace uniqueness, and absence of rigid-translation copies."""
    validate_evaluator_bundle(evaluator_bundle)

    cases = evaluator_bundle["cases"]
    by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    trace_hashes: dict[str, str] = {}
    duplicate_traces: list[tuple[str, str]] = []

    for item in cases:
        cid = item["case_id"]
        sid = item["scene_id"]
        by_scene[sid].append(item)
        t_sha = canonical_hash(item["trace"])
        if t_sha in trace_hashes:
            duplicate_traces.append((trace_hashes[t_sha], cid))
        else:
            trace_hashes[t_sha] = cid

    # Check pairwise scene independence (geometry + displacement signatures across scenes)
    scene_geom_seen: dict[tuple[float, ...], str] = {}
    scene_traj_seen: dict[tuple[tuple[float, float, float], ...], str] = {}
    translated_or_duplicate_scenes: list[dict[str, str]] = []

    for sid in sorted(by_scene):
        scene_cases = by_scene[sid]
        rep_geom = _normalized_scene_geometry(scene_cases[0]["contract"])
        if rep_geom in scene_geom_seen:
            translated_or_duplicate_scenes.append({
                "scene_a": scene_geom_seen[rep_geom],
                "scene_b": sid,
                "reason": "translation_equivalent_scene_geometry",
            })
        else:
            scene_geom_seen[rep_geom] = sid

        for item in scene_cases:
            sig = _normalized_trajectory_signature(item["trace"])
            if not sig:
                continue
            prev_scene = scene_traj_seen.get(sig)
            if prev_scene is not None and prev_scene != sid:
                translated_or_duplicate_scenes.append({
                    "scene_a": prev_scene,
                    "scene_b": sid,
                    "case_id": item["case_id"],
                    "reason": "translation_equivalent_trajectory_across_scenes",
                })
            else:
                scene_traj_seen[sig] = sid

    errors: list[str] = []
    if duplicate_traces:
        errors.append(f"Duplicate observation traces across cases: {duplicate_traces}")
    if translated_or_duplicate_scenes:
        errors.append(f"Non-independent or translated-copy scenes detected: {translated_or_duplicate_scenes}")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "n_scenes": len(by_scene),
        "n_cases": len(cases),
        "duplicate_trace_pairs": duplicate_traces,
        "translated_or_duplicate_scenes": translated_or_duplicate_scenes,
        "errors": errors,
    }
    if errors:
        raise SplitIntegrityError("; ".join(errors))
    return report
