"""Cross-simulator validation engine: Isaac Lab <-> MuJoCo sim-to-sim transfer validation.

Important:
This module performs strict 'sim-to-sim transfer validation' between NVIDIA Isaac Lab
and MuJoCo physics engines. In accordance with VEAB scientific verification protocols,
this must NEVER be termed 'sim-to-real' until physical hardware measurements are gathered.
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel, Field
from .spec import Scenario, digest


class TrajectoryPoint(BaseModel):
    tick: int
    time_s: float
    x: float
    y: float
    vx: float
    vy: float
    contact_force_n: float = 0.0
    energy_joules: float = 0.0


class SimToSimTransferReport(BaseModel):
    """Rigorous sim-to-sim transfer assessment between Isaac Lab and MuJoCo."""
    scenario_id: str
    scenario_sha256: str
    evaluation_label: str = "sim-to-sim transfer validation (Isaac Lab <-> MuJoCo)"
    is_sim_to_real: bool = False  # Strictly False until physical hardware execution
    dtw_trajectory_distance: float
    rmse_position_m: float
    peak_force_delta_n: float
    energy_divergence_pct: float
    transfer_gap_score: float  # [0, 1], lower is closer transfer
    transfer_acceptable: bool
    notes: str


def compute_euclidean_rmse(
    traj_a: list[TrajectoryPoint],
    traj_b: list[TrajectoryPoint]
) -> float:
    """Compute root-mean-square error between matched trajectory timestamps."""
    n = min(len(traj_a), len(traj_b))
    if n == 0:
        return 0.0
    sq_err = sum((traj_a[i].x - traj_b[i].x)**2 + (traj_a[i].y - traj_b[i].y)**2 for i in range(n))
    return math.sqrt(sq_err / n)


def compute_dtw_distance(
    traj_a: list[TrajectoryPoint],
    traj_b: list[TrajectoryPoint]
) -> float:
    """Dynamic Time Warping (DTW) alignment between two trajectory profiles."""
    n = len(traj_a)
    m = len(traj_b)
    if n == 0 or m == 0:
        return 0.0

    # DP table
    dp = [[float("inf")] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = math.hypot(traj_a[i-1].x - traj_b[j-1].x, traj_a[i-1].y - traj_b[j-1].y)
            dp[i][j] = cost + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

    return dp[n][m] / max(n, m)


def evaluate_sim_to_sim_transfer(
    scenario: Scenario,
    isaac_trajectory: list[dict[str, Any]],
    mujoco_trajectory: list[dict[str, Any]],
    rmse_threshold_m: float = 0.25,
    energy_div_threshold_pct: float = 15.0
) -> SimToSimTransferReport:
    """Evaluate cross-simulator fidelity gap between Isaac Lab and MuJoCo runs."""
    pts_isaac = [TrajectoryPoint.model_validate(p) for p in isaac_trajectory]
    pts_mujoco = [TrajectoryPoint.model_validate(p) for p in mujoco_trajectory]

    sc_dict = scenario.model_dump(mode="json", exclude_none=True)
    sc_hash = digest(sc_dict)

    rmse = compute_euclidean_rmse(pts_isaac, pts_mujoco)
    dtw = compute_dtw_distance(pts_isaac, pts_mujoco)

    max_force_isaac = max((p.contact_force_n for p in pts_isaac), default=0.0)
    max_force_mujoco = max((p.contact_force_n for p in pts_mujoco), default=0.0)
    force_delta = abs(max_force_isaac - max_force_mujoco)

    e_isaac = pts_isaac[-1].energy_joules if pts_isaac else 0.0
    e_mujoco = pts_mujoco[-1].energy_joules if pts_mujoco else 0.0
    denom = max(1.0, (e_isaac + e_mujoco) / 2.0)
    energy_div_pct = (abs(e_isaac - e_mujoco) / denom) * 100.0

    # Transfer gap score in [0, 1]
    gap = min(1.0, (rmse / 1.0) * 0.5 + (energy_div_pct / 50.0) * 0.5)
    acceptable = (rmse <= rmse_threshold_m) and (energy_div_pct <= energy_div_threshold_pct)

    return SimToSimTransferReport(
        scenario_id=scenario.id,
        scenario_sha256=sc_hash,
        evaluation_label="sim-to-sim transfer validation (Isaac Lab <-> MuJoCo)",
        is_sim_to_real=False,
        dtw_trajectory_distance=round(dtw, 4),
        rmse_position_m=round(rmse, 4),
        peak_force_delta_n=round(force_delta, 2),
        energy_divergence_pct=round(energy_div_pct, 2),
        transfer_gap_score=round(gap, 4),
        transfer_acceptable=acceptable,
        notes="Evaluated under matched initial poses and action sequences across Isaac Lab and MuJoCo physics engines."
    )

