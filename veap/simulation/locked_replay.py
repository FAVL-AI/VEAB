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
DIAGNOSTIC_SCHEMA = "veap-paired-physics-diagnostic/1"
MAX_STEPS = 2000


def _yaw_from_quat_xyzw(q: Sequence[float]) -> float:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _angle_diff_rad(a: float, b: float) -> float:
    return math.atan2(math.sin(a - b), math.cos(a - b))


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


def _trace_repeatability(scenario: Scenario, tape: dict, reference: dict, candidate: dict) -> dict:
    validate_execution(scenario, tape, reference)
    validate_execution(scenario, tape, candidate)
    if reference["manifest"]["engine"] != candidate["manifest"]["engine"]:
        raise ValueError("repeatability check requires matching engine identifier")
    pos_diffs = [
        math.dist(a["position_xyz_m"], b["position_xyz_m"])
        for a, b in zip(reference["samples"], candidate["samples"])
    ]
    vel_diffs = [
        math.dist(a["velocity_xyz_m_s"], b["velocity_xyz_m_s"])
        for a, b in zip(reference["samples"], candidate["samples"])
    ]
    yaw_diffs = [
        abs(float(a["angular_z_rad_s"]) - float(b["angular_z_rad_s"]))
        for a, b in zip(reference["samples"], candidate["samples"])
    ]
    max_pos = round(max(pos_diffs), 8)
    max_vel = round(max(vel_diffs), 8)
    max_yaw_rate = round(max(yaw_diffs), 8)
    return {
        "engine": reference["manifest"]["engine"],
        "engine_version_reference": reference["manifest"]["engine_version"],
        "engine_version_candidate": candidate["manifest"]["engine_version"],
        "sample_chain_sha256_matches": (
            reference["manifest"]["sample_chain_sha256"] == candidate["manifest"]["sample_chain_sha256"]
        ),
        "max_position_diff_m": max_pos,
        "max_velocity_diff_m_s": max_vel,
        "max_yaw_rate_diff_rad_s": max_yaw_rate,
        "repeats_deterministically": max_pos <= 1e-7 and max_vel <= 1e-7 and max_yaw_rate <= 1e-7,
    }


def diagnose_paired_replay(
    scenario: Scenario,
    tape: dict,
    left: dict,
    right: dict,
    *,
    position_divergence_threshold_m: float = 0.001,
    velocity_divergence_threshold_m_s: float = 0.01,
    max_position_rmse_m: float = 0.10,
    repeat_left: dict | None = None,
    repeat_right: dict | None = None,
) -> dict:
    """Produce a per-tick cross-engine divergence localization and repeatability report."""
    pos_thresh = _num(position_divergence_threshold_m, "position divergence threshold")
    vel_thresh = _num(velocity_divergence_threshold_m_s, "velocity divergence threshold")
    if pos_thresh <= 0 or vel_thresh <= 0:
        raise ValueError("divergence thresholds must be positive")
    summary = paired_physics_report(scenario, tape, left, right, max_position_rmse_m=max_position_rmse_m)

    ticks: list[dict[str, Any]] = []
    contact_counts = {
        "both_observed_match": 0,
        "both_observed_disagree": 0,
        "missing_left": 0,
        "missing_right": 0,
        "missing_both": 0,
    }
    stalled_left: list[int] = []
    stalled_right: list[int] = []
    commanded_motion_ticks = 0

    for a, b in zip(left["samples"], right["samples"]):
        t = int(a["tick"])
        cmd = [float(v) for v in a["command_vx_vy_yaw"]]
        lp = [float(v) for v in a["position_xyz_m"]]
        rp = [float(v) for v in b["position_xyz_m"]]
        lv = [float(v) for v in a["velocity_xyz_m_s"]]
        rv = [float(v) for v in b["velocity_xyz_m_s"]]
        dp = [round(rp[i] - lp[i], 8) for i in range(3)]
        dv = [round(rv[i] - lv[i], 8) for i in range(3)]
        pos_err = round(math.dist(lp, rp), 8)
        planar_pos_err = round(math.hypot(rp[0] - lp[0], rp[1] - lp[1]), 8)
        vert_pos_err = round(abs(rp[2] - lp[2]), 8)
        vel_err = round(math.dist(lv, rv), 8)
        planar_vel_err = round(math.hypot(rv[0] - lv[0], rv[1] - lv[1]), 8)
        vert_vel_err = round(abs(rv[2] - lv[2]), 8)
        cmd_track_l = round(math.hypot(lv[0] - cmd[0], lv[1] - cmd[1]), 8)
        cmd_track_r = round(math.hypot(rv[0] - cmd[0], rv[1] - cmd[1]), 8)
        yaw_l = round(_yaw_from_quat_xyzw(a["orientation_xyzw"]), 8)
        yaw_r = round(_yaw_from_quat_xyzw(b["orientation_xyzw"]), 8)
        yaw_err = round(abs(_angle_diff_rad(yaw_r, yaw_l)), 8)
        wz_l = round(float(a["angular_z_rad_s"]), 8)
        wz_r = round(float(b["angular_z_rad_s"]), 8)
        wz_err = round(abs(wz_r - wz_l), 8)
        cl = a["contacts"]
        cr = b["contacts"]
        if cl is None and cr is None:
            c_status = "missing_both"
        elif cl is None:
            c_status = "missing_left"
        elif cr is None:
            c_status = "missing_right"
        elif cl == cr:
            c_status = "both_observed_match"
        else:
            c_status = "both_observed_disagree"
        contact_counts[c_status] += 1

        if math.hypot(cmd[0], cmd[1]) > 1e-6:
            commanded_motion_ticks += 1
            if math.hypot(lv[0], lv[1]) < 0.005:
                stalled_left.append(t)
            if math.hypot(rv[0], rv[1]) < 0.005:
                stalled_right.append(t)

        ticks.append({
            "tick": t,
            "time_s": float(a["time_s"]),
            "command_vx_vy_yaw": cmd,
            "position_left_xyz_m": lp,
            "position_right_xyz_m": rp,
            "position_delta_xyz_m": dp,
            "position_error_m": pos_err,
            "planar_position_error_m": planar_pos_err,
            "vertical_position_error_m": vert_pos_err,
            "velocity_left_xyz_m_s": lv,
            "velocity_right_xyz_m_s": rv,
            "velocity_delta_xyz_m_s": dv,
            "velocity_error_m_s": vel_err,
            "planar_velocity_error_m_s": planar_vel_err,
            "vertical_velocity_error_m_s": vert_vel_err,
            "command_tracking_error_left_xy_m_s": cmd_track_l,
            "command_tracking_error_right_xy_m_s": cmd_track_r,
            "yaw_left_rad": yaw_l,
            "yaw_right_rad": yaw_r,
            "yaw_error_rad": yaw_err,
            "angular_z_left_rad_s": wz_l,
            "angular_z_right_rad_s": wz_r,
            "angular_z_error_rad_s": wz_err,
            "contacts_left": cl,
            "contacts_right": cr,
            "contact_status": c_status,
        })

    def _first(pred, key: str):
        for row in ticks:
            if pred(row):
                return row["tick"], row[key]
        return None, None

    first_pos_tick, first_pos_val = _first(lambda r: r["position_error_m"] > pos_thresh, "position_error_m")
    first_planar_tick, first_planar_val = _first(
        lambda r: r["planar_position_error_m"] > pos_thresh, "planar_position_error_m"
    )
    first_vel_tick, first_vel_val = _first(lambda r: r["velocity_error_m_s"] > vel_thresh, "velocity_error_m_s")
    first_planar_vel_tick, first_planar_vel_val = _first(
        lambda r: r["planar_velocity_error_m_s"] > vel_thresh, "planar_velocity_error_m_s"
    )
    first_exceed_tick, first_exceed_val = _first(
        lambda r: r["position_error_m"] > summary["position_rmse_tolerance_m"], "position_error_m"
    )
    peak_row = max(ticks, key=lambda r: r["position_error_m"])
    t0 = ticks[0]

    localization = {
        "position_divergence_threshold_m": pos_thresh,
        "velocity_divergence_threshold_m_s": vel_thresh,
        "initial_pose_diverged_at_tick_0": (
            t0["position_error_m"] > pos_thresh or t0["velocity_error_m_s"] > vel_thresh
        ),
        "tick_0_position_error_m": t0["position_error_m"],
        "tick_0_planar_error_m": t0["planar_position_error_m"],
        "tick_0_vertical_delta_m": t0["vertical_position_error_m"],
        "tick_0_velocity_error_m_s": t0["velocity_error_m_s"],
        "tick_0_vertical_velocity_delta_m_s": t0["vertical_velocity_error_m_s"],
        "first_position_divergence_tick": first_pos_tick,
        "first_position_divergence_m": first_pos_val,
        "first_planar_divergence_tick": first_planar_tick,
        "first_planar_divergence_m": first_planar_val,
        "first_velocity_divergence_tick": first_vel_tick,
        "first_velocity_divergence_m_s": first_vel_val,
        "first_planar_velocity_divergence_tick": first_planar_vel_tick,
        "first_planar_velocity_divergence_m_s": first_planar_vel_val,
        "first_target_exceedance_tick": first_exceed_tick,
        "first_target_exceedance_m": first_exceed_val,
        "peak_position_error_tick": peak_row["tick"],
        "peak_position_error_m": peak_row["position_error_m"],
        "commanded_motion_ticks": commanded_motion_ticks,
        "stalled_planar_motion_ticks_left": stalled_left,
        "stalled_planar_motion_ticks_right": stalled_right,
        "contact_observation_counts": contact_counts,
    }

    repeatability: dict[str, Any] = {
        "left": _trace_repeatability(scenario, tape, left, repeat_left) if repeat_left is not None else None,
        "right": _trace_repeatability(scenario, tape, right, repeat_right) if repeat_right is not None else None,
        "divergence_repeats_identically": None,
    }
    if repeat_left is not None and repeat_right is not None:
        rep_summary = paired_physics_report(
            scenario, tape, repeat_left, repeat_right, max_position_rmse_m=max_position_rmse_m
        )
        repeatability["repeat_position_rmse_m"] = rep_summary["position_rmse_m"]
        repeatability["divergence_repeats_identically"] = (
            bool(repeatability["left"]["repeats_deterministically"])
            and bool(repeatability["right"]["repeats_deterministically"])
            and abs(rep_summary["position_rmse_m"] - summary["position_rmse_m"]) <= 1e-7
        )

    return {
        "schema_version": DIAGNOSTIC_SCHEMA,
        "scenario_id": scenario.id,
        "tape_sha256": tape["tape_sha256"],
        "scene_sha256": tape["scene_sha256"],
        "summary": summary,
        "localization": localization,
        "repeatability": repeatability,
        "ticks": ticks,
    }
