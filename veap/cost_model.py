"""Cost model for autonomous embodied AI benchmarking.

Jointly measures:
1. Time: Wall-clock verification duration (ms) and simulated episode time (s).
2. Compute: Total simulation steps, planning calls, replanning frequency.
3. Energy: Integrated motion proxy energy and transport cost (energy per metre).
4. Communication: Ingested observation bytes, emitted action proposal bytes, total payload.
"""
from __future__ import annotations
import json
import math
from typing import Any
from pydantic import BaseModel, Field


class EpisodeCostProfile(BaseModel):
    # Time
    wall_clock_ms: float = Field(ge=0.0)
    sim_time_s: float = Field(ge=0.0)
    step_duration_s: float = Field(default=0.2)
    
    # Compute
    simulation_steps: int = Field(ge=0)
    planning_proposals: int = Field(ge=0)
    replanning_events: int = Field(ge=0)
    
    # Energy
    motion_energy_proxy: float = Field(ge=0.0)
    total_trajectory_distance_m: float = Field(ge=0.0)
    transport_cost_energy_per_m: float = Field(ge=0.0)
    peak_power_proxy: float = Field(ge=0.0)
    
    # Communication
    observation_bytes: int = Field(ge=0)
    proposal_bytes: int = Field(ge=0)
    total_comm_bytes: int = Field(ge=0)
    comm_bandwidth_bytes_per_s: float = Field(ge=0.0)


def evaluate_cost_profile(bundle: dict[str, Any], wall_clock_ms: float = 0.0) -> EpisodeCostProfile:
    """Analyze time, compute, energy, and communication costs from a bundle."""
    manifest = bundle.get("manifest", {})
    events = bundle.get("events", [])
    dt = float(manifest.get("dt_seconds", 0.2))
    steps = int(manifest.get("simulation_steps", 0))
    
    obs_bytes = 0
    prop_bytes = 0
    props = 0
    replans = 0
    
    states = []
    
    for e in events:
        payload_bytes = len(json.dumps(e.get("payload", {})))
        kind = e.get("kind")
        if kind == "observation":
            obs_bytes += payload_bytes
        elif kind == "proposal":
            prop_bytes += payload_bytes
            props += 1
            if e.get("payload", {}).get("replans", 0) > 1:
                replans += 1
        elif kind == "state":
            p = e.get("payload", {})
            states.append((float(p.get("x", 0.0)), float(p.get("y", 0.0)),
                           float(p.get("vx", 0.0)), float(p.get("vy", 0.0))))
            
    # Trajectory distance, energy, and peak power
    dist = 0.0
    energy = 0.0
    peak_power = 0.0
    
    for i in range(len(states)):
        vx, vy = states[i][2], states[i][3]
        spd_sq = vx * vx + vy * vy
        energy += spd_sq * dt
        peak_power = max(peak_power, spd_sq)
        if i > 0:
            dx = states[i][0] - states[i-1][0]
            dy = states[i][1] - states[i-1][1]
            dist += math.hypot(dx, dy)
            
    total_comm = obs_bytes + prop_bytes
    sim_time = steps * dt
    bandwidth = (total_comm / sim_time) if sim_time > 0.001 else 0.0
    transport_cost = (energy / dist) if dist > 0.01 else 0.0

    return EpisodeCostProfile(
        wall_clock_ms=round(wall_clock_ms, 2),
        sim_time_s=round(sim_time, 2),
        step_duration_s=dt,
        simulation_steps=steps,
        planning_proposals=props,
        replanning_events=replans,
        motion_energy_proxy=round(energy, 4),
        total_trajectory_distance_m=round(dist, 4),
        transport_cost_energy_per_m=round(transport_cost, 4),
        peak_power_proxy=round(peak_power, 4),
        observation_bytes=obs_bytes,
        proposal_bytes=prop_bytes,
        total_comm_bytes=total_comm,
        comm_bandwidth_bytes_per_s=round(bandwidth, 2)
    )

