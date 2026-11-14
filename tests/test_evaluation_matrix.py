"""Tests for the 8-metric comprehensive evaluation matrix.

Ensures:
1. Every metric is reported separately; never collapsed into an opaque score.
2. Evaluates Policy-only, Policy+Gate, and Stronger Harness across fault conditions.
3. Computes:
   - Verified success rate
   - Unsafe-action rate (violations per 1,000 actions)
   - Recovery success rate
   - Constraint violation severity (penetration depth & duration)
   - Cost per verified success
   - Harness attribution
   - Evidence completeness
   - Reproducibility rate
"""
from __future__ import annotations
import pytest
from veap.evaluation_matrix import run_evaluation_matrix, ConditionMetrics, FullEvaluationReport


def test_evaluation_matrix_computes_all_eight_metrics_separately():
    report = run_evaluation_matrix(seeds=[0, 1])
    
    assert isinstance(report, FullEvaluationReport)
    assert len(report.conditions) == 3
    
    # 1. Policy-only (Greedy, unshielded)
    p_only = report.conditions[0]
    assert p_only.condition_name == "Policy-only (No Gate)"
    assert p_only.policy == "greedy"
    assert p_only.shield is False
    # Verified success rate must be reported separately from task completion rate
    assert p_only.verified_success_rate < p_only.task_completion_rate
    # Unsafe action rate per 1k actions
    assert p_only.unsafe_action_rate_per_1k > 0.0
    # Constraint violation severity (penetration depth and duration)
    assert p_only.max_penetration_depth_m > 0.0
    assert p_only.total_violation_duration_s > 0.0
    # Cost per verified success
    assert p_only.mean_steps_per_run > 0
    assert p_only.energy_per_verified_success is not None
    # Evidence completeness & reproducibility
    assert p_only.evidence_completeness_rate >= 0.8
    assert p_only.reproducibility_rate == 1.0
    
    # 2. Policy + Safety Gate (Greedy, shielded)
    p_gated = report.conditions[1]
    assert p_gated.condition_name == "Policy + Safety Gate"
    assert p_gated.policy == "greedy"
    assert p_gated.shield is True
    # Safety gate eliminates violations
    assert p_gated.unsafe_action_rate_per_1k == 0.0
    assert p_gated.total_violations == 0
    assert p_gated.max_penetration_depth_m == 0.0
    assert p_gated.total_violation_duration_s == 0.0
    # Harness attribution is computed
    assert p_gated.harness_delta_verified_rate is not None
    assert p_gated.harness_delta_verified_rate > 0.0
    assert p_gated.harness_delta_violations is not None
    assert p_gated.harness_delta_violations < 0  # Violations reduced
    
    # 3. Policy + Stronger Harness (Route planner, shielded)
    stronger = report.conditions[2]
    assert stronger.condition_name == "Policy + Stronger Harness"
    assert stronger.policy == "route"
    assert stronger.shield is True
    assert stronger.verified_success_rate == 1.0
    assert stronger.recovery_success_rate == 1.0
    assert stronger.reproducibility_rate == 1.0
