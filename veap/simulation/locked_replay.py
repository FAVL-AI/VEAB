"""VEAP v0.6: frozen, frame-explicit control-input contracts for native physics.

This contract is intentionally *open-loop*: the engines receive the same command
sequence. The contract does not prove that their robot models or dynamics match.
No command is sent to physical equipment.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from ..spec import Scenario, digest
from .scene import canonical_scenario_payload, compile_scene
from .telemetry import check_physics_trace

TAPE_SCHEMA = "veab-control-tape/1"
REPORT_SCHEMA = "veab-locked-physics-comparison/1"
MAX_STEPS = 2000


def _num(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def create_tape(scenario: Scenario, commands: Sequence[Sequence[float]], *, seed: int = 17,
                controller_id: str = "planar-force-pd/1") -> dict:
    """Freeze ENU velocity references and controller identity for paired runs.

    Mass, contact parameters and control gains remain research surrogates until
    independently calibrated and reported. The hash provides integrity only.
    """
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed outside uint32")
    if controller_id != "planar-force-pd/1":
        raise ValueError("unsupported controller")
    if not 1 <= len(commands) <= min(MAX_STEPS, scenario.max_steps):
        raise ValueError("invalid command tape length")
    values = []
    for i, row in enumerate(commands):
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError("each command requires ENU vx, vy and yaw rate")
        x, y, yaw = (_num(v, f"command[{i}]") for v in row)
        if math.hypot(x, y) > scenario.max_speed + 1e-10:
            raise ValueError("command exceeds scenario velocity limit")
        if abs(yaw) > 2.0:
            raise ValueError("yaw rate exceeds reference limit")
        values.append([round(x, 7), round(y, 7), round(yaw, 7)])
    dt = float(scenario.dt)
    payload = {
        "schema_version": TAPE_SCHEMA,
        "scenario_id": scenario.id,
        "scenario_sha256": digest(canonical_scenario_payload(scenario)),
        "scene_sha256": compile_scene(scenario)["content_sha256"],
        "source_split": scenario.split,
        "seed": seed,
        "coordinate_frame": "ENU_z_up_m",
        "command_frame": "world_enu_velocity_reference",
        "dt_s": dt,
        "controller_id": controller_id,
        "robot_model": "veab-scout-surrogate-not-vendor-calibrated",
        "calibration_status": "unmeasured_research_surrogate",
        "commands_vx_vy_yaw": values,
        "evidence_warning": "Public toy scenes; no native engine, physical sensor or external provenance implied",
    }
    return {**payload, "tape_sha256": digest(payload)}


def standard_tape(scenario: Scenario, *, seed: int = 17, steps: int = 24) -> dict:
    """Bounded deterministic open-loop excitation; not a navigation success claim."""
    if type(steps) is not int or not 4 <= steps <= min(scenario.max_steps, MAX_STEPS):
        raise ValueError("steps outside allowed range")
    velocity = min(0.20, scenario.max_speed / 2)
    result = []
    for i in range(steps):
        phase = (4 * i) // steps
        result.append([(velocity, 0, 0), (0, velocity, 0), (-velocity, 0, 0), (0, 0, 0)][min(3, phase)])
    return create_tape(scenario, result, seed=seed)


def validate_tape(scenario: Scenario, tape: dict) -> None:
    if not isinstance(tape, dict):
        raise ValueError("tape must be object")
    expected = {
        "schema_version", "scenario_id", "scenario_sha256", "scene_sha256", "source_split", "seed",
        "coordinate_frame", "command_frame", "dt_s", "controller_id", "robot_model",
        "calibration_status", "commands_vx_vy_yaw", "evidence_warning", "tape_sha256",
    }
    if set(tape) != expected:
        raise ValueError("control tape schema mismatch")
    if tape["schema_version"] != TAPE_SCHEMA:
        raise ValueError("unsupported tape version")
    if (tape["scenario_id"] != scenario.id or
        tape["scenario_sha256"] != digest(canonical_scenario_payload(scenario)) or
        tape["scene_sha256"] != compile_scene(scenario)["content_sha256"] or
        tape["source_split"] != scenario.split):
        raise ValueError("scenario or scene identity mismatch")
    if (tape["coordinate_frame"] != "ENU_z_up_m" or
        tape["command_frame"] != "world_enu_velocity_reference" or
        tape["robot_model"] != "veab-scout-surrogate-not-vendor-calibrated" or
        tape["calibration_status"] != "unmeasured_research_surrogate"):
        raise ValueError("frame, model or calibration status mismatch")
    if type(tape["dt_s"]) not in (float, int) or tape["dt_s"] != float(scenario.dt):
        raise ValueError("control timestep mismatch")
    if type(tape["evidence_warning"]) is not str or not tape["evidence_warning"]:
        raise ValueError("evidence warning required")
    recomputed = create_tape(scenario, tape["commands_vx_vy_yaw"],
                             seed=tape["seed"], controller_id=tape["controller_id"])
    if tape != recomputed:
        raise ValueError("tape modified, missing metadata or checksum mismatch")


def validate_execution(scenario: Scenario, tape: dict, trace: dict, *,
                       timing_tolerance_s: float = 0.002) -> dict:
    """Validate that a recorded physics trace was sampled under a specific tape.

    No source authenticity is implied. If a simulator reports an incorrect state
    consistently, trace hash verification alone cannot detect that failure.
    """
    validate_tape(scenario, tape)
    report = check_physics_trace(trace)
    if not report["trace_integrity"]:
        raise ValueError("physics trace integrity invalid: " + "; ".join(report["errors"]))
    m = trace["manifest"]
    if m["scenario_sha256"] != tape["scenario_sha256"] or m["scene_sha256"] != tape["scene_sha256"]:
        raise ValueError("physics trace from different scene")
    samples = trace["samples"]
    if len(samples) != len(tape["commands_vx_vy_yaw"]) + 1:
        raise ValueError("physics trace missing or extra locked steps")
    if samples[0]["command_vx_vy_yaw"] != [0.0, 0.0, 0.0]:
        raise ValueError("initial sample must have zero command")
    tol = _num(timing_tolerance_s, "timing tolerance")
    if not 0 <= tol <= 0.1:
        raise ValueError("timing tolerance outside accepted range")
    max_jitter = 0.0
    for tick, sample in enumerate(samples):
        nominal = tick * tape["dt_s"]
        error = abs(sample["time_s"] - nominal)
        max_jitter = max(max_jitter, error)
        if error > tol + 1e-9:
            raise ValueError(f"timestamp outside locked grid at tick {tick}")
        if tick and any(abs(a - b) > 1e-6 for a, b in zip(
            sample["command_vx_vy_yaw"], tape["commands_vx_vy_yaw"][tick - 1])):
            raise ValueError(f"command differs from frozen tape at tick {tick}")
    return {"trace_integrity": True, "tape_matches": True,
            "max_timestamp_error_s": round(max_jitter, 8),
            "engine": m["engine"], "samples": len(samples),
            "physical_source_authenticity": "not_established"}


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(values)-1)*fraction
    low = math.floor(k)
    high = math.ceil(k)
    return ordered[low]*(high-k) + ordered[high]*(k-low) if high != low else ordered[low]


def paired_physics_report(scenario: Scenario, tape: dict, left: dict, right: dict,
                          *, max_position_rmse_m: float = 0.10) -> dict:
    """Compute cross-engine mismatch on identical commands; NEVER claim ground truth."""
    l = validate_execution(scenario, tape, left)
    r = validate_execution(scenario, tape, right)
    if left["manifest"]["engine"] == right["manifest"]["engine"]:
        raise ValueError("cross-engine report requires two distinct engines")
    tolerance = _num(max_position_rmse_m, "position tolerance")
    if not 0 < tolerance <= 10:
        raise ValueError("position tolerance outside supported bounds")
    distances = [math.dist(a["position_xyz_m"], b["position_xyz_m"])
                 for a, b in zip(left["samples"], right["samples"])]
    contact_a = [p["contacts"] for p in left["samples"]]
    contact_b = [p["contacts"] for p in right["samples"]]
    known_contacts = sum(a is not None and b is not None for a,b in zip(contact_a,contact_b))
    mismatch_contacts = sum(a != b for a,b in zip(contact_a,contact_b) if a is not None and b is not None)
    rmse = math.sqrt(sum(v*v for v in distances) / len(distances))
    return {
        "schema_version": REPORT_SCHEMA,
        "tape_sha256": tape["tape_sha256"],
        "scene_sha256": tape["scene_sha256"],
        "engine_left": left["manifest"]["engine"],
        "engine_right": right["manifest"]["engine"],
        "engine_versions": [left["manifest"]["engine_version"], right["manifest"]["engine_version"]],
        "matched_controls": l["tape_matches"] and r["tape_matches"],
        "samples": len(distances),
        "position_rmse_m": round(rmse, 8),
        "position_p90_m": round(_percentile(distances, 0.9), 8),
        "position_max_m": round(max(distances), 8),
        "position_rmse_tolerance_m": tolerance,
        "position_rmse_within_target": rmse <= tolerance,
        "contact_observed_samples": known_contacts,
        "contact_count_disagreement_samples": mismatch_contacts,
        "contacts_comparable": known_contacts == len(distances),
        "control_timegrid_max_error_s": max(l["max_timestamp_error_s"], r["max_timestamp_error_s"]),
        "calibration_status": tape["calibration_status"],
        "eligible_for_physics_equivalence_claim": False,
        "independently_attested_ground_truth": False,
        "scope": "paired cross-simulator trace discrepancy; not accuracy, reliability, real-world safety, or SOTA",
    }
