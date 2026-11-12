"""Model- and harness-agnostic joint evaluation protocol for VEAB.

Definition:
A model- and harness-agnostic evaluation protocol that jointly measures
task success, constraint violations, recovery, resource cost, and
independently checkable evidence under controlled faults.
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel, Field
from .spec import Scenario
from .verifier import verify_bundle


class TaskSuccessMetrics(BaseModel):
    task_completed: bool
    milestones_achieved: int
    total_milestones: int
    progress_ratio: float = Field(ge=0.0, le=1.0)
    negative_goal_abstention: bool | None = None
    terminal_claim_valid: bool


class ConstraintMetrics(BaseModel):
    zero_violation_gate: bool
    total_violations: int
    min_clearance_m: float | None
    speed_limit_violations: int
    obstacle_collisions: int
    forbidden_zone_intrusions: int
    contact_force_violations: int


class RecoveryMetrics(BaseModel):
    controlled_faults_injected: int
    faults_recovered: int
    recovery_rate: float = Field(ge=0.0, le=1.0)
    interventions_applied: int
    replanning_events: int


class ResourceCostMetrics(BaseModel):
    sim_time_seconds: float
    total_steps: int
    energy_proxy: float
    mechanical_work_joules: float | None = None
    transport_cost: float | None = None  # Energy per metre
    peak_speed: float


class EvidenceMetrics(BaseModel):
    trace_integrity: bool
    ledger_root_sha256: str
    scenario_sha256: str
    event_count: int
    provenance: str
    attestation_verified: bool | None = None
    evaluation_valid: bool


class JointEvaluationResult(BaseModel):
    """Unified 5-dimensional evaluation result across model, harness, and faults."""
    scenario_id: str
    policy_name: str
    harness_environment: str
    seed: int
    verified_success: bool
    
    # The 5 First-Class Evaluation Dimensions
    task_success: TaskSuccessMetrics
    constraints: ConstraintMetrics
    recovery: RecoveryMetrics
    resource_cost: ResourceCostMetrics
    evidence: EvidenceMetrics
    
    failure_reasons: list[str]


def evaluate_bundle_jointly(bundle: dict[str, Any], attestation_key: str | None = None) -> JointEvaluationResult:
    """Evaluate an evidence bundle across all five first-class dimensions."""
    verification = verify_bundle(bundle, attestation_key)
    manifest = bundle.get("manifest", {})
    events = bundle.get("events", [])
    scenario_data = manifest.get("scenario", {})
    
    # 1. Task Success
    milestones_achieved = 0
    total_milestones = len(scenario_data.get("waypoints", []))
    target_present = scenario_data.get("target_present", True)
    
    for e in events:
        if e.get("kind") == "milestone":
            milestones_achieved += 1
            
    terminal_ev = events[-1] if events and events[-1].get("kind") == "terminal" else {}
    claimed = terminal_ev.get("payload", {}).get("claimed")
    
    task_completed = verification.get("task_completed", False)
    abstention_valid = None
    if not target_present:
        abstention_valid = (claimed == "abstained" and task_completed)
        
    task_success = TaskSuccessMetrics(
        task_completed=task_completed,
        milestones_achieved=milestones_achieved,
        total_milestones=total_milestones,
        progress_ratio=verification.get("progress", 0.0),
        negative_goal_abstention=abstention_valid,
        terminal_claim_valid=bool(claimed in {"completed", "abstained", "timeout"} and verification.get("evaluation_valid"))
    )
    
    # 2. Constraint Violations
    violations = verification.get("violations", [])
    speed_viol = sum(1 for v in violations if "speed limit" in v.get("type", ""))
    obs_viol = sum(1 for v in violations if "collision" in v.get("type", ""))
    zone_viol = sum(1 for v in violations if "forbidden zone" in v.get("type", ""))
    
    constraints = ConstraintMetrics(
        zero_violation_gate=(len(violations) == 0),
        total_violations=len(violations),
        min_clearance_m=verification.get("min_clearance_m"),
        speed_limit_violations=speed_viol,
        obstacle_collisions=obs_viol,
        forbidden_zone_intrusions=zone_viol,
        contact_force_violations=0
    )
    
    # 3. Recovery Metrics
    total_faults = verification.get("faults", 0)
    recovered_faults = verification.get("recovered_faults", 0)
    rec_rate = (recovered_faults / total_faults) if total_faults > 0 else 1.0
    
    replans = sum(1 for e in events if e.get("kind") == "proposal" and e.get("payload", {}).get("replans", 0) > 1)
    
    recovery = RecoveryMetrics(
        controlled_faults_injected=total_faults,
        faults_recovered=recovered_faults,
        recovery_rate=round(rec_rate, 4),
        interventions_applied=verification.get("interventions", 0),
        replanning_events=replans
    )
    
    # 4. Resource Cost Metrics
    states = [e.get("payload", {}) for e in events if e.get("kind") == "state"]
    peak_speed = 0.0
    total_dist = 0.0
    for idx, st in enumerate(states):
        vx, vy = float(st.get("vx", 0.0)), float(st.get("vy", 0.0))
        spd = math.hypot(vx, vy)
        peak_speed = max(peak_speed, spd)
        if idx > 0:
            dx = float(st.get("x", 0.0)) - float(states[idx-1].get("x", 0.0))
            dy = float(st.get("y", 0.0)) - float(states[idx-1].get("y", 0.0))
            total_dist += math.hypot(dx, dy)
            
    energy_proxy = verification.get("energy_proxy", 0.0)
    transport_cost = (energy_proxy / total_dist) if total_dist > 0.1 else None
    
    resource_cost = ResourceCostMetrics(
        sim_time_seconds=verification.get("sim_time_seconds", 0.0),
        total_steps=verification.get("steps", 0),
        energy_proxy=energy_proxy,
        mechanical_work_joules=manifest.get("measured_energy_joules"),
        transport_cost=round(transport_cost, 4) if transport_cost else None,
        peak_speed=round(peak_speed, 4)
    )
    
    # 5. Evidence Metrics
    evidence = EvidenceMetrics(
        trace_integrity=verification.get("trace_integrity", False),
        ledger_root_sha256=manifest.get("ledger_root_sha256", ""),
        scenario_sha256=manifest.get("scenario_sha256", ""),
        event_count=len(events),
        provenance=verification.get("provenance", "unknown"),
        attestation_verified=verification.get("attestation_verified"),
        evaluation_valid=verification.get("evaluation_valid", False)
    )
    
    return JointEvaluationResult(
        scenario_id=scenario_data.get("id", "unknown"),
        policy_name=manifest.get("policy", "unknown"),
        harness_environment=manifest.get("environment", "unknown"),
        seed=manifest.get("seed", 0),
        verified_success=verification.get("verified", False),
        task_success=task_success,
        constraints=constraints,
        recovery=recovery,
        resource_cost=resource_cost,
        evidence=evidence,
        failure_reasons=verification.get("failure_reasons", [])
    )

