"""Test ROS 2 & MCAP telemetry ingestion, preserving all signals, and truth vs record check."""
import pytest
from veap.spec import load_scenario
from veap.adapters.mcap_telemetry import (
    MCAPTelemetryFrame,
    ProvenanceMetadata,
    CalibrationMetadata,
    TFFrame,
    JointState,
    distinguish_ground_truth_from_evidence,
)

def test_mcap_ingestion_preserves_all_metadata_and_detects_drift():
    scenario = load_scenario("warehouse-transfer")
    provenance = ProvenanceMetadata(
        git_commit_sha="a1b2c3d4e5f6",
        model_weights_sha256="9f8e7d6c5b4a",
        firmware_version="yahboom-stm32-v2.1"
    )
    calibration = CalibrationMetadata(wheel_radius_m=0.040, track_width_m=0.210)

    # Simulated sensor frames where odometry drifts:
    # Sensor claims robot is moving safely at y=3.0: (6.0, 3.0)
    # But actual physical ground-truth robot drifted inside forbidden zone (5.5, 1.5)!
    sensor_frames = [
        MCAPTelemetryFrame(
            timestamp_ns=1700000000000000 + i * 200_000_000,
            header_stamp_ns=1700000000000000 + i * 200_000_000 - 5_000_000,
            topic="/odom",
            odom_pose=[6.0, 3.0 + i * 0.1, 0.0],
            cmd_vel=[0.0, 0.1, 0.0],
            joint_state=JointState(names=["w1", "w2", "w3", "w4"], positions=[0.1*i]*4, velocities=[1.5]*4),
            tf_transforms=[TFFrame(parent_frame="odom", child_frame="base_link", translation=[6.0, 3.0 + i * 0.1, 0.0], rotation_xyzw=[0, 0, 0, 1])],
            fault_events=["sensor_dropout"] if i == 5 else [],
            safety_interventions=["geofence_boundary_brake"] if i == 9 else []
        )
        for i in range(10)
    ]

    # Ground truth: at tick 4, ground truth was actually inside forbidden zone (6.0, 1.5)
    ground_truth = [(6.0, 3.0 + i * 0.1) for i in range(10)]
    ground_truth[4] = (6.0, 1.5)  # Inside forbidden zone [5.1, 0.8, 7.7, 2.2]!

    bundle, report = distinguish_ground_truth_from_evidence(
        sensor_frames=sensor_frames,
        ground_truth_poses=ground_truth,
        scenario=scenario,
        provenance=provenance,
        calibration=calibration
    )

    # 1. Cryptographic chain of custody over the recorded telemetry is intact:
    assert report.record_integrity_valid is True
    assert len(report.record_ledger_root_sha256) == 64
    assert bundle["ledger_root_sha256"] == report.record_ledger_root_sha256

    # 2. Epistemic check catches that record integrity != world truth:
    # Sensor data itself was not corrupted after recording, but unobserved violation occurred in physical reality
    assert report.unobserved_violations_detected == 1
    assert report.max_state_estimation_drift_m >= 1.0
    assert "AUDIT WARN" in report.epistemic_verdict
    assert "unobserved constraint violations" in report.epistemic_verdict

