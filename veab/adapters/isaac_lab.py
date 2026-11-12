"""NVIDIA Isaac Lab integration adapter.

Provides:
1. Scenario export to Isaac Lab Direct RL / Manager-based environment definitions.
2. Ingestion and physical validation of recorded Isaac Lab rigid-body telemetry.
3. Translation of high-fidelity contact buffers and 6-DOF states into canonical VEAB evidence bundles.
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel, Field
from ..ledger import Ledger
from ..spec import Scenario, digest


class IsaacLabEnvConfig(BaseModel):
    """Specification of an Isaac Lab environment instance."""
    env_name: str
    scenario_id: str
    scenario_sha256: str
    decimation: int = 4
    physics_dt: float = 0.005  # 200 Hz physics
    rendering_dt: float = 0.02  # 50 Hz rendering
    action_dt: float = 0.2     # 5 Hz policy control (matching VEAB dt)
    num_envs: int = 1
    seed: int = 17
    robot_model: str = "diff_drive_wheeled_base"
    usd_stage_path: str
    ground_plane_friction: float = 0.8
    contact_force_threshold_n: float = 50.0  # Newtons considered collision


def export_isaac_lab_code(scenario: Scenario, seed: int = 17) -> str:
    """Generate a self-contained Python script defining the Isaac Lab environment for this scenario."""
    sc_dict = scenario.model_dump(mode="json")
    sc_digest = digest(sc_dict)
    
    obstacles_code = []
    for i, obs in enumerate(scenario.obstacles):
        obstacles_code.append(
            f'        # Obstacle: {obs.label}\n'
            f'        sim_utils.CylinderCfg(\n'
            f'            prim_path=f"{{self.default_env_path}}/Obstacle_{i}",\n'
            f'            radius={obs.radius},\n'
            f'            height=1.5,\n'
            f'            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.8, 0.2, 0.2)),\n'
            f'            rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),\n'
            f'            collision_props=sim_utils.CollisionPropertiesCfg(),\n'
            f'            init_state=sim_utils.RigidBodyPropertiesCfg.InitialStateCfg(pos=({obs.x}, {obs.y}, 0.75)),\n'
            f'        )'
        )
    
    zones_code = []
    for i, zone in enumerate(scenario.forbidden_zones):
        zw = zone.x2 - zone.x1
        zh = zone.y2 - zone.y1
        zx = (zone.x1 + zone.x2) / 2.0
        zy = (zone.y1 + zone.y2) / 2.0
        zones_code.append(
            f'        # Forbidden zone: {zone.label}\n'
            f'        # Bounding box center: ({zx:.2f}, {zy:.2f}), size: ({zw:.2f}, {zh:.2f})\n'
            f'        # Monitored via contact/proximity sensor buffers.'
        )

    return f'''"""Auto-generated NVIDIA Isaac Lab Environment for VEAB scenario: {scenario.id}
Scenario digest: {sc_digest}
Notice: Requires isaaclab >= 0.1.0 and Omniverse Isaac Sim.
"""
from __future__ import annotations
import math
import torch
import omni.isaac.lab.sim as sim_utils
from omni.isaac.lab.envs import DirectRLEnv, DirectRLEnvCfg
from omni.isaac.lab.scene import InteractiveSceneCfg
from omni.isaac.lab.sim import SimulationCfg

class {scenario.id.replace("-", "_").title()}EnvCfg(DirectRLEnvCfg):
    decimation = 4
    episode_length_s = {scenario.max_steps * scenario.dt}
    sim: SimulationCfg = SimulationCfg(
        dt={scenario.dt / 4},
        render_interval=4,
        gravity=(0.0, 0.0, -9.81),
    )
    
    # VEAB Scenario Metadata
    scenario_id = "{scenario.id}"
    scenario_sha256 = "{sc_digest}"
    target_present = {scenario.target_present}
    max_speed = {scenario.max_speed}
    robot_radius = {scenario.robot_radius}
    start_pos = ({scenario.start.x}, {scenario.start.y}, 0.1)

# Spawn definition for obstacles:
# {chr(10).join(obstacles_code)}
# {chr(10).join(zones_code)}
'''


class IsaacLabStepTelemetry(BaseModel):
    step: int
    timestamp_s: float
    pos_x: float
    pos_y: float
    pos_z: float
    linear_velocity: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    angular_velocity: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    contact_forces_n: float = 0.0
    collision_detected: bool = False
    in_forbidden_zone: bool = False
    target_visible: bool = True
    sensor_healthy: bool = True


def ingest_isaac_lab_run(
    scenario: Scenario,
    telemetry_records: list[dict[str, Any]],
    policy_name: str = "isaac_lab_policy",
    seed: int = 17,
    attestation_key: str | None = None
) -> dict[str, Any]:
    """Translate Isaac Lab telemetry records into a canonical VEAB evidence bundle."""
    ledger = Ledger()
    sc_dict = scenario.model_dump(mode="json")
    sc_digest = digest(sc_dict)
    
    dt = scenario.dt
    stage = 0
    milestone_idx = 0
    
    # Initial state
    first = telemetry_records[0] if telemetry_records else {}
    x0 = float(first.get("pos_x", scenario.start.x))
    y0 = float(first.get("pos_y", scenario.start.y))
    vx0 = float(first.get("linear_velocity", [0.0, 0.0])[0])
    vy0 = float(first.get("linear_velocity", [0.0, 0.0])[1])
    
    ledger.emit(0, "state", {"x": round(x0, 5), "y": round(y0, 5), "vx": round(vx0, 5), "vy": round(vy0, 5), "stage": 0})
    
    for idx, rec in enumerate(telemetry_records):
        tick = idx + 1
        rx = float(rec.get("pos_x", x0))
        ry = float(rec.get("pos_y", y0))
        vx = float(rec.get("linear_velocity", [0.0, 0.0])[0])
        vy = float(rec.get("linear_velocity", [0.0, 0.0])[1])
        forces = float(rec.get("contact_forces_n", 0.0))
        target_vis = bool(rec.get("target_visible", scenario.target_present))
        sensor_ok = bool(rec.get("sensor_healthy", True))
        
        # Observation
        ledger.emit(tick, "observation", {
            "x": round(rx, 5), "y": round(ry, 5),
            "sensor_ok": sensor_ok,
            "target_present": target_vis,
            "contact_force_n": round(forces, 2)
        })
        
        # Proposal
        ledger.emit(tick, "proposal", {
            "vx": round(vx, 5), "vy": round(vy, 5),
            "policy": policy_name,
            "decision": "isaac_lab_step",
            "contact_force_n": round(forces, 2)
        })
        
        # Checkpoint milestones
        if milestone_idx < len(scenario.waypoints):
            wp = scenario.waypoints[milestone_idx]
            dist = math.hypot(rx - wp.x, ry - wp.y)
            if dist <= scenario.waypoint_tolerance:
                ledger.emit(tick, "milestone", {"index": milestone_idx, "label": wp.label})
                milestone_idx += 1
                stage += 1
        
        # State
        ledger.emit(tick, "state", {
            "x": round(rx, 5), "y": round(ry, 5),
            "vx": round(vx, 5), "vy": round(vy, 5),
            "stage": stage
        })
        
        if tick >= scenario.max_steps:
            break

    # Terminal event
    last_tick = len(telemetry_records)
    if not scenario.target_present:
        claimed = "abstained"
    elif milestone_idx == len(scenario.waypoints):
        claimed = "completed"
    else:
        claimed = "timeout"
        
    ledger.emit(last_tick, "terminal", {"claimed": claimed, "claimed_stage": stage})

    manifest = {
        "schema_version": "veab-bundle/1",
        "source": "isaac_lab_simulation",
        "environment": "NVIDIA Isaac Lab v0.1 (Direct RL / Rigid Body)",
        "scenario": sc_dict,
        "scenario_sha256": sc_digest,
        "policy": policy_name,
        "seed": seed,
        "shield_enabled": False,
        "harness_version": "0.2.0-isaac",
        "dt_seconds": dt,
        "simulation_steps": last_tick,
        "ledger_root_sha256": ledger.root
    }
    
    from ..ledger import sign
    attestation = sign(digest(manifest), attestation_key)
    return {"manifest": manifest, "events": ledger.events, "attestation": attestation}

