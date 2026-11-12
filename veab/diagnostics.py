"""Incremental Diagnostic Value Quantifier (Research Gate 3).

Quantifies:
1. Conventional Outcome-Only Success (arrival at destination coordinates).
2. VEAB Process-Level Verified Success (kinematic consistency, safety clearances, fault recoveries, integrity).
3. False Success Rate (FSR): Proportion of outcome-only successes that concealed critical process violations.
4. Incremental Diagnostic Detection Delta: Delta of true failures exposed by process verification.
5. False Positive Rate (FPR) of the verifier on validated safe baselines.
6. Verification runtime overhead (microseconds per step).
"""
from __future__ import annotations
import math
import time
from typing import Any
from pydantic import BaseModel
from .spec import Scenario, load_scenario
from .verifier import verify_bundle


class DiagnosticReport(BaseModel):
    total_trials: int
    outcome_only_successes: int
    process_verified_successes: int
    false_successes_masked_by_outcome: int
    false_success_rate: float
    incremental_failure_detection_delta: int
    false_positive_rejections_on_safe_baselines: int
    false_positive_rate: float
    total_safety_violations_caught: int
    avg_verification_time_ms: float
    verification_overhead_us_per_step: float
    breakdown_by_scenario: dict[str, dict[str, Any]]


def evaluate_trial_diagnostics(records: list[dict[str, Any]]) -> DiagnosticReport:
    """Evaluate diagnostic value across an ablation or benchmark trial collection."""
    total = len(records)
    if total == 0:
        raise ValueError("No trial records provided")
        
    outcome_successes = 0
    verified_successes = 0
    false_successes = 0
    false_positives = 0
    safe_baseline_count = 0
    total_violations = 0
    scenario_stats: dict[str, dict[str, Any]] = {}
    
    total_time_ms = 0.0
    total_steps = 0
    
    for r in records:
        sc_id = r.get("scenario_id", "unknown")
        if sc_id not in scenario_stats:
            scenario_stats[sc_id] = {
                "total": 0, "outcome_success": 0, "verified_success": 0,
                "masked_failures": 0, "violations": 0
            }
        s_stat = scenario_stats[sc_id]
        s_stat["total"] += 1
        
        # Outcome-only metric: Did the run claim 'task_completed' or reach the final coordinates?
        outcome_ok = bool(r.get("task_completed", False))
        if outcome_ok:
            outcome_successes += 1
            s_stat["outcome_success"] += 1
            
        # Process verification result
        proc_ok = bool(r.get("verified", False))
        if proc_ok:
            verified_successes += 1
            s_stat["verified_success"] += 1
            
        violations = int(r.get("safety_violations", 0))
        total_violations += violations
        s_stat["violations"] += violations
        
        # Masked failure: outcome says success, but process verification failed
        if outcome_ok and not proc_ok:
            false_successes += 1
            s_stat["masked_failures"] += 1
            
        # False positive check: if policy is 'route' with shield on, it is a known-safe baseline.
        # If it was unverified due to verifier error, count as false positive.
        if r.get("policy") == "route" and r.get("shield") is True:
            safe_baseline_count += 1
            if not proc_ok:
                false_positives += 1
                
        steps = int(r.get("steps", 0))
        total_steps += steps
        duration = float(r.get("duration_ms", 0.0))
        total_time_ms += duration

    fsr = false_successes / max(1, outcome_successes)
    fpr = false_positives / max(1, safe_baseline_count)
    avg_ms = total_time_ms / max(1, total)
    us_per_step = (total_time_ms * 1000.0) / max(1, total_steps)

    return DiagnosticReport(
        total_trials=total,
        outcome_only_successes=outcome_successes,
        process_verified_successes=verified_successes,
        false_successes_masked_by_outcome=false_successes,
        false_success_rate=round(fsr, 4),
        incremental_failure_detection_delta=false_successes,
        false_positive_rejections_on_safe_baselines=false_positives,
        false_positive_rate=round(fpr, 4),
        total_safety_violations_caught=total_violations,
        avg_verification_time_ms=round(avg_ms, 2),
        verification_overhead_us_per_step=round(us_per_step, 2),
        breakdown_by_scenario=scenario_stats
    )

