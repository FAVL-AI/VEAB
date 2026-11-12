"""Test native backend execution: Rust verifier, C++ sim, and Go orchestrator."""
import pytest
from pathlib import Path
from veab.native import (
    has_rust_verifier,
    has_cpp_sim,
    has_go_orchestrator,
    run_rust_verifier,
    run_cpp_sim,
    run_go_orchestrator,
)

def test_rust_verifier_executes():
    assert has_rust_verifier(), "Rust verifier binary should exist in backend/bin"
    bundle_path = Path("artifacts/407b11c464024fd397167e63f8f57f35.json")
    if bundle_path.exists():
        res = run_rust_verifier(bundle_path)
        assert "verified" in res
        assert "trace_integrity" in res
        assert "backend" in res
        assert "Rust" in res["backend"]

def test_cpp_sim_executes():
    assert has_cpp_sim(), "C++ sim binary should exist in backend/bin"
    res = run_cpp_sim(shielded=True, fault="actuator_stall", seed=17)
    assert res["completed"] is True
    assert res["violations"] == 0
    assert res["energy_joules"] > 0
    assert res["shielded"] is True
    assert res["fault"] == "actuator_stall"

def test_go_orchestrator_executes():
    assert has_go_orchestrator(), "Go orchestrator binary should exist in backend/bin"
    res = run_go_orchestrator(seeds=5)
    assert res["num_scenarios"] == 5
    assert res["total_trials"] == 50
    assert "agent_a_unshielded" in res["metrics_by_policy"]
    assert "agent_b_shielded" in res["metrics_by_policy"]
    pol_a = res["metrics_by_policy"]["agent_a_unshielded"]
    pol_b = res["metrics_by_policy"]["agent_b_shielded"]
    # Agent B should have higher verified success and 0 violations
    assert pol_b["verified_success_rate"] >= pol_a["verified_success_rate"]
    assert pol_b["unsafe_action_rate"] == 0.0

