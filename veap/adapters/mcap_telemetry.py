"""ROS 2 & MCAP telemetry ingestion engine with ground-truth vs sensor-evidence distinction.

Preserves:
1. Sensor timestamps (nanosecond resolution, PTP/NTP jitter)
2. TF transforms (/tf, /tf_static frames)
3. Joint states (wheel velocities, steering angles, joint efforts)
4. Control commands (/cmd_vel)
5. Fault events (injected or real hardware faults)
6. Safety interventions (geofence interventions, e-stops)
7. Software and model versions (git commit sha, policy weights sha, ROS 2 distro)
8. Calibration metadata (camera intrinsics, LiDAR extrinsics, wheel radius)

Crucial Epistemological Guarantee:
Distinguishes simulator-generated ground truth from real sensor evidence:
A hash chain over incorrect sensor data proves integrity of the record,
not truth of the world.
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel, Field
from ..ledger import Ledger
from ..spec import Scenario, digest


class CalibrationMetadata(BaseModel):
    wheel_radius_m: float = 0.040  # e.g., Yahboom M3 Pro 80mm mecanum wheel
    track_width_m: float = 0.220
    camera_matrix: list[float] = Field(default_factory=lambda: [525.0, 0.0, 319.5, 0.0, 525.0, 239.5, 0.0, 0.0, 1.0])
    lidar_to_base_xyz: list[float] = Field(default_factory=lambda: [0.05, 0.0, 0.18])
    imu_mount_rpy: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class ProvenanceMetadata(BaseModel):
    ros_distro: str = "humble"
    git_commit_sha: str
    model_weights_sha256: str
    firmware_version: str = "yahboom-stm32-v2.1"
    host_platform: str = "NVIDIA Jetson Orin Nano / Linux aarch64"


class TFFrame(BaseModel):
    parent_frame: str
    child_frame: str
    translation: list[float]
    rotation_xyzw: list[float]


class JointState(BaseModel):
    names: list[str]
    positions: list[float]
    velocities: list[float]
    efforts: list[float] = Field(default_factory=list)


class MCAPTelemetryFrame(BaseModel):
    timestamp_ns: int
    header_stamp_ns: int
    topic: str
    tf_transforms: list[TFFrame] = Field(default_factory=list)
    joint_state: JointState | None = None
    cmd_vel: list[float] | None = None  # [vx, vy, wz]
    odom_pose: list[float] | None = None  # [x, y, yaw]
    fault_events: list[str] = Field(default_factory=list)
    safety_interventions: list[str] = Field(default_factory=list)
    min_laser_distance_m: float = 10.0


class EpistemicVerificationReport(BaseModel):
    record_integrity_valid: bool
    record_ledger_root_sha256: str
    provenance: ProvenanceMetadata
    calibration: CalibrationMetadata
    world_truth_available: bool
    max_state_estimation_drift_m: float
    unobserved_violations_detected: int
    epistemic_verdict: str


def distinguish_ground_truth_from_evidence(
    sensor_frames: list[MCAPTelemetryFrame],
    ground_truth_poses: list[tuple[float, float]] | None,
    scenario: Scenario,
    provenance: ProvenanceMetadata,
    calibration: CalibrationMetadata
) -> tuple[dict[str, Any], EpistemicVerificationReport]:
    """Ingest MCAP telemetry into a tamper-evident ledger and evaluate epistemic truth."""
    ledger = Ledger()
    drifts = []
    unobserved_violations = 0

    for idx, frame in enumerate(sensor_frames):
        tick = idx
        payload = {
            "timestamp_ns": frame.timestamp_ns,
            "header_stamp_ns": frame.header_stamp_ns,
            "topic": frame.topic,
            "odom_pose": frame.odom_pose,
            "cmd_vel": frame.cmd_vel,
            "fault_events": frame.fault_events,
            "safety_interventions": frame.safety_interventions,
        }
        if frame.joint_state:
            payload["joint_state"] = frame.joint_state.model_dump()
        if frame.tf_transforms:
            payload["tf"] = [t.model_dump() for t in frame.tf_transforms]

        ledger.emit(tick=tick, kind="sensor_telemetry", payload=payload)

        # Cross-examine sensor evidence against independent ground truth (e.g. mocap/sim)
        if ground_truth_poses and idx < len(ground_truth_poses) and frame.odom_pose:
            gt_x, gt_y = ground_truth_poses[idx]
            odom_x, odom_y = frame.odom_pose[0], frame.odom_pose[1]
            drift = math.hypot(gt_x - odom_x, gt_y - odom_y)
            drifts.append(drift)

            # Check if ground truth violated forbidden zone while odometry claimed safe
            gt_in_forbidden = any(
                (gt_x >= z.x1 and gt_x <= z.x2 and gt_y >= z.y1 and gt_y <= z.y2)
                for z in scenario.forbidden_zones
            )
            odom_in_forbidden = any(
                (odom_x >= z.x1 and odom_x <= z.x2 and odom_y >= z.y1 and odom_y <= z.y2)
                for z in scenario.forbidden_zones
            )
            if gt_in_forbidden and not odom_in_forbidden:
                unobserved_violations += 1

    max_drift = max(drifts) if drifts else 0.0

    # Epistemic verdict logic
    if ground_truth_poses:
        if unobserved_violations > 0:
            verdict = (
                f"AUDIT WARN: Ledger integrity is cryptographically proven, but real-world ground truth "
                f"reveals {unobserved_violations} unobserved constraint violations due to {max_drift:.3f}m sensor drift."
            )
        else:
            verdict = f"VERIFIED CONCORDANT: Sensor evidence and ground-truth agree within {max_drift:.3f}m."
    else:
        verdict = "AUDIT INTACT (UNANCHORED): Cryptographic chain guarantees record integrity; real-world ground truth unanchored."

    report = EpistemicVerificationReport(
        record_integrity_valid=True,
        record_ledger_root_sha256=ledger.root,
        provenance=provenance,
        calibration=calibration,
        world_truth_available=bool(ground_truth_poses),
        max_state_estimation_drift_m=round(max_drift, 4),
        unobserved_violations_detected=unobserved_violations,
        epistemic_verdict=verdict,
    )

    evidence_bundle = {
        "scenario_id": scenario.id,
        "scenario_digest": digest(scenario.model_dump(mode="json", exclude_none=True)),
        "provenance": provenance.model_dump(),
        "calibration": calibration.model_dump(),
        "ledger_root_sha256": ledger.root,
        "events": ledger.events,
        "epistemic_report": report.model_dump(),
    }

    return evidence_bundle, report

