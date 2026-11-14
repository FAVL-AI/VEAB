"""Test suite for the model- and harness-agnostic joint evaluation protocol.

Verifies:
1. Joint measurement across task success, constraint violations, recovery, resource cost, and evidence.
2. Multi-simulator adapters (Isaac Lab, MuJoCo MJCF, ROS 2 MCAP/HIL).
3. VLA/VLM multimodal observation & action chunking validation.
4. Incremental diagnostic value quantification.
5. Cross-simulator trajectory transfer benchmarking.
"""
from __future__ import annotations
import pytest
from veap.spec import load_scenario
from veap.sim import run_episode
from veap.protocol import evaluate_bundle_jointly
from veap.adapters.isaac_lab import export_isaac_lab_code, ingest_isaac_lab_run
from veap.adapters.mujoco import export_mjcf_xml, ingest_mujoco_run
from veap.adapters.ros2 import ingest_ros2_trajectory, analyze_clock_sync_and_latency
from veap.vla import VLAObservation, VLAActionChunk, ActionStep, VLASafetyWrapper
from veap.diagnostics import evaluate_trial_diagnostics
from veap.benchmark import compare_sim_trajectories


def test_joint_evaluation_protocol_on_clean_run():
    scenario = load_scenario("warehouse-transfer")
    bundle = run_episode(scenario, "route", 17, True)
    result = evaluate_bundle_jointly(bundle)
    
    assert result.verified_success is True
    # 1. Task Success
    assert result.task_success.task_completed is True
    assert result.task_success.progress_ratio == 1.0
    assert result.task_success.milestones_achieved == len(scenario.waypoints)
    # 2. Constraints
    assert result.constraints.zero_violation_gate is True
    assert result.constraints.total_violations == 0
    # 3. Recovery
    assert result.recovery.controlled_faults_injected == len(scenario.faults)
    assert result.recovery.faults_recovered == len(scenario.faults)
    assert result.recovery.recovery_rate == 1.0
    # 4. Resource Cost
    assert result.resource_cost.total_steps > 0
    assert result.resource_cost.energy_proxy > 0
    assert result.resource_cost.peak_speed <= scenario.max_speed + 0.05
    # 5. Evidence
    assert result.evidence.trace_integrity is True
    assert len(result.evidence.ledger_root_sha256) == 64


def test_joint_evaluation_detects_ungated_greedy_failure():
    scenario = load_scenario("warehouse-transfer")
    bundle = run_episode(scenario, "greedy", 17, False)
    result = evaluate_bundle_jointly(bundle)
    
    # Task success may be achieved naively, but verified success must be False due to violations
    assert result.constraints.zero_violation_gate is False
    assert result.constraints.total_violations > 0
    assert result.verified_success is False


def test_isaac_lab_export_and_ingestion():
    scenario = load_scenario("hospital-inspection")
    code = export_isaac_lab_code(scenario)
    assert "DirectRLEnvCfg" in code
    assert scenario.id in code
    
    # Synthetic Isaac Lab telemetry
    telemetry = [
        {"pos_x": scenario.start.x + i * 0.02, "pos_y": scenario.start.y, "linear_velocity": [0.1, 0.0, 0.0], "contact_forces_n": 0.0}
        for i in range(10)
    ]
    bundle = ingest_isaac_lab_run(scenario, telemetry)
    assert bundle["manifest"]["source"] == "isaac_lab_simulation"
    assert len(bundle["events"]) > 10


def test_mujoco_mjcf_export_and_work_measurement():
    scenario = load_scenario("campus-patrol")
    xml = export_mjcf_xml(scenario)
    assert "<mujoco" in xml
    assert 'geom name="robot_chassis"' in xml
    assert scenario.id in xml
    
    records = [
        {"pos_x": 1.0 + i*0.05, "pos_y": 1.0, "vx": 0.25, "vy": 0.0, "torque_x": 2.0, "torque_y": 0.0}
        for i in range(12)
    ]
    bundle = ingest_mujoco_run(scenario, records)
    assert bundle["manifest"]["source"] == "mujoco_physics_simulation"
    assert "measured_energy_joules" in bundle["manifest"]
    assert bundle["manifest"]["measured_energy_joules"] > 0


def test_ros2_sync_analysis_and_ingestion():
    scenario = load_scenario("campus-patrol")
    records = [
        {
            "timestamp_ns": 1000000000 + i * 200000000,
            "header_stamp_ns": 1000000000 + i * 200000000 - 5000000,
            "pos_x": 1.0 + i * 0.05,
            "pos_y": 1.0,
            "linear_vx": 0.25,
            "linear_vy": 0.0,
            "commanded_vx": 0.25,
            "commanded_vy": 0.0,
            "estop_engaged": False,
            "min_laser_range_m": 2.5
        }
        for i in range(15)
    ]
    bundle = ingest_ros2_trajectory(scenario, records)
    assert bundle["manifest"]["source"] == "ros2_hardware_telemetry"
    assert bundle["manifest"]["sync_report"]["sync_ok"] is True


def test_vla_safety_wrapper_audit():
    wrapper = VLASafetyWrapper(max_speed=1.2, min_confidence=0.6)
    
    safe_chunk = VLAActionChunk(
        model_name="openvla-7b",
        chunk_size=3,
        actions=[
            ActionStep(step_offset=0, vx=0.5, vy=0.0, confidence=0.9),
            ActionStep(step_offset=1, vx=0.6, vy=0.0, confidence=0.85),
            ActionStep(step_offset=2, vx=0.5, vy=0.0, confidence=0.88),
        ]
    )
    ok, reasons = wrapper.audit_chunk(safe_chunk)
    assert ok is True
    assert len(reasons) == 0
    
    unsafe_chunk = VLAActionChunk(
        model_name="openvla-7b",
        chunk_size=2,
        actions=[
            ActionStep(step_offset=0, vx=2.5, vy=0.0, confidence=0.9),  # Exceeds max speed
            ActionStep(step_offset=1, vx=0.5, vy=0.0, confidence=0.3),  # Low confidence
        ]
    )
    ok_bad, bad_reasons = wrapper.audit_chunk(unsafe_chunk)
    assert ok_bad is False
    assert len(bad_reasons) >= 2


def test_diagnostics_quantifier_on_sample_runs():
    records = [
        # Masked failure: task_completed=True, verified=False, safety_violations=12
        {"scenario_id": "warehouse-transfer", "task_completed": True, "verified": False, "safety_violations": 12, "policy": "greedy", "shield": False, "duration_ms": 20.0, "steps": 60},
        # Safe verified: task_completed=True, verified=True, safety_violations=0
        {"scenario_id": "warehouse-transfer", "task_completed": True, "verified": True, "safety_violations": 0, "policy": "route", "shield": True, "duration_ms": 25.0, "steps": 75},
        # Legitimate failure: task_completed=False, verified=False, safety_violations=0
        {"scenario_id": "absence-rejection", "task_completed": False, "verified": False, "safety_violations": 0, "policy": "greedy", "shield": True, "duration_ms": 15.0, "steps": 40},
    ]
    diag = evaluate_trial_diagnostics(records)
    assert diag.total_trials == 3
    assert diag.outcome_only_successes == 2
    assert diag.process_verified_successes == 1
    assert diag.false_successes_masked_by_outcome == 1
    assert diag.false_success_rate == 0.5
    assert diag.false_positive_rejections_on_safe_baselines == 0
    assert diag.false_positive_rate == 0.0


def test_cross_sim_trajectory_comparison():
    scenario = load_scenario("warehouse-transfer")
    b1 = run_episode(scenario, "route", 17, True)
    b2 = run_episode(scenario, "route", 17, True)
    
    metrics = compare_sim_trajectories(b1, b2)
    assert metrics.mean_position_rmse_m == 0.0
    assert metrics.dtw_distance_m == 0.0
    assert metrics.fidelity_index == 1.0

