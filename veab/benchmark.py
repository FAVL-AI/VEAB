"""Cross-simulator and sim-to-real transfer benchmarking engine.

Quantifies the fidelity gap between:
- 2D Kinematic Toy Simulation
- MuJoCo Contact Dynamics (MJCF)
- NVIDIA Isaac Lab (Direct RL / Rigid Body)
- Physical Hardware Telemetry (ROS 2 MCAP)
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel


class SimTransferMetrics(BaseModel):
    sim_a_name: str
    sim_b_name: str
    trajectory_length_a: int
    trajectory_length_b: int
    mean_position_rmse_m: float
    max_position_divergence_m: float
    dtw_distance_m: float
    velocity_rmse_mps: float
    energy_discrepancy_ratio: float
    fidelity_index: float  # 1.0 = identical; 0.0 = completely divergent


def _compute_dtw(seq_a: list[tuple[float, float]], seq_b: list[tuple[float, float]]) -> float:
    """Compute Dynamic Time Warping (DTW) distance between two 2D coordinate sequences."""
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return 0.0
        
    # Standard DTW table with bounded memory
    dtw = [[math.inf] * (m + 1) for _ in range(n + 1)]
    dtw[0][0] = 0.0
    
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = math.hypot(seq_a[i-1][0] - seq_b[j-1][0], seq_a[i-1][1] - seq_b[j-1][1])
            dtw[i][j] = cost + min(dtw[i-1][j], dtw[i][j-1], dtw[i-1][j-1])
            
    return dtw[n][m] / max(1, n + m)


def compare_sim_trajectories(
    bundle_a: dict[str, Any],
    bundle_b: dict[str, Any]
) -> SimTransferMetrics:
    """Compare two evidence bundles from different simulators executing the same scenario."""
    env_a = bundle_a.get("manifest", {}).get("environment", "Simulator A")
    env_b = bundle_b.get("manifest", {}).get("environment", "Simulator B")
    
    states_a = [
        (e["payload"]["x"], e["payload"]["y"], e["payload"]["vx"], e["payload"]["vy"])
        for e in bundle_a.get("events", []) if e.get("kind") == "state"
    ]
    states_b = [
        (e["payload"]["x"], e["payload"]["y"], e["payload"]["vx"], e["payload"]["vy"])
        for e in bundle_b.get("events", []) if e.get("kind") == "state"
    ]
    
    coords_a = [(s[0], s[1]) for s in states_a]
    coords_b = [(s[0], s[1]) for s in states_b]
    
    dtw = _compute_dtw(coords_a, coords_b)
    
    # Paired Euclidean distances up to minimum common length
    min_len = min(len(states_a), len(states_b))
    sq_errs = []
    v_sq_errs = []
    max_div = 0.0
    
    for i in range(min_len):
        dx = states_a[i][0] - states_b[i][0]
        dy = states_a[i][1] - states_b[i][1]
        dist = math.hypot(dx, dy)
        sq_errs.append(dist * dist)
        max_div = max(max_div, dist)
        
        dvx = states_a[i][2] - states_b[i][2]
        dvy = states_a[i][3] - states_b[i][3]
        v_sq_errs.append(dvx * dvx + dvy * dvy)
        
    rmse = math.sqrt(sum(sq_errs) / max(1, min_len)) if sq_errs else 0.0
    v_rmse = math.sqrt(sum(v_sq_errs) / max(1, min_len)) if v_sq_errs else 0.0
    
    energy_a = bundle_a.get("manifest", {}).get("measured_energy_joules", 1.0)
    energy_b = bundle_b.get("manifest", {}).get("measured_energy_joules", 1.0)
    ratio = float(energy_a) / max(1e-5, float(energy_b))
    
    # Fidelity index: normalized decay score
    fidelity = math.exp(-rmse / 0.5)
    
    return SimTransferMetrics(
        sim_a_name=env_a,
        sim_b_name=env_b,
        trajectory_length_a=len(states_a),
        trajectory_length_b=len(states_b),
        mean_position_rmse_m=round(rmse, 4),
        max_position_divergence_m=round(max_div, 4),
        dtw_distance_m=round(dtw, 4),
        velocity_rmse_mps=round(v_rmse, 4),
        energy_discrepancy_ratio=round(ratio, 4),
        fidelity_index=round(fidelity, 4)
    )

