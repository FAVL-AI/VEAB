"""Tests for Stage 1 (Power analysis, Cost model, Ablations, Reproducibility)
and Stage 2 (Machine-checkable formal task contracts).
"""
from __future__ import annotations
import pytest
from veap.spec import load_scenario
from veap.sim import run_episode
from veap.power_analysis import compute_sample_size
from veap.cost_model import evaluate_cost_profile
from veap.ablation import run_factorial_ablation
from veap.reproducibility import generate_reproducibility_report
from veap.formal_contracts import check_formal_task_contracts


def test_statistical_power_analysis():
    # Detect a delta of 0.30 (from 60% to 90%) at alpha=0.05, power=0.80 across 5 scenarios
    res = compute_sample_size(p1=0.60, p2=0.90, alpha=0.05, power=0.80, scenario_count=5)
    assert res.effect_size_delta == 0.30
    assert res.required_seeds_per_scenario >= 3
    assert res.total_trials_needed >= 15
    assert "seeds per scenario" in res.recommendation


def test_cost_model_evaluation():
    sc = load_scenario("warehouse-transfer")
    bundle = run_episode(sc, "route", 17, True)
    cost = evaluate_cost_profile(bundle, wall_clock_ms=25.0)
    
    assert cost.wall_clock_ms == 25.0
    assert cost.sim_time_s > 0.0
    assert cost.simulation_steps > 0
    assert cost.motion_energy_proxy > 0.0
    assert cost.total_trajectory_distance_m > 0.0
    assert cost.transport_cost_energy_per_m > 0.0
    assert cost.total_comm_bytes > 0


def test_factorial_ablation_decomposes_planner_and_gate():
    sc = load_scenario("warehouse-transfer")
    ablation = run_factorial_ablation(sc, seeds=[0, 1])
    
    assert len(ablation.cells) == 8  # 4 configs x 2 seeds
    # Gated should have fewer violations than ungated
    assert ablation.safety_gate_effect_delta_violations < 0
    assert "Ablation in scenario" in ablation.analysis


def test_reproducibility_report_generation():
    rep = generate_reproducibility_report(seeds=[0, 1])
    assert rep.reproducibility_rate == 1.0
    assert "100% DETERMINISTIC REPRODUCIBILITY CONFIRMED" in rep.audit_verdict
    assert len(rep.scenario_digests) >= 5


def test_formal_task_contracts_on_safe_route():
    sc = load_scenario("warehouse-transfer")
    bundle = run_episode(sc, "route", 17, True)
    report = check_formal_task_contracts(sc, bundle, energy_budget_max=30.0)
    
    assert report.all_contracts_satisfied is True
    assert len(report.clauses) == 6
    # Check all individual clauses
    assert all(c.satisfied for c in report.clauses)


def test_formal_task_contracts_catches_greedy_forbidden_intrusion():
    sc = load_scenario("warehouse-transfer")
    bundle = run_episode(sc, "greedy", 17, False)
    report = check_formal_task_contracts(sc, bundle)
    
    assert report.all_contracts_satisfied is False
    # Clause C2 (Forbidden zone) or C3 (Collision) must be violated
    failed_clauses = [c.clause_id for c in report.clauses if not c.satisfied]
    assert ("C2_NEVER_FORBIDDEN" in failed_clauses or "C3_NO_COLLISION" in failed_clauses)

