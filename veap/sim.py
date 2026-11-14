"""Sandboxed, deterministic 2-D dynamics and an optional independent safety gate.

This is NOT Isaac Lab, a physics validated robot simulator, or a formal CBF proof.
The 3-D dashboard visualizes a 2-D test world's extruded geometry.
"""
from __future__ import annotations
import math
import random
from typing import Callable
from .agents import BaselineAgent, clamp_vector
from .ledger import Ledger, sign
from .spec import Scenario, digest


def _clear(s: Scenario, x: float, y: float) -> bool:
    r = s.robot_radius
    if not (r <= x <= s.width-r and r <= y <= s.height-r):
        return False
    for o in s.obstacles:
        if math.hypot(x-o.x, y-o.y) < o.radius+r:
            return False
    for z in s.forbidden_zones:
        if z.x1-r < x < z.x2+r and z.y1-r < y < z.y2+r:
            return False
    return True


def safe_motion(s: Scenario, pos: tuple[float,float], velocity: tuple[float,float]) -> bool:
    for n in range(1, 13):
        k = s.dt*n/12
        if not _clear(s, pos[0]+velocity[0]*k, pos[1]+velocity[1]*k):
            return False
    return True


def shield_velocity(s: Scenario, pos: tuple[float, float], desired: tuple[float,float], sensor_ok: bool):
    vx, vy = clamp_vector(*desired, s.max_speed)
    if not sensor_ok:
        return (0.0, 0.0), "sensor integrity emergency hold"
    if safe_motion(s, pos, (vx, vy)):
        return (vx, vy), None
    # Local geometric projection/slide. It is NOT a proven control barrier function.
    for fraction in (0.75, 0.5, 0.25):
        attempt = (vx*fraction, vy*fraction)
        if safe_motion(s, pos, attempt):
            return attempt, "trajectory clamped"
    for theta_deg in (30,-30,60,-60,90,-90):
        theta = math.radians(theta_deg)
        attempt = ((vx*math.cos(theta)-vy*math.sin(theta))*0.65,
                   (vx*math.sin(theta)+vy*math.cos(theta))*0.65)
        if safe_motion(s, pos, attempt):
            return attempt, "trajectory reoriented"
    return (0.0, 0.0), "obstacle emergency hold"


def run_episode(s: Scenario, policy: str = "route", seed: int = 0, shield: bool = True,
                callback: Callable[[dict], None] | None = None,
                attestation_key: str | None = None) -> dict:
    if not 0 <= seed <= 2**32-1:
        raise ValueError("seed out of range")
    rng = random.Random(seed)
    agent = BaselineAgent(policy, s)
    pos = (s.start.x, s.start.y)
    stage = 0
    ticks = 0
    ledger = Ledger()
    observations = 0
    last_known_pos = pos
    terminal = "timeout"
    cmd_history: list[tuple[float,float]] = []

    def emit(tick: int, kind: str, data: dict):
        record = ledger.emit(tick, kind, data)
        if callback:
            callback(record)

    emit(0, "state", {"x":pos[0], "y":pos[1], "vx":0.0,"vy":0.0, "stage":stage})
    for tick in range(1, s.max_steps+1):
        ticks = tick
        active = [f for f in s.faults if f.start_step <= tick < f.start_step+f.duration_steps]
        for f in s.faults:
            if f.start_step == tick:
                emit(tick, "fault", {"kind":f.kind, "phase":"start", "duration_steps":f.duration_steps})
            if f.start_step + f.duration_steps == tick:
                emit(tick, "fault", {"kind":f.kind, "phase":"end"})
        dropout = any(f.kind == "sensor_dropout" for f in active)
        stall = any(f.kind == "actuator_stall" for f in active)
        noise = any(f.kind == "perception_noise" for f in active)
        delay = any(f.kind == "communication_delay" for f in active)
        observed_present = s.target_present if not dropout else None
        visible_pos = last_known_pos if dropout else pos
        if noise:
            visible_pos = (visible_pos[0]+rng.uniform(-0.24,0.24),visible_pos[1]+rng.uniform(-0.24,0.24))
        if not dropout:
            last_known_pos = pos
            observations += 1
        emit(tick, "observation", {"x":round(visible_pos[0],5), "y":round(visible_pos[1],5),
              "sensor_ok":not dropout,"target_present":observed_present})
        desired, rationale = agent.act(visible_pos, stage, observed_present)
        emit(tick, "proposal", {"vx":desired[0],"vy":desired[1],"policy":policy,**rationale})
        if not s.target_present and observations >= 3 and observed_present is False and policy == "route":
            emit(tick, "state", {"x":pos[0],"y":pos[1],"vx":0.0,"vy":0.0,"stage":stage})
            emit(tick, "abstain", {"reason":"requested target absent in authoritative observation"})
            terminal = "abstained"
            break
        if shield:
            applied, intervention = shield_velocity(s, pos, desired, not dropout)
        else:
            applied, intervention = desired, None
        if delay and len(cmd_history) >= 2:
            applied = cmd_history[-2]
        cmd_history.append(applied)
        if stall:
            applied = (0.0,0.0)
        if intervention is not None:
            emit(tick, "intervention", {"reason":intervention,"proposed_vx":desired[0],"proposed_vy":desired[1],
                                       "applied_vx":round(applied[0],6),"applied_vy":round(applied[1],6)})
        x = round(pos[0]+applied[0]*s.dt, 5)
        y = round(pos[1]+applied[1]*s.dt, 5)
        pos = (x,y)
        emit(tick, "state", {"x":x,"y":y,"vx":round(applied[0],6),"vy":round(applied[1],6), "stage":stage})
        if s.target_present and stage < len(s.waypoints):
            p = s.waypoints[stage]
            if math.hypot(x-p.x,y-p.y) <= s.waypoint_tolerance:
                emit(tick, "milestone", {"index":stage, "label":p.label})
                stage += 1
                if stage == len(s.waypoints):
                    terminal = "completed"
                    break
    emit(ticks, "terminal", {"claimed":terminal,"claimed_stage":stage})
    manifest = {
        "schema_version":"veap-bundle/1", "source":"deterministic_toy_simulation",
        "environment":"VEAP toy planar simulator v0.1 (not Isaac/ROS2)",
        "scenario":s.model_dump(mode="json", exclude_none=True), "scenario_sha256":digest(s.model_dump(mode="json", exclude_none=True)),
        "policy":policy,"seed":seed,"shield_enabled":shield,
        "harness_version":"0.1.0", "dt_seconds":s.dt,
        "simulation_steps":ticks,
        "ledger_root_sha256":ledger.root,
    }
    bundle = {"manifest":manifest,"events":ledger.events,"attestation":sign(digest(manifest),attestation_key)}
    return bundle
