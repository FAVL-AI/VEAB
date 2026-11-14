"""Tests for the comparative agent evaluation (Agent A vs Agent B).

Demonstrates the core hypothesis:
Conventional success-only metrics fail to separate agents with identical arrival
rates but divergent safety, recovery, and energy characteristics.
"""
from __future__ import annotations
import pytest
from veap.comparison import AgentSummary, compare_agents


def test_agent_a_vs_agent_b_diagnostic_separation():
    agent_a = AgentSummary(
        agent_name="Agent A (Fast & Fragile)",
        task_success_rate=0.90,
        keepout_violation_rate=0.30,
        actuator_fault_recovery_rate=0.20,
        normalized_energy_consumption=2.0
    )
    
    agent_b = AgentSummary(
        agent_name="Agent B (Verified & Robust)",
        task_success_rate=0.90,
        keepout_violation_rate=0.00,
        actuator_fault_recovery_rate=0.80,
        normalized_energy_consumption=1.0
    )
    
    report = compare_agents(agent_a, agent_b)
    
    # Conventional success-only metric sees zero difference
    assert report.conventional_metric_delta == 0.0
    assert "EQUIVALENT" in report.conventional_metric_verdict
    
    # VEAP exposes the true operational gap
    assert report.veap_verified_delta == 0.30  # 90% vs 60%
    assert report.safety_divergence_delta == 0.30  # 30% vs 0% violations
    assert report.fault_recovery_advantage_ratio == 4.0  # 80% vs 20% = 4x
    assert report.energy_efficiency_ratio == 2.0  # Agent A uses 2x energy
    
    assert report.agent_a_evaluation["deployment_status"] == "REJECTED_UNSAFE"
    assert report.agent_b_evaluation["deployment_status"] == "VERIFIED_CANDIDATE"

