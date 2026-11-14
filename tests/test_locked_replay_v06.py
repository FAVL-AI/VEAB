"""Offline and retained-trace controls for locked cross-engine replay."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import pytest

from veap.spec import canonical, digest, load_scenario
from veap.simulation.locked_replay import (
    DIAGNOSTIC_SCHEMA,
    TAPE_SCHEMA,
    create_tape,
    diagnose_paired_replay,
    paired_physics_report,
    standard_tape,
    validate_execution,
    validate_tape,
)
from veap.simulation.telemetry import PhysicsRecorder, make_sample
from veap.simulation.isaaclab_locked_collector import IsaacLabTapeCollector
from veap.simulation.native_locked_runner import run_mujoco_tape

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TAPE_SHA256 = "ba0d2388943e76304dc21435b5ac2c1cd434258e75b3e90daece749bddd62d6e"


def scenario():
    return load_scenario("warehouse-transfer")


def synthetic_trace(tape, *, engine="mujoco", x_shift=0.0, contact=None):
    s = scenario()
    r = PhysicsRecorder(s, engine, "synthetic-fixture-not-native", tape["scene_sha256"], seed=tape["seed"])
    sx, sy = s.start.x, s.start.y
    r.append(make_sample(0, 0, [sx, sy, 0.16]))
    for i, cmd in enumerate(tape["commands_vx_vy_yaw"], 1):
        x = sx + x_shift + 0.01 * i
        r.append(make_sample(i, s.dt * i, [x, sy, 0.16], [0.05, 0, 0], command=cmd, contacts=contact))
    return r.finish("unknown")


def test_committed_v06_control_tape_loads_unchanged():
    tape_path = ROOT / "artifacts" / "research" / "v06-control-tape.json"
    tape = json.loads(tape_path.read_text(encoding="utf-8"))
    s = scenario()
    assert tape["schema_version"] == "veab-control-tape/1"
    assert tape["schema_version"] == TAPE_SCHEMA
    assert tape["tape_sha256"] == CANONICAL_TAPE_SHA256
    assert tape["calibration_status"] == "unmeasured_research_surrogate"
    validate_tape(s, tape)
    assert tape == standard_tape(s, seed=17, steps=24)


def test_tape_reproducible_and_referentially_bound():
    s = scenario()
    t = standard_tape(s, seed=17, steps=16)
    validate_tape(s, t)
    assert t == standard_tape(s, seed=17, steps=16)
    assert t["calibration_status"] == "unmeasured_research_surrogate"
    assert t["scene_sha256"]
    assert t["tape_sha256"]
    assert len(t["commands_vx_vy_yaw"]) == 16


def test_tape_rejects_invalid_commands_and_metadata():
    s = scenario()
    bad = [[s.max_speed * 2, 0, 0]]
    with pytest.raises(ValueError, match="velocity limit"):
        create_tape(s, bad)
    with pytest.raises(ValueError, match="finite"):
        create_tape(s, [[math.nan, 0, 0]])
    with pytest.raises(ValueError, match="yaw rate"):
        create_tape(s, [[0, 0, 3]])
    with pytest.raises(ValueError, match="command requires"):
        create_tape(s, [[0, 0]])
    t = standard_tape(s)
    for key, value in [
        ("scene_sha256", "f" * 64),
        ("coordinate_frame", "NED"),
        ("calibration_status", "calibrated"),
        ("seed", -1),
        ("dt_s", s.dt / 2),
        ("tape_sha256", "0" * 64),
    ]:
        fake = copy.deepcopy(t)
        fake[key] = value
        with pytest.raises(ValueError):
            validate_tape(s, fake)
    fake = copy.deepcopy(t)
    fake["commands_vx_vy_yaw"][0][0] = 0.8
    with pytest.raises(ValueError):
        validate_tape(s, fake)


def test_locked_execution_accepts_synthetic_fixture_without_authenticity_claim():
    t = standard_tape(scenario(), steps=12)
    trace = synthetic_trace(t)
    report = validate_execution(scenario(), t, trace)
    assert report["tape_matches"]
    assert report["physical_source_authenticity"] == "not_established"
    assert report["trace_integrity"]


def test_missing_and_changed_action_rejected():
    t = standard_tape(scenario(), steps=12)
    trace = synthetic_trace(t)
    forged = copy.deepcopy(trace)
    forged["samples"].pop()
    forged["manifest"]["sample_count"] = len(forged["samples"])
    root = "0" * 64
    for s in forged["samples"]:
        root = hashlib.sha256(bytes.fromhex(root) + canonical(s)).hexdigest()
    forged["manifest"]["sample_chain_sha256"] = root
    forged["manifest"]["manifest_sha256"] = digest({k: v for k, v in forged["manifest"].items() if k != "manifest_sha256"})
    with pytest.raises(ValueError, match="missing or extra"):
        validate_execution(scenario(), t, forged)
    altered = copy.deepcopy(trace)
    altered["samples"][3]["command_vx_vy_yaw"] = [0.0, 0.0, 0.0]
    root = "0" * 64
    for s in altered["samples"]:
        root = hashlib.sha256(bytes.fromhex(root) + canonical(s)).hexdigest()
    altered["manifest"]["sample_chain_sha256"] = root
    altered["manifest"]["manifest_sha256"] = digest({k: v for k, v in altered["manifest"].items() if k != "manifest_sha256"})
    with pytest.raises(ValueError, match="command differs"):
        validate_execution(scenario(), t, altered)


def test_reordered_commands_detected_in_tape_and_execution():
    s = scenario()
    t = standard_tape(s, steps=12)
    reordered_tape = copy.deepcopy(t)
    reordered_tape["commands_vx_vy_yaw"][0], reordered_tape["commands_vx_vy_yaw"][4] = (
        reordered_tape["commands_vx_vy_yaw"][4],
        reordered_tape["commands_vx_vy_yaw"][0],
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        validate_tape(s, reordered_tape)

    trace = synthetic_trace(t)
    reordered_trace = copy.deepcopy(trace)
    reordered_trace["samples"][1]["command_vx_vy_yaw"], reordered_trace["samples"][5]["command_vx_vy_yaw"] = (
        reordered_trace["samples"][5]["command_vx_vy_yaw"],
        reordered_trace["samples"][1]["command_vx_vy_yaw"],
    )
    root = "0" * 64
    for sample in reordered_trace["samples"]:
        root = hashlib.sha256(bytes.fromhex(root) + canonical(sample)).hexdigest()
    reordered_trace["manifest"]["sample_chain_sha256"] = root
    reordered_trace["manifest"]["manifest_sha256"] = digest(
        {k: v for k, v in reordered_trace["manifest"].items() if k != "manifest_sha256"}
    )
    with pytest.raises(ValueError, match="command differs from frozen tape"):
        validate_execution(s, t, reordered_trace)


def test_paired_comparison_zero_error_remains_unvalidated():
    t = standard_tape(scenario(), steps=12)
    a = synthetic_trace(t, engine="mujoco", contact=None)
    b = synthetic_trace(t, engine="isaaclab", contact=None)
    result = paired_physics_report(scenario(), t, a, b)
    assert result["position_rmse_m"] == 0
    assert result["matched_controls"]
    assert not result["contacts_comparable"]
    assert result["calibration_status"] == "unmeasured_research_surrogate"
    assert result["eligible_for_physics_equivalence_claim"] is False
    assert not result["independently_attested_ground_truth"]


def test_paired_comparison_detects_divergence_and_wrong_engines():
    t = standard_tape(scenario(), steps=12)
    a = synthetic_trace(t, engine="mujoco", contact=0)
    b = synthetic_trace(t, engine="isaaclab", x_shift=0.2, contact=1)
    r = paired_physics_report(scenario(), t, a, b, max_position_rmse_m=0.1)
    assert r["position_rmse_m"] > 0.1
    assert r["position_p90_m"] > 0.1
    assert not r["position_rmse_within_target"]
    assert r["contact_count_disagreement_samples"] == 12
    assert r["calibration_status"] == "unmeasured_research_surrogate"
    with pytest.raises(ValueError, match="distinct engines"):
        paired_physics_report(scenario(), t, a, a)


def test_isaac_bridge_uses_native_observation_contract_not_fabricated_engine():
    s = scenario()
    t = standard_tape(s, steps=4)
    recorder = IsaacLabTapeCollector(s, t, engine_version="fixture")
    recorder.append_state(
        time_s=0,
        position_xyz_m=[s.start.x, s.start.y, 0.16],
        quaternion_xyzw=[0, 0, 0, 1],
        velocity_xyz_m_s=[0, 0, 0],
    )
    for tick in range(1, 5):
        recorder.append_state(
            time_s=tick * s.dt,
            position_xyz_m=[s.start.x + 0.01 * tick, s.start.y, 0.16],
            quaternion_xyzw=[0, 0, 0, 1],
            velocity_xyz_m_s=[0.05, 0, 0],
        )
    result = recorder.finish()
    assert result["control_contract"]["tape_matches"]
    assert not result["native_execution_asserted_by_veab"]
    assert result["trace"]["manifest"]["engine"] == "isaaclab"


def test_native_mujoco_never_falls_back_to_toy_world(tmp_path):
    import importlib.util

    if importlib.util.find_spec("mujoco") is None:
        with pytest.raises(RuntimeError, match="Native MuJoCo is required"):
            run_mujoco_tape(scenario(), standard_tape(scenario(), steps=4), tmp_path)
    else:
        pytest.skip("This is an offline missing-dependency control, not the native physics integration suite")


def test_retained_workstation_mujoco_and_isaaclab_traces_match_committed_tape():
    s = scenario()
    tape = json.loads((ROOT / "artifacts" / "research" / "v06-control-tape.json").read_text(encoding="utf-8"))
    mj_bundle = json.loads((ROOT / "artifacts" / "research" / "v06-mujoco-locked-replay.json").read_text(encoding="utf-8"))
    is_bundle = json.loads((ROOT / "artifacts" / "research" / "v06-isaaclab-locked-replay.json").read_text(encoding="utf-8"))
    paired_saved = json.loads((ROOT / "artifacts" / "research" / "v06-paired-physics-report.json").read_text(encoding="utf-8"))

    assert mj_bundle["tape_sha256"] == CANONICAL_TAPE_SHA256
    assert is_bundle["tape_sha256"] == CANONICAL_TAPE_SHA256

    mj_check = validate_execution(s, tape, mj_bundle["trace"])
    is_check = validate_execution(s, tape, is_bundle["trace"])
    assert mj_check["tape_matches"] is True
    assert is_check["tape_matches"] is True
    assert mj_check["samples"] == len(tape["commands_vx_vy_yaw"]) + 1 == 25
    assert is_check["samples"] == len(tape["commands_vx_vy_yaw"]) + 1 == 25
    assert mj_check["engine"] == "mujoco"
    assert is_check["engine"] == "isaaclab"

    paired = paired_physics_report(s, tape, mj_bundle["trace"], is_bundle["trace"])
    assert paired == paired_saved
    assert paired["tape_sha256"] == CANONICAL_TAPE_SHA256
    assert paired["matched_controls"] is True
    assert paired["samples"] == 25
    assert paired["calibration_status"] == "unmeasured_research_surrogate"
    assert paired["eligible_for_physics_equivalence_claim"] is False
    assert paired["independently_attested_ground_truth"] is False


def test_per_tick_diagnostic_localizes_pilot_divergence_and_cli(tmp_path):
    from scripts.veap_v06 import main as veap_v06_main

    s = scenario()
    tape = json.loads((ROOT / "artifacts" / "research" / "v06-control-tape.json").read_text(encoding="utf-8"))
    mj_bundle = json.loads((ROOT / "artifacts" / "research" / "v06-mujoco-locked-replay.json").read_text(encoding="utf-8"))
    is_bundle = json.loads((ROOT / "artifacts" / "research" / "v06-isaaclab-locked-replay.json").read_text(encoding="utf-8"))
    diag_saved = json.loads((ROOT / "artifacts" / "research" / "v06-pilot-per-tick-diagnostic.json").read_text(encoding="utf-8"))

    diag = diagnose_paired_replay(
        s,
        tape,
        mj_bundle["trace"],
        is_bundle["trace"],
        repeat_left=mj_bundle["trace"],
        repeat_right=is_bundle["trace"],
    )
    assert diag["schema_version"] == DIAGNOSTIC_SCHEMA
    assert diag["tape_sha256"] == CANONICAL_TAPE_SHA256
    assert len(diag["ticks"]) == 25
    loc = diag["localization"]
    assert loc["initial_pose_diverged_at_tick_0"] is True
    assert loc["tick_0_position_error_m"] == pytest.approx(0.0028649, abs=1e-7)
    assert loc["tick_0_planar_error_m"] == 0.0
    assert loc["tick_0_vertical_delta_m"] == pytest.approx(0.0028649, abs=1e-7)
    assert loc["tick_0_velocity_error_m_s"] == pytest.approx(0.1903532, abs=1e-7)
    assert loc["first_position_divergence_tick"] == 0
    assert loc["first_planar_divergence_tick"] == 2
    assert loc["first_velocity_divergence_tick"] == 0
    assert loc["first_planar_velocity_divergence_tick"] == 1
    assert loc["first_target_exceedance_tick"] == 5
    assert loc["peak_position_error_tick"] == 13
    assert loc["peak_position_error_m"] == pytest.approx(0.27508361, abs=1e-7)
    assert loc["commanded_motion_ticks"] == 18
    assert loc["stalled_planar_motion_ticks_left"] == []
    assert loc["stalled_planar_motion_ticks_right"] == list(range(2, 19))
    assert loc["contact_observation_counts"]["missing_right"] == 25

    rep = diag["repeatability"]
    assert rep["left"]["repeats_deterministically"] is True
    assert rep["right"]["repeats_deterministically"] is True
    assert rep["divergence_repeats_identically"] is True
    assert diag == diag_saved

    out_file = tmp_path / "cli-diagnostic.json"
    rc = veap_v06_main([
        "diagnose",
        "--tape", str(ROOT / "artifacts/research/v06-control-tape.json"),
        "--left", str(ROOT / "artifacts/research/v06-mujoco-locked-replay.json"),
        "--right", str(ROOT / "artifacts/research/v06-isaaclab-locked-replay.json"),
        "--repeat-left", str(ROOT / "artifacts/research/v06-mujoco-locked-replay.json"),
        "--repeat-right", str(ROOT / "artifacts/research/v06-isaaclab-locked-replay.json"),
        "--out", str(out_file),
    ])
    assert rc == 0
    assert json.loads(out_file.read_text(encoding="utf-8")) == diag_saved


def test_frozen_v06_evaluation_manifest_and_pilot_preservation():
    from veap.simulation.v06_gate import EVALUATION_MANIFEST_SCHEMA, build_v06_evaluation_manifest

    manifest_saved = json.loads((ROOT / "artifacts" / "research" / "v06-evaluation-manifest.json").read_text(encoding="utf-8"))
    assert manifest_saved["schema_version"] == EVALUATION_MANIFEST_SCHEMA
    assert manifest_saved["held_out_summary"]["total_tapes"] == 20
    assert manifest_saved["held_out_summary"]["expected_native_traces"] == 40
    assert manifest_saved["held_out_summary"]["split"] == "test"
    assert set(manifest_saved["held_out_summary"]["families"]) >= {"navigation", "inspection"}
    assert manifest_saved["pilot_baseline"]["position_rmse_m"] == pytest.approx(0.20182817, abs=1e-8)
    assert manifest_saved["criteria"]["max_position_rmse_m"] == 0.100

    rebuilt = build_v06_evaluation_manifest()
    assert rebuilt["manifest_sha256"] != ""
    assert [t["tape_sha256"] for t in rebuilt["tapes"]] == [t["tape_sha256"] for t in manifest_saved["tapes"]]


def test_stage2_contact_verification_distinguishes_zero_contact_and_missing():
    s2 = json.loads((ROOT / "artifacts" / "research" / "v06-stage2-contact-verification.json").read_text(encoding="utf-8"))
    assert s2["zero_contact_observed_example"]["isaaclab_contacts_unique"] == [0]
    assert any(c > 0 for c in s2["contact_observed_example"]["isaaclab_contacts"])
    assert any(c == 0 for c in s2["contact_observed_example"]["isaaclab_contacts"])
    assert s2["missing_observation_example"]["contact_sensor_enabled"] is False
    assert s2["missing_observation_example"]["isaaclab_contacts_unique_is_null"] is True


def test_heldout_40_trace_release_gate_reproducibility():
    from veap.simulation.v06_gate import RELEASE_GATE_REPORT_SCHEMA, evaluate_v06_release_gate

    manifest = json.loads((ROOT / "artifacts" / "research" / "v06-evaluation-manifest.json").read_text(encoding="utf-8"))
    saved_report = json.loads((ROOT / "artifacts" / "research" / "v06-release-gate-report.json").read_text(encoding="utf-8"))
    traces_root = ROOT / "artifacts" / "research" / "v06-heldout-traces"

    paired_runs = []
    for entry in manifest["tapes"]:
        tid = entry["tape_id"]
        paired_runs.append({
            "tape_id": tid,
            "mujoco": json.loads((traces_root / "mujoco" / f"{tid}.json").read_text(encoding="utf-8")),
            "isaaclab": json.loads((traces_root / "isaaclab" / f"{tid}.json").read_text(encoding="utf-8")),
        })

    report = evaluate_v06_release_gate(
        manifest,
        paired_runs,
        reviewer_assessment=saved_report.get("independent_reviewer_assessment"),
    )
    assert report["schema_version"] == RELEASE_GATE_REPORT_SCHEMA
    assert report["summary"]["total_paired_runs"] == 20
    assert report["summary"]["total_native_traces"] == 40
    assert report["summary"]["missing_contact_observations_left"] == 0
    assert report["summary"]["missing_contact_observations_right"] == 0
    assert report["summary"]["max_control_timegrid_error_s"] == 0.0
    assert report["summary"]["max_position_rmse_m"] < 0.100
    assert [r["tape_id"] for r in report["failed_runs"]] == ["insp-07", "insp-08"]
    assert report["eligible_for_physics_equivalence_claim"] is False
    assert report["independently_attested_ground_truth"] is False
    assert report == saved_report


def test_isaaclab_native_runner_never_falls_back_to_toy_world(tmp_path):
    import importlib.util
    from veap.simulation.isaaclab_native_runner import run_isaaclab_tape

    if importlib.util.find_spec("isaaclab") is None:
        with pytest.raises(RuntimeError, match="Native Isaac Lab is required"):
            run_isaaclab_tape(scenario(), standard_tape(scenario(), steps=4), tmp_path)
    else:
        pytest.skip("This is an offline missing-dependency control, not the native Isaac Lab suite")
