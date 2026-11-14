"""VEAP v0.6 frozen evaluation manifest and 40-trace release-gate evaluator."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from ..spec import digest, load_scenario
from .export import export_scene
from .locked_replay import create_tape, paired_physics_report, validate_execution
from .scene import compile_scene

EVALUATION_MANIFEST_SCHEMA = "veap-v06-evaluation-manifest/1"
RELEASE_GATE_REPORT_SCHEMA = "veap-v06-release-gate-report/1"

PILOT_BASELINE = {
    "scenario_id": "warehouse-transfer",
    "tape_sha256": "ba0d2388943e76304dc21435b5ac2c1cd434258e75b3e90daece749bddd62d6e",
    "position_rmse_m": 0.20182817,
    "position_p90_m": 0.26211512,
    "position_max_m": 0.27508361,
    "position_rmse_tolerance_m": 0.1,
    "position_rmse_within_target": False,
    "contacts_comparable": False,
    "contact_observed_samples": 0,
    "missing_contact_samples_right": 25,
    "artifacts": [
        "artifacts/research/v06-control-tape.json",
        "artifacts/research/v06-mujoco-locked-replay.json",
        "artifacts/research/v06-isaaclab-locked-replay.json",
        "artifacts/research/v06-paired-physics-report.json",
        "artifacts/research/v06-pilot-per-tick-diagnostic.json",
    ],
}

MODEL_ALIGNMENT_SPEC = {
    "coordinate_frame": "ENU_z_up_m",
    "quaternion_ordering": {
        "canonical_trace": "XYZW",
        "mujoco": "XYZW ([0, 0, sin(yaw/2), cos(yaw/2)])",
        "isaaclab": "WXYZ root_quat_w explicitly converted to XYZW",
    },
    "controller_mapping": {
        "controller_id": "planar-force-pd/1",
        "gains_kp": [22.0, 22.0, 4.0],
        "effort_limits": [50.0, 50.0, 8.0],
        "isaaclab_actuation": "set_external_force_and_torque(is_global=True)",
    },
    "timing": {
        "physics_dt_s": 0.01,
        "control_dt_s": 0.2,
        "substeps_per_control_tick": 20,
    },
    "inertial_and_damping": {
        "mass_kg": 8.0,
        "footprint_radius_m": 0.22,
        "height_m": 0.27,
        "inertia_z_kg_m2": 0.1936,
        "mujoco_linear_damping_n_s_m": 2.0,
        "isaaclab_linear_damping_s_inv": 0.25,
        "mujoco_angular_damping_n_m_s_rad": 0.3,
        "isaaclab_angular_damping_s_inv": 1.54958678,
        "vertical_abstraction": "planar surrogate at z=0.16 m (MJCF planar joints; PhysX disable_gravity=True)",
    },
    "friction_and_contacts": {
        "mjcf_world_friction": "0.8 0.1 0.1",
        "mjcf_robot_friction": "1 .005 .0001",
        "mujoco_contact_channel": "int(data.ncon) (manifold contact point count)",
        "isaaclab_contact_channel": "ContactSensor(force_threshold=1e-4) -> 1 if ||net_forces_w|| > 1e-4 else 0; null if sensor disabled",
        "missing_observation_policy": "null (never coerced to 0)",
    },
}

DEFAULT_CRITERIA = {
    "max_position_rmse_m": 0.100,
    "max_position_p90_m": 0.150,
    "max_position_max_m": 0.200,
    "max_control_timegrid_error_s": 1e-6,
    "require_contacts_comparable": True,
    "max_contact_state_disagreement_rate": 0.05,
    "max_failed_runs": 0,
    "threshold_change_justification": (
        "Retained the original 0.100 m position RMSE target from the pilot report without relaxation; "
        "added explicit P90 (0.150 m), max (0.200 m), time-grid (1e-6 s), zero missing contact observations, "
        "and <=5% binary contact-state disagreement criteria before executing the 40-trace held-out campaign."
    ),
}


def _held_out_specs() -> list[dict[str, Any]]:
    """Return 20 deterministic held-out tape specifications across 3 test-split task families."""
    return [
        # Family 1: navigation (distribution-shift, split=test) - 8 tapes
        {"tape_id": "nav-01", "scenario_id": "distribution-shift", "seed": 101, "expects_contact": False,
         "commands": [[0.25, 0.0, 0.0]] * 6 + [[0.0, -0.25, 0.0]] * 6 + [[0.25, 0.0, 0.0]] * 6 + [[0.0, 0.0, 0.0]] * 6},
        {"tape_id": "nav-02", "scenario_id": "distribution-shift", "seed": 102, "expects_contact": False,
         "commands": [[0.35, 0.15, 0.2]] * 8 + [[0.2, -0.2, -0.2]] * 8 + [[0.0, 0.0, 0.0]] * 4},
        {"tape_id": "nav-03", "scenario_id": "distribution-shift", "seed": 103, "expects_contact": False,
         "commands": [[0.4, 0.0, 0.5]] * 6 + [[0.0, -0.3, -0.5]] * 6 + [[-0.2, 0.1, 0.0]] * 6 + [[0.0, 0.0, 0.0]] * 2},
        {"tape_id": "nav-04", "scenario_id": "distribution-shift", "seed": 104, "expects_contact": False,
         "commands": [[0.5, 0.1, 0.0]] * 5 + [[0.0, 0.0, 0.0]] * 3 + [[0.3, -0.2, 0.3]] * 6 + [[0.0, 0.0, 0.0]] * 4},
        {"tape_id": "nav-05", "scenario_id": "distribution-shift", "seed": 105, "expects_contact": False,
         "commands": [[0.15, 0.15, 0.4]] * 8 + [[0.3, 0.0, -0.4]] * 8 + [[0.0, 0.0, 0.0]] * 4},
        {"tape_id": "nav-06", "scenario_id": "distribution-shift", "seed": 106, "expects_contact": False,
         "commands": [[0.45, -0.1, 0.0]] * 6 + [[0.0, 0.25, 0.3]] * 6 + [[-0.25, 0.0, -0.3]] * 6 + [[0.0, 0.0, 0.0]] * 2},
        {"tape_id": "nav-07", "scenario_id": "distribution-shift", "seed": 107, "expects_contact": True,
         # Starts at (1.2, 7.9); driving -x hits West boundary at x=0.22
         "commands": [[-0.8, 0.0, 0.0]] * 10 + [[0.0, 0.0, 0.0]] * 2},
        {"tape_id": "nav-08", "scenario_id": "distribution-shift", "seed": 108, "expects_contact": True,
         # Starts at (1.2, 7.9); driving +y hits North boundary at y=9.78
         "commands": [[0.0, 0.9, 0.0]] * 14 + [[0.0, 0.0, 0.0]] * 2},

        # Family 2: inspection (hospital-inspection, split=test) - 8 tapes
        {"tape_id": "insp-01", "scenario_id": "hospital-inspection", "seed": 201, "expects_contact": False,
         "commands": [[0.0, 0.3, 0.0]] * 6 + [[0.3, 0.0, 0.0]] * 6 + [[0.0, -0.2, 0.0]] * 6 + [[0.0, 0.0, 0.0]] * 6},
        {"tape_id": "insp-02", "scenario_id": "hospital-inspection", "seed": 202, "expects_contact": False,
         "commands": [[0.2, 0.4, 0.3]] * 8 + [[0.3, -0.1, -0.3]] * 8 + [[0.0, 0.0, 0.0]] * 4},
        {"tape_id": "insp-03", "scenario_id": "hospital-inspection", "seed": 203, "expects_contact": False,
         "commands": [[0.0, 0.5, 0.6]] * 6 + [[0.4, 0.0, -0.6]] * 6 + [[-0.2, -0.2, 0.0]] * 6 + [[0.0, 0.0, 0.0]] * 2},
        {"tape_id": "insp-04", "scenario_id": "hospital-inspection", "seed": 204, "expects_contact": False,
         "commands": [[0.3, 0.3, 0.0]] * 5 + [[0.0, 0.0, 0.0]] * 3 + [[0.0, 0.4, 0.2]] * 6 + [[0.0, 0.0, 0.0]] * 4},
        {"tape_id": "insp-05", "scenario_id": "hospital-inspection", "seed": 205, "expects_contact": False,
         "commands": [[0.15, 0.25, -0.4]] * 8 + [[0.25, 0.1, 0.4]] * 8 + [[0.0, 0.0, 0.0]] * 4},
        {"tape_id": "insp-06", "scenario_id": "hospital-inspection", "seed": 206, "expects_contact": False,
         "commands": [[0.4, 0.0, 0.2]] * 6 + [[0.0, 0.35, -0.2]] * 6 + [[-0.25, 0.0, 0.0]] * 6 + [[0.0, 0.0, 0.0]] * 2},
        {"tape_id": "insp-07", "scenario_id": "hospital-inspection", "seed": 207, "expects_contact": True,
         # Starts at (1.1, 1.1); driving -x hits West boundary at x=0.22
         "commands": [[-0.8, 0.0, 0.0]] * 10 + [[0.0, 0.0, 0.0]] * 2},
        {"tape_id": "insp-08", "scenario_id": "hospital-inspection", "seed": 208, "expects_contact": True,
         # Starts at (1.1, 1.1); driving -y hits South boundary at y=0.22
         "commands": [[0.0, -0.8, 0.0]] * 10 + [[0.0, 0.0, 0.0]] * 2},

        # Family 3: absence (absence-rejection, split=test) - 4 tapes
        {"tape_id": "abs-01", "scenario_id": "absence-rejection", "seed": 301, "expects_contact": False,
         "commands": [[0.0, 0.0, 0.0]] * 12},
        {"tape_id": "abs-02", "scenario_id": "absence-rejection", "seed": 302, "expects_contact": False,
         "commands": [[0.0, 0.0, 0.5]] * 6 + [[0.0, 0.0, -0.5]] * 6},
        {"tape_id": "abs-03", "scenario_id": "absence-rejection", "seed": 303, "expects_contact": False,
         "commands": [[0.2, 0.1, 0.0]] * 5 + [[-0.2, -0.1, 0.0]] * 5 + [[0.0, 0.0, 0.0]] * 2},
        {"tape_id": "abs-04", "scenario_id": "absence-rejection", "seed": 304, "expects_contact": True,
         # Starts at (2.0, 2.0); driving +x/+y hits Static fixture at (6.0, 4.0, r=1.1)
         "commands": [[0.88, 0.44, 0.0]] * 20},
    ]


def build_v06_evaluation_manifest(export_dir: str | Path | None = None) -> dict[str, Any]:
    """Build the frozen v0.6 evaluation manifest with scenes, asset hashes, criteria, and 20 held-out tapes."""
    specs = _held_out_specs()
    scenes_meta: dict[str, Any] = {}
    tapes_meta: list[dict[str, Any]] = []

    for spec in specs:
        s = load_scenario(spec["scenario_id"])
        if s.split != "test":
            raise ValueError(f"Held-out evaluation requires split=='test', got {s.split} for {s.id}")
        scene = compile_scene(s)
        if s.id not in scenes_meta:
            scene_entry: dict[str, Any] = {
                "scenario_id": s.id,
                "family": s.family,
                "split": s.split,
                "source_scenario_sha256": scene["source_scenario_sha256"],
                "scene_sha256": scene["content_sha256"],
            }
            if export_dir is not None:
                manifest = export_scene(scene, Path(export_dir) / s.id)
                scene_entry["exported_assets"] = {
                    k: {"name": v["name"], "sha256": v["sha256"]}
                    for k, v in manifest["files"].items()
                }
            scenes_meta[s.id] = scene_entry

        tape = create_tape(s, spec["commands"], seed=spec["seed"])
        tapes_meta.append({
            "tape_id": spec["tape_id"],
            "scenario_id": s.id,
            "family": s.family,
            "split": s.split,
            "seed": spec["seed"],
            "steps": len(spec["commands"]),
            "expects_contact": spec["expects_contact"],
            "scene_sha256": tape["scene_sha256"],
            "tape_sha256": tape["tape_sha256"],
            "tape": tape,
        })

    payload = {
        "schema_version": EVALUATION_MANIFEST_SCHEMA,
        "pilot_baseline": PILOT_BASELINE,
        "model_alignment": MODEL_ALIGNMENT_SPEC,
        "criteria": DEFAULT_CRITERIA,
        "held_out_summary": {
            "total_tapes": len(tapes_meta),
            "expected_native_traces": len(tapes_meta) * 2,
            "families": sorted({t["family"] for t in tapes_meta}),
            "scenarios": sorted(scenes_meta.keys()),
            "split": "test",
        },
        "scenes": scenes_meta,
        "tapes": tapes_meta,
    }
    return {**payload, "manifest_sha256": digest(payload)}


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]


def evaluate_v06_release_gate(
    manifest: dict[str, Any],
    paired_runs: list[dict[str, Any]],
    *,
    reviewer_assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate 20+ held-out paired runs (40+ native traces) against the frozen evaluation manifest."""
    if manifest.get("schema_version") != EVALUATION_MANIFEST_SCHEMA:
        raise ValueError("unsupported evaluation manifest schema")
    expected_digest = digest({k: v for k, v in manifest.items() if k != "manifest_sha256"})
    if manifest.get("manifest_sha256") != expected_digest:
        raise ValueError("evaluation manifest checksum mismatch")

    criteria = manifest["criteria"]
    tapes_by_id = {entry["tape_id"]: entry for entry in manifest["tapes"]}
    runs_by_id = {entry["tape_id"]: entry for entry in paired_runs}

    if set(runs_by_id.keys()) != set(tapes_by_id.keys()):
        missing = sorted(set(tapes_by_id.keys()) - set(runs_by_id.keys()))
        extra = sorted(set(runs_by_id.keys()) - set(tapes_by_id.keys()))
        raise ValueError(f"paired run coverage mismatch: missing={missing}, extra={extra}")

    per_run: list[dict[str, Any]] = []
    failed_runs: list[dict[str, Any]] = []
    all_rmses: list[float] = []
    all_p90s: list[float] = []
    all_maxs: list[float] = []
    max_timegrid_err = 0.0
    total_samples = 0
    total_missing_left = 0
    total_missing_right = 0
    total_contact_count_disagree = 0
    total_contact_state_disagree = 0

    for tape_entry in manifest["tapes"]:
        tid = tape_entry["tape_id"]
        tape = tape_entry["tape"]
        s = load_scenario(tape_entry["scenario_id"])
        run = runs_by_id[tid]

        if run.get("error"):
            fail_info = {"tape_id": tid, "scenario_id": s.id, "family": s.family, "reason": str(run["error"])}
            failed_runs.append(fail_info)
            per_run.append({**fail_info, "passed": False})
            continue

        left_trace = run["mujoco"]["trace"]
        right_trace = run["isaaclab"]["trace"]
        left_check = validate_execution(s, tape, left_trace)
        right_check = validate_execution(s, tape, right_trace)
        paired = paired_physics_report(
            s, tape, left_trace, right_trace, max_position_rmse_m=criteria["max_position_rmse_m"]
        )

        lsamples = left_trace["samples"]
        rsamples = right_trace["samples"]
        missing_l = sum(1 for p in lsamples if p["contacts"] is None)
        missing_r = sum(1 for p in rsamples if p["contacts"] is None)
        observed_l = [p["contacts"] for p in lsamples]
        observed_r = [p["contacts"] for p in rsamples]
        state_disagree = sum(
            (a > 0) != (b > 0)
            for a, b in zip(observed_l, observed_r)
            if a is not None and b is not None
        )
        observed_contact_l = any((c or 0) > 0 for c in observed_l)
        observed_contact_r = any((c or 0) > 0 for c in observed_r)

        reasons: list[str] = []
        if not (left_check["tape_matches"] and right_check["tape_matches"]):
            reasons.append("control_tape_mismatch")
        if paired["position_rmse_m"] > criteria["max_position_rmse_m"]:
            reasons.append(f"position_rmse_m={paired['position_rmse_m']} > {criteria['max_position_rmse_m']}")
        if paired["position_p90_m"] > criteria["max_position_p90_m"]:
            reasons.append(f"position_p90_m={paired['position_p90_m']} > {criteria['max_position_p90_m']}")
        if paired["position_max_m"] > criteria["max_position_max_m"]:
            reasons.append(f"position_max_m={paired['position_max_m']} > {criteria['max_position_max_m']}")
        if paired["control_timegrid_max_error_s"] > criteria["max_control_timegrid_error_s"]:
            reasons.append("timegrid_error_exceeded")
        if criteria["require_contacts_comparable"] and not paired["contacts_comparable"]:
            reasons.append(f"contacts_not_comparable (missing_l={missing_l}, missing_r={missing_r})")
        state_disagree_rate = state_disagree / len(lsamples)
        if state_disagree_rate > criteria["max_contact_state_disagreement_rate"]:
            reasons.append(f"contact_state_disagreement_rate={state_disagree_rate:.4f}")
        if tape_entry["expects_contact"] and not (observed_contact_l and observed_contact_r):
            reasons.append("expected_contact_not_observed_in_both_engines")

        passed = len(reasons) == 0
        row = {
            "tape_id": tid,
            "scenario_id": s.id,
            "family": s.family,
            "split": s.split,
            "tape_sha256": tape["tape_sha256"],
            "samples": paired["samples"],
            "position_rmse_m": paired["position_rmse_m"],
            "position_p90_m": paired["position_p90_m"],
            "position_max_m": paired["position_max_m"],
            "control_timegrid_max_error_s": paired["control_timegrid_max_error_s"],
            "contact_observed_samples": paired["contact_observed_samples"],
            "missing_contacts_left": missing_l,
            "missing_contacts_right": missing_r,
            "contact_count_disagreement_samples": paired["contact_count_disagreement_samples"],
            "contact_state_disagreement_samples": state_disagree,
            "observed_contact_left": observed_contact_l,
            "observed_contact_right": observed_contact_r,
            "mujoco_sample_chain_sha256": left_trace["manifest"]["sample_chain_sha256"],
            "isaaclab_sample_chain_sha256": right_trace["manifest"]["sample_chain_sha256"],
            "passed": passed,
            "failure_reasons": reasons,
        }
        per_run.append(row)
        if not passed:
            failed_runs.append({"tape_id": tid, "scenario_id": s.id, "family": s.family, "reasons": reasons})

        all_rmses.append(paired["position_rmse_m"])
        all_p90s.append(paired["position_p90_m"])
        all_maxs.append(paired["position_max_m"])
        max_timegrid_err = max(max_timegrid_err, paired["control_timegrid_max_error_s"])
        total_samples += paired["samples"]
        total_missing_left += missing_l
        total_missing_right += missing_r
        total_contact_count_disagree += paired["contact_count_disagreement_samples"]
        total_contact_state_disagree += state_disagree

    by_family: dict[str, Any] = {}
    for fam in sorted({r["family"] for r in per_run}):
        frows = [r for r in per_run if r["family"] == fam and "position_rmse_m" in r]
        by_family[fam] = {
            "tapes": len([r for r in per_run if r["family"] == fam]),
            "passed": len([r for r in per_run if r["family"] == fam and r["passed"]]),
            "mean_rmse_m": round(sum(r["position_rmse_m"] for r in frows) / len(frows), 8) if frows else None,
            "max_rmse_m": round(max(r["position_rmse_m"] for r in frows), 8) if frows else None,
            "max_p90_m": round(max(r["position_p90_m"] for r in frows), 8) if frows else None,
            "max_error_m": round(max(r["position_max_m"] for r in frows), 8) if frows else None,
        }

    gate_passed = (
        len(per_run) >= 20
        and len(failed_runs) <= criteria["max_failed_runs"]
        and len(by_family) >= 2
    )

    return {
        "schema_version": RELEASE_GATE_REPORT_SCHEMA,
        "evaluation_manifest_sha256": manifest["manifest_sha256"],
        "pilot_baseline_preserved": manifest["pilot_baseline"],
        "gate_passed": gate_passed,
        "summary": {
            "total_paired_runs": len(per_run),
            "total_native_traces": len(per_run) * 2,
            "passed_runs": len(per_run) - len(failed_runs),
            "failed_run_count": len(failed_runs),
            "task_families": sorted(by_family.keys()),
            "total_samples": total_samples,
            "mean_position_rmse_m": round(sum(all_rmses) / len(all_rmses), 8) if all_rmses else None,
            "max_position_rmse_m": round(max(all_rmses), 8) if all_rmses else None,
            "p90_of_run_rmses_m": round(_percentile(all_rmses, 0.9), 8) if all_rmses else None,
            "max_position_p90_m": round(max(all_p90s), 8) if all_p90s else None,
            "max_position_error_m": round(max(all_maxs), 8) if all_maxs else None,
            "max_control_timegrid_error_s": max_timegrid_err,
            "missing_contact_observations_left": total_missing_left,
            "missing_contact_observations_right": total_missing_right,
            "contact_count_disagreement_samples": total_contact_count_disagree,
            "contact_state_disagreement_samples": total_contact_state_disagree,
        },
        "by_family": by_family,
        "failed_runs": failed_runs,
        "per_run": per_run,
        "independent_reviewer_assessment": reviewer_assessment or {
            "status": "pending_independent_review",
        },
        "eligible_for_physics_equivalence_claim": False,
        "independently_attested_ground_truth": False,
        "scope": "v0.6 held-out cross-engine discrepancy gate on uncalibrated planar surrogate; not hardware calibration or SOTA",
    }
