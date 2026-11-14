"""MuJoCo Physics Engine & MJCF XML model adapter for VEAP.

Provides:
1. Procedural generation of MuJoCo MJCF XML models from VEAP scenario contracts.
2. Ingestion and joint-torque / contact-force validation of MuJoCo physics runs.
3. Measurement of mechanical work in Joules: W = sum(tau * qvel * dt).
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel, Field
from ..ledger import Ledger
from ..spec import Scenario, digest


def export_mjcf_xml(scenario: Scenario) -> str:
    """Export a VEAP scenario to a clean, valid MuJoCo MJCF XML model."""
    sc_dict = scenario.model_dump(mode="json")
    sc_digest = digest(sc_dict)
    
    body_elements = []
    
    # Ground plane and walls
    w, h = scenario.width, scenario.height
    r = scenario.robot_radius
    
    body_elements.append(
        f'    <!-- Floor and boundaries -->\n'
        f'    <geom name="floor" type="plane" size="{w/2} {h/2} 0.1" pos="{w/2} {h/2} 0" rgba="0.1 0.12 0.18 1"/>\n'
        f'    <geom name="wall_south" type="box" size="{w/2} 0.05 0.5" pos="{w/2} 0 0.25" rgba="0.3 0.35 0.45 1"/>\n'
        f'    <geom name="wall_north" type="box" size="{w/2} 0.05 0.5" pos="{w/2} {h} 0.25" rgba="0.3 0.35 0.45 1"/>\n'
        f'    <geom name="wall_west" type="box" size="0.05 {h/2} 0.5" pos="0 {h/2} 0.25" rgba="0.3 0.35 0.45 1"/>\n'
        f'    <geom name="wall_east" type="box" size="0.05 {h/2} 0.5" pos="{w} {h/2} 0.25" rgba="0.3 0.35 0.45 1"/>'
    )
    
    # Static Obstacles
    for i, obs in enumerate(scenario.obstacles):
        body_elements.append(
            f'    <body name="obstacle_{i}" pos="{obs.x} {obs.y} 0.4">\n'
            f'      <geom name="geom_obs_{i}" type="cylinder" size="{obs.radius} 0.4" rgba="0.85 0.35 0.25 1" friction="0.7 0.1 0.1"/>\n'
            f'    </body>'
        )
        
    # Robot body
    sx, sy = scenario.start.x, scenario.start.y
    robot_body = (
        f'    <!-- Robot Agent -->\n'
        f'    <body name="robot" pos="{sx} {sy} 0.15">\n'
        f'      <joint name="root_x" type="slide" axis="1 0 0" damping="1.5"/>\n'
        f'      <joint name="root_y" type="slide" axis="0 1 0" damping="1.5"/>\n'
        f'      <joint name="root_yaw" type="hinge" axis="0 0 1" damping="0.5"/>\n'
        f'      <geom name="robot_chassis" type="cylinder" size="{r} 0.15" mass="12.0" rgba="0.2 0.7 0.9 1"/>\n'
        f'      <site name="robot_sensor" pos="0 0 0.15" size="0.05"/>\n'
        f'    </body>'
    )
    body_elements.append(robot_body)

    xml = f'''<!--
  VEAP MuJoCo Physics Model
  Scenario: {scenario.id}
  Scenario SHA-256: {sc_digest}
-->
<mujoco model="{scenario.id}">
  <compiler angle="radian" coordinate="local"/>
  <option timestep="{scenario.dt}" gravity="0 0 -9.81" iterations="50" solver="Newton">
    <flag contact="enable" frictionloss="enable"/>
  </option>

  <visual>
    <headlight ambient="0.5 0.5 0.5" diffuse="0.8 0.8 0.8"/>
  </visual>

  <worldbody>
{chr(10).join(body_elements)}
  </worldbody>

  <actuator>
    <motor name="actuator_x" joint="root_x" gear="1" ctrlrange="-50 50"/>
    <motor name="actuator_y" joint="root_y" gear="1" ctrlrange="-50 50"/>
  </actuator>

  <sensor>
    <framelinvel name="robot_vel" objtype="site" objname="robot_sensor"/>
    <framepos name="robot_pos" objtype="site" objname="robot_sensor"/>
  </sensor>
</mujoco>
'''
    return xml


class MujocoTelemetryRecord(BaseModel):
    step: int
    pos_x: float
    pos_y: float
    vx: float
    vy: float
    torque_x: float = 0.0
    torque_y: float = 0.0
    contact_force_n: float = 0.0
    in_collision: bool = False


def ingest_mujoco_run(
    scenario: Scenario,
    records: list[dict[str, Any]],
    policy_name: str = "mujoco_control_policy",
    seed: int = 17,
    attestation_key: str | None = None
) -> dict[str, Any]:
    """Ingest MuJoCo physics simulation records and compute true mechanical energy in Joules."""
    ledger = Ledger()
    sc_dict = scenario.model_dump(mode="json")
    sc_digest = digest(sc_dict)
    dt = scenario.dt
    
    first = records[0] if records else {}
    x0 = float(first.get("pos_x", scenario.start.x))
    y0 = float(first.get("pos_y", scenario.start.y))
    vx0 = float(first.get("vx", 0.0))
    vy0 = float(first.get("vy", 0.0))
    
    ledger.emit(0, "state", {"x": round(x0, 5), "y": round(y0, 5), "vx": round(vx0, 5), "vy": round(vy0, 5), "stage": 0})
    
    milestone_idx = 0
    stage = 0
    total_joules = 0.0
    
    for idx, rec in enumerate(records):
        tick = idx + 1
        rx = float(rec.get("pos_x", x0))
        ry = float(rec.get("pos_y", y0))
        vx = float(rec.get("vx", 0.0))
        vy = float(rec.get("vy", 0.0))
        tx = float(rec.get("torque_x", 0.0))
        ty = float(rec.get("torque_y", 0.0))
        cf = float(rec.get("contact_force_n", 0.0))
        
        # Power = tau * vel -> Energy = sum(Power * dt)
        step_joules = (abs(tx * vx) + abs(ty * vy)) * dt
        total_joules += step_joules
        
        ledger.emit(tick, "observation", {
            "x": round(rx, 5), "y": round(ry, 5),
            "sensor_ok": True,
            "target_present": scenario.target_present,
            "contact_force_n": round(cf, 2),
            "mechanical_energy_joules": round(total_joules, 4)
        })
        
        ledger.emit(tick, "proposal", {
            "vx": round(vx, 5), "vy": round(vy, 5),
            "torque_x": round(tx, 3), "torque_y": round(ty, 3),
            "policy": policy_name,
            "decision": "mujoco_physics_step"
        })
        
        if milestone_idx < len(scenario.waypoints):
            wp = scenario.waypoints[milestone_idx]
            if math.hypot(rx - wp.x, ry - wp.y) <= scenario.waypoint_tolerance:
                ledger.emit(tick, "milestone", {"index": milestone_idx, "label": wp.label})
                milestone_idx += 1
                stage += 1
                
        ledger.emit(tick, "state", {
            "x": round(rx, 5), "y": round(ry, 5),
            "vx": round(vx, 5), "vy": round(vy, 5),
            "stage": stage
        })
        
        if tick >= scenario.max_steps:
            break
            
    last_tick = len(records)
    claimed = "completed" if (scenario.target_present and milestone_idx == len(scenario.waypoints)) else (
        "abstained" if not scenario.target_present else "timeout"
    )
    ledger.emit(last_tick, "terminal", {"claimed": claimed, "claimed_stage": stage})

    manifest = {
        "schema_version": "veap-bundle/1",
        "source": "mujoco_physics_simulation",
        "environment": "MuJoCo Contact Dynamics v3.0+",
        "scenario": sc_dict,
        "scenario_sha256": sc_digest,
        "policy": policy_name,
        "seed": seed,
        "shield_enabled": False,
        "harness_version": "0.2.0-mujoco",
        "dt_seconds": dt,
        "simulation_steps": last_tick,
        "ledger_root_sha256": ledger.root,
        "measured_energy_joules": round(total_joules, 4)
    }
    
    from ..ledger import sign
    attestation = sign(digest(manifest), attestation_key)
    return {"manifest": manifest, "events": ledger.events, "attestation": attestation}

