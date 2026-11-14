"""Test Isaac Lab <-> MuJoCo sim-to-sim transfer validation."""
import pytest
from veap.spec import load_scenario
from veap.cross_sim import evaluate_sim_to_sim_transfer

def test_sim_to_sim_transfer_matching_trajectories():
    scenario = load_scenario("warehouse-transfer")
    # Identical runs with minor numerical jitter
    isaac_traj = [
        {"tick": i, "time_s": i * 0.2, "x": 1.0 + i * 0.1, "y": 1.0 + i * 0.1, "vx": 0.5, "vy": 0.5, "contact_force_n": 0.0, "energy_joules": i * 3.0}
        for i in range(20)
    ]
    mujoco_traj = [
        {"tick": i, "time_s": i * 0.2, "x": 1.0 + i * 0.1 + 0.01, "y": 1.0 + i * 0.1 - 0.01, "vx": 0.5, "vy": 0.5, "contact_force_n": 0.0, "energy_joules": i * 3.1}
        for i in range(20)
    ]

    report = evaluate_sim_to_sim_transfer(scenario, isaac_traj, mujoco_traj)
    assert report.is_sim_to_real is False, "Must NOT be called sim-to-real without hardware data"
    assert "sim-to-sim transfer" in report.evaluation_label
    assert report.rmse_position_m < 0.05
    assert report.energy_divergence_pct < 5.0
    assert report.transfer_acceptable is True
    assert report.transfer_gap_score < 0.10

def test_sim_to_sim_transfer_detects_divergence():
    scenario = load_scenario("warehouse-transfer")
    isaac_traj = [
        {"tick": i, "time_s": i * 0.2, "x": 1.0 + i * 0.1, "y": 1.0, "vx": 0.5, "vy": 0.0, "contact_force_n": 0.0, "energy_joules": i * 2.0}
        for i in range(20)
    ]
    mujoco_traj = [
        {"tick": i, "time_s": i * 0.2, "x": 1.0, "y": 1.0 + i * 0.1, "vx": 0.0, "vy": 0.5, "contact_force_n": 10.0, "energy_joules": i * 8.0}
        for i in range(20)
    ]

    report = evaluate_sim_to_sim_transfer(scenario, isaac_traj, mujoco_traj)
    assert report.transfer_acceptable is False
    assert report.rmse_position_m > 0.5
    assert report.energy_divergence_pct > 50.0

