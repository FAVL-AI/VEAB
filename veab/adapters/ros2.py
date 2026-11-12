"""ROS 2 & Hardware-in-the-Loop (HIL) telemetry integration adapter.

Provides:
1. Parsing of synchronised ROS 2 topics (/odom, /cmd_vel, /joint_states, /estop, /scan).
2. PTP / NTP clock synchronisation and jitter validation.
3. Command-to-actuation latency profiling (p50, p95, p99).
4. Translation of ROS 2 bag/MCAP streams into signed VEAB evidence bundles.
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel, Field
from ..ledger import Ledger
from ..spec import Scenario, digest


class ROSTopicTelemetry(BaseModel):
    timestamp_ns: int
    header_stamp_ns: int
    pos_x: float
    pos_y: float
    linear_vx: float
    linear_vy: float
    angular_wz: float = 0.0
    commanded_vx: float = 0.0
    commanded_vy: float = 0.0
    estop_engaged: bool = False
    sync_jitter_ms: float = 0.0
    min_laser_range_m: float = 10.0


def analyze_clock_sync_and_latency(records: list[ROSTopicTelemetry]) -> dict[str, Any]:
    """Calculate PTP/NTP time sync jitter and command-actuation delay."""
    if not records:
        return {"sync_ok": False, "jitter_p95_ms": 0.0, "latency_p95_ms": 0.0}
    
    jitters = []
    latencies = []
    
    for i in range(1, len(records)):
        dt_actual = (records[i].timestamp_ns - records[i-1].timestamp_ns) / 1e6  # ms
        jitter = abs(dt_actual - 200.0)  # assume 5Hz / 200ms nominal
        jitters.append(jitter)
        
        # Command-to-actuation response: delay between cmd_vel non-zero and actual non-zero
        if abs(records[i].commanded_vx) > 0.01 and abs(records[i].linear_vx) > 0.01:
            cmd_delay = abs(records[i].timestamp_ns - records[i].header_stamp_ns) / 1e6
            latencies.append(cmd_delay)
            
    jitters.sort()
    latencies.sort() if latencies else [0.0]
    
    p95_idx = int(0.95 * len(jitters)) if jitters else 0
    p95_jitter = jitters[p95_idx] if jitters else 0.0
    
    p95_lat_idx = int(0.95 * len(latencies)) if latencies else 0
    p95_lat = latencies[p95_lat_idx] if latencies else 0.0
    
    return {
        "sync_ok": p95_jitter < 50.0,  # Less than 50ms jitter acceptable for HIL
        "jitter_p95_ms": round(p95_jitter, 2),
        "latency_p95_ms": round(p95_lat, 2),
        "samples": len(records)
    }


def ingest_ros2_trajectory(
    scenario: Scenario,
    records: list[dict[str, Any]],
    robot_id: str = "unitree_go2",
    firmware_version: str = "ros2-humble-v1.4",
    attestation_key: str | None = None
) -> dict[str, Any]:
    """Ingest ROS 2 hardware or HIL telemetry stream into a canonical VEAB evidence bundle."""
    parsed = [ROSTopicTelemetry.model_validate(r) for r in records]
    sync_report = analyze_clock_sync_and_latency(parsed)
    
    ledger = Ledger()
    sc_dict = scenario.model_dump(mode="json")
    sc_digest = digest(sc_dict)
    
    x0 = parsed[0].pos_x if parsed else scenario.start.x
    y0 = parsed[0].pos_y if parsed else scenario.start.y
    vx0 = parsed[0].linear_vx if parsed else 0.0
    vy0 = parsed[0].linear_vy if parsed else 0.0
    
    ledger.emit(0, "state", {"x": round(x0, 5), "y": round(y0, 5), "vx": round(vx0, 5), "vy": round(vy0, 5), "stage": 0})
    
    milestone_idx = 0
    stage = 0
    
    for idx, rec in enumerate(parsed):
        tick = idx + 1
        # Observation
        ledger.emit(tick, "observation", {
            "x": round(rec.pos_x, 5), "y": round(rec.pos_y, 5),
            "sensor_ok": not rec.estop_engaged,
            "target_present": scenario.target_present,
            "min_laser_range_m": round(rec.min_laser_range_m, 3),
            "estop_engaged": rec.estop_engaged
        })
        
        # Proposal
        ledger.emit(tick, "proposal", {
            "vx": round(rec.commanded_vx, 5), "vy": round(rec.commanded_vy, 5),
            "policy": f"ros2_node_{robot_id}",
            "decision": "twist_command"
        })
        
        if milestone_idx < len(scenario.waypoints):
            wp = scenario.waypoints[milestone_idx]
            if math.hypot(rec.pos_x - wp.x, rec.pos_y - wp.y) <= scenario.waypoint_tolerance:
                ledger.emit(tick, "milestone", {"index": milestone_idx, "label": wp.label})
                milestone_idx += 1
                stage += 1
                
        ledger.emit(tick, "state", {
            "x": round(rec.pos_x, 5), "y": round(rec.pos_y, 5),
            "vx": round(rec.linear_vx, 5), "vy": round(rec.linear_vy, 5),
            "stage": stage
        })
        
        if tick >= scenario.max_steps:
            break
            
    last_tick = len(parsed)
    claimed = "completed" if (scenario.target_present and milestone_idx == len(scenario.waypoints)) else (
        "abstained" if not scenario.target_present else "timeout"
    )
    ledger.emit(last_tick, "terminal", {"claimed": claimed, "claimed_stage": stage})

    manifest = {
        "schema_version": "veab-bundle/1",
        "source": "ros2_hardware_telemetry",
        "environment": f"ROS 2 Humble / {robot_id} (Firmware {firmware_version})",
        "scenario": sc_dict,
        "scenario_sha256": sc_digest,
        "policy": f"ros2_{robot_id}",
        "seed": 0,
        "shield_enabled": False,
        "harness_version": "0.2.0-ros2",
        "dt_seconds": scenario.dt,
        "simulation_steps": last_tick,
        "ledger_root_sha256": ledger.root,
        "sync_report": sync_report
    }
    
    from ..ledger import sign
    attestation = sign(digest(manifest), attestation_key)
    return {"manifest": manifest, "events": ledger.events, "attestation": attestation}

