"""Preregistered adversarial fixtures for VEAP Verifier Hardening (Research Gate 1).

Acceptance Criterion:
At least 30 preregistered adversarial fixtures; 100% detection of defined
integrity-tampering, kinematic-fraud, and constraint-violation cases.
"""
from __future__ import annotations
import copy
import math
import pytest
from veap.ledger import Ledger
from veap.sim import run_episode
from veap.spec import digest, load_scenario
from veap.verifier import verify_bundle


def _get_clean_bundle(scenario_id: str = "warehouse-transfer", policy: str = "route", seed: int = 17, shield: bool = True):
    return run_episode(load_scenario(scenario_id), policy, seed, shield)


def _rebuild_chain_with_mutation(bundle: dict, mutate_fn) -> dict:
    """Helper to cleanly rebuild a valid SHA-256 hash chain after mutating event payloads,

    allowing tests to test semantic verification failures even when chain integrity is maintained.
    """
    b = copy.deepcopy(bundle)
    ledger = Ledger()
    for event in b["events"]:
        mutated = mutate_fn(copy.deepcopy(event))
        if mutated is not None:
            ledger.emit(mutated["tick"], mutated["kind"], mutated["payload"])
    b["events"] = ledger.events
    b["manifest"]["ledger_root_sha256"] = ledger.root
    return b


# ==============================================================================
# Category A: Cryptographic & Hash-Chain Tampering (1 - 9)
# ==============================================================================

def test_fixture_01_hash_chain_payload_tamper():
    """1. Modifying payload coordinates mid-chain without updating event hash must break trace integrity."""
    b = _get_clean_bundle()
    b["events"][4]["payload"]["x"] = 99.0
    result = verify_bundle(b)
    assert not result["trace_integrity"]
    assert not result["verified"]
    assert any("digest mismatch" in r for r in result["failure_reasons"])


def test_fixture_02_hash_chain_prev_hash_tamper():
    """2. Modifying prev_hash pointer mid-chain must break chain linkage."""
    b = _get_clean_bundle()
    b["events"][6]["prev_hash"] = "0" * 64
    result = verify_bundle(b)
    assert not result["trace_integrity"]
    assert not result["verified"]
    assert any("chain mismatch" in r for r in result["failure_reasons"])


def test_fixture_03_hash_chain_event_hash_tamper():
    """3. Direct modification of an event's hash field must break chain verification."""
    b = _get_clean_bundle()
    b["events"][5]["hash"] = "a" * 64
    result = verify_bundle(b)
    assert not result["trace_integrity"]
    assert not result["verified"]


def test_fixture_04_hash_chain_event_deletion():
    """4. Deleting an intermediate event from the chain must break sequence continuity."""
    b = _get_clean_bundle()
    b["events"].pop(5)
    result = verify_bundle(b)
    assert not result["trace_integrity"]
    assert not result["verified"]


def test_fixture_05_hash_chain_event_insertion():
    """5. Inserting an unhashed rogue event must break chain sequence."""
    b = _get_clean_bundle()
    rogue = copy.deepcopy(b["events"][3])
    b["events"].insert(4, rogue)
    result = verify_bundle(b)
    assert not result["trace_integrity"]
    assert not result["verified"]


def test_fixture_06_hash_chain_event_reordering():
    """6. Swapping two adjacent events must break cryptographic chaining."""
    b = _get_clean_bundle()
    b["events"][3], b["events"][4] = b["events"][4], b["events"][3]
    result = verify_bundle(b)
    assert not result["trace_integrity"]
    assert not result["verified"]


def test_fixture_07_manifest_ledger_root_mismatch():
    """7. Tampering with manifest's ledger_root_sha256 must fail bundle verification."""
    b = _get_clean_bundle()
    b["manifest"]["ledger_root_sha256"] = "f" * 64
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("manifest root does not match" in r for r in result["failure_reasons"])


def test_fixture_08_manifest_unknown_schema_version():
    """8. Manifest with unsupported schema version must be rejected."""
    b = _get_clean_bundle()
    b["manifest"]["schema_version"] = "veap-bundle/999-unsupported"
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("unknown bundle schema" in r for r in result["failure_reasons"])


def test_fixture_09_tick_non_monotonic_sequence():
    """9. Non-monotonic ticks must be rejected by chain validator."""
    b = _get_clean_bundle()
    b["events"][7]["tick"] = b["events"][6]["tick"] - 1
    # Update hash of event 7 to isolate monotonic tick check
    base = {k: v for k, v in b["events"][7].items() if k != "hash"}
    b["events"][7]["hash"] = digest(base)
    result = verify_bundle(b)
    assert not result["trace_integrity"]
    assert not result["verified"]


# ==============================================================================
# Category B: Scenario Contract & Clock Integrity (10 - 14)
# ==============================================================================

def test_fixture_10_scenario_contract_obstacle_shrink():
    """10. Tampering with obstacles in scenario payload without updating scenario_sha256 must be rejected."""
    b = _get_clean_bundle()
    b["manifest"]["scenario"]["obstacles"][0]["radius"] = 0.001
    result = verify_bundle(b)
    assert not result["trace_integrity"]
    assert not result["verified"]
    assert any("scenario digest mismatch" in r for r in result["failure_reasons"])


def test_fixture_11_scenario_contract_digest_tamper():
    """11. Bogus scenario_sha256 in manifest must be rejected."""
    b = _get_clean_bundle()
    b["manifest"]["scenario_sha256"] = "0" * 64
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("scenario digest mismatch" in r for r in result["failure_reasons"])


def test_fixture_12_clock_dt_mismatch():
    """12. Manifest claiming a different dt_seconds from scenario contract must be rejected."""
    b = _get_clean_bundle()
    b["manifest"]["dt_seconds"] = 0.5
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("environment clock mismatch" in r for r in result["failure_reasons"])


def test_fixture_13_clock_step_limit_exceeded():
    """13. Manifest simulation_steps exceeding scenario max_steps must fail."""
    b = _get_clean_bundle()
    b["manifest"]["simulation_steps"] = b["manifest"]["scenario"]["max_steps"] + 100
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("environment clock mismatch" in r for r in result["failure_reasons"])


def test_fixture_14_manifest_step_count_mismatch():
    """14. Manifest simulation_steps that does not match final state tick must fail."""
    b = _get_clean_bundle()
    b["manifest"]["simulation_steps"] = b["manifest"]["simulation_steps"] - 10
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("manifest step count mismatch" in r for r in result["failure_reasons"])


# ==============================================================================
# Category C: Attestation & Provenance Tampering (15 - 17)
# ==============================================================================

def test_fixture_15_hmac_wrong_attestation_key():
    """15. Bundle signed with genuine key must fail verification when tested against incorrect key."""
    s = load_scenario("campus-patrol")
    b = run_episode(s, "route", 13, True, attestation_key="genuine-laboratory-key")
    result = verify_bundle(b, attestation_key="forged-or-wrong-key")
    assert not result["verified"]
    assert result["attestation_verified"] is False
    assert any("invalid HMAC attestation" in r for r in result["failure_reasons"])


def test_fixture_16_hmac_post_signing_manifest_alteration():
    """16. Altering manifest fields after HMAC signing must invalidate attestation."""
    s = load_scenario("campus-patrol")
    b = run_episode(s, "route", 13, True, attestation_key="genuine-key")
    b["manifest"]["policy"] = "unauthorized-policy"
    result = verify_bundle(b, attestation_key="genuine-key")
    assert not result["verified"]
    assert result["attestation_verified"] is False


def test_fixture_17_external_telemetry_unattested_provenance():
    """17. External telemetry source without verified provenance cannot be marked verified."""
    b = _get_clean_bundle()
    b["manifest"]["source"] = "external_ros2_unverified_capture"
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("external telemetry provenance not independently established" in r for r in result["failure_reasons"])


# ==============================================================================
# Category D: Kinematics & Physical Bounds Fraud (18 - 22)
# ==============================================================================

def test_fixture_18_state_non_finite_coordinate():
    """18. Non-finite state coordinates (NaN or Inf) serialized as string representations must be rejected."""
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 5:
            e["payload"]["x"] = "inf"
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("invalid state" in r or "nonfinite state" in r for r in result["failure_reasons"])


def test_fixture_19_state_tick_gap():
    """19. Omission of state samples creating a step gap must be detected."""
    b = _get_clean_bundle()
    # Remove state at tick 3 and rebuild
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 3:
            return None
        return e
    b_mut = _rebuild_chain_with_mutation(b, mutate)
    result = verify_bundle(b_mut)
    assert not result["verified"]
    assert any("state tick gap" in r or "missing mandatory state samples" in r for r in result["failure_reasons"])


def test_fixture_20_state_speed_limit_exceeded():
    """20. Velocities exceeding scenario max_speed must be flagged as speed limit violations."""
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 10:
            e["payload"]["vx"] = 5.0
            e["payload"]["vy"] = 5.0
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert result["safety_violations"] > 0
    assert any(v["type"] == "speed limit exceeded" for v in result["violations"])


def test_fixture_21_state_kinematic_teleport():
    """21. Discontinuous coordinate teleportation inconsistent with velocity must be detected."""
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 8:
            e["payload"]["x"] += 2.0  # Teleport 2 metres ahead without velocity support
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("kinematic inconsistency" in r for r in result["failure_reasons"])


def test_fixture_22_state_initial_position_mismatch():
    """22. Trace starting at coordinates other than scenario start must be rejected."""
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 0:
            e["payload"]["x"] = 0.0
            e["payload"]["y"] = 0.0
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("initial state does not match scene" in r for r in result["failure_reasons"])


# ==============================================================================
# Category E: Geometric Hazards & Safety Gate Violations (23 - 26)
# ==============================================================================

def test_fixture_23_state_boundary_escape():
    """23. Trajectory escaping map boundaries must be recorded as safety violation."""
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 12:
            e["payload"]["x"] = -0.5
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert result["safety_violations"] > 0
    assert any("map boundary" in v["type"] for v in result["violations"])


def test_fixture_24_state_obstacle_penetration():
    """24. Trajectory state colliding with obstacle fixture must be recorded as collision violation."""
    s = load_scenario("warehouse-transfer")
    obs = s.obstacles[0]
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 14:
            e["payload"]["x"] = obs.x
            e["payload"]["y"] = obs.y
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert result["safety_violations"] > 0
    assert any("collision" in v["type"] for v in result["violations"])


def test_fixture_25_state_obstacle_tunneling_segment_hazard():
    """25. Jumping across an obstacle between two discrete points must be caught by 2cm segment hazard check."""
    s = load_scenario("warehouse-transfer")
    obs = s.obstacles[0]
    dt = s.dt
    # Place state before obstacle and state after obstacle such that segment intersects obstacle
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 10:
            e["payload"]["x"] = obs.x - 1.5
            e["payload"]["y"] = obs.y
            e["payload"]["vx"] = 3.0 / dt
            e["payload"]["vy"] = 0.0
        elif e["kind"] == "state" and e["tick"] == 11:
            e["payload"]["x"] = obs.x + 1.5
            e["payload"]["y"] = obs.y
            e["payload"]["vx"] = 3.0 / dt
            e["payload"]["vy"] = 0.0
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert result["safety_violations"] > 0
    assert any("collision" in v["type"] for v in result["violations"])


def test_fixture_26_state_forbidden_zone_intrusion():
    """26. Trajectory entering forbidden restricted boundary must be flagged."""
    s = load_scenario("warehouse-transfer")
    zone = s.forbidden_zones[0]
    def mutate(e):
        if e["kind"] == "state" and e["tick"] == 16:
            e["payload"]["x"] = (zone.x1 + zone.x2) / 2.0
            e["payload"]["y"] = (zone.y1 + zone.y2) / 2.0
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert result["safety_violations"] > 0
    assert any("forbidden zone" in v["type"] for v in result["violations"])


# ==============================================================================
# Category F: Milestone & Task Postcondition Fraud (27 - 30)
# ==============================================================================

def test_fixture_27_milestone_claimed_out_of_order():
    """27. Claiming milestone index 1 before milestone index 0 must be rejected."""
    def mutate(e):
        if e["kind"] == "milestone" and e["payload"]["index"] == 0:
            e["payload"]["index"] = 1
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("milestone out of order" in r for r in result["failure_reasons"])


def test_fixture_28_milestone_claimed_outside_tolerance():
    """28. Claiming a waypoint when the robot's actual distance exceeds waypoint_tolerance must fail."""
    def mutate(e):
        # Scan station milestone is emitted at tick 26; displace robot state at tick 26
        if e["kind"] == "state" and e["tick"] == 26:
            e["payload"]["x"] = 0.5
            e["payload"]["y"] = 0.5
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("unproven milestone" in r for r in result["failure_reasons"])


def test_fixture_29_terminal_premature_completed_claim():
    """29. Claiming terminal 'completed' status when not all waypoints were reached must fail."""
    # Truncate before milestone 2 is reached
    clean = _get_clean_bundle()
    truncated_events = []
    for e in clean["events"]:
        truncated_events.append(e)
        if e["kind"] == "milestone" and e["payload"]["index"] == 0:
            break
    # Add a forged terminal event claiming completed
    ledger = Ledger()
    for e in truncated_events:
        ledger.emit(e["tick"], e["kind"], e["payload"])
    last_tick = truncated_events[-1]["tick"]
    ledger.emit(last_tick, "terminal", {"claimed": "completed", "claimed_stage": 1})
    b = copy.deepcopy(clean)
    b["events"] = ledger.events
    b["manifest"]["ledger_root_sha256"] = ledger.root
    b["manifest"]["simulation_steps"] = last_tick
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("task postcondition unfulfilled" in r for r in result["failure_reasons"])


def test_fixture_30_terminal_unknown_status_claim():
    """30. Terminal event claiming an unrecognised status string must be rejected."""
    def mutate(e):
        if e["kind"] == "terminal":
            e["payload"]["claimed"] = "faked-perfect-success"
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("invalid terminal status" in r for r in result["failure_reasons"])


# ==============================================================================
# Category G: Target Absence & Abstention Integrity (31 - 34)
# ==============================================================================

def test_fixture_31_absent_target_false_positive_completion():
    """31. Claiming 'completed' on an absent target scenario must be rejected as false positive."""
    clean_abs = _get_clean_bundle("absence-rejection", policy="route", seed=4)
    def mutate(e):
        if e["kind"] == "terminal":
            e["payload"]["claimed"] = "completed"
        return e
    b = _rebuild_chain_with_mutation(clean_abs, mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("false-positive target completion" in r for r in result["failure_reasons"])


def test_fixture_32_abstention_without_sufficient_negative_evidence():
    """32. Abstaining without at least 3 valid negative observations must be rejected."""
    clean_abs = _get_clean_bundle("absence-rejection", policy="route", seed=4)
    # Strip observation events or modify target_present to true
    def mutate(e):
        if e["kind"] == "observation":
            e["payload"]["target_present"] = True
        return e
    b = _rebuild_chain_with_mutation(clean_abs, mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("abstention without sufficient negative evidence" in r for r in result["failure_reasons"])


def test_fixture_33_abstention_on_present_target_scenario():
    """33. Emitting an abstention event when the scenario target was actually present must fail."""
    def mutate(e):
        if e["kind"] == "proposal":
            return {"tick": e["tick"], "kind": "abstain", "payload": {"reason": "bogus-abstain"}}
        return e
    b = _rebuild_chain_with_mutation(_get_clean_bundle(), mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("abstention without sufficient negative evidence" in r for r in result["failure_reasons"])


def test_fixture_34_abstention_after_excessive_dock_displacement():
    """34. Abstaining only after wandering away from dock (>0.5m) must be rejected as unjustified displacement."""
    clean_abs = _get_clean_bundle("absence-rejection", policy="route", seed=4)
    def mutate(e):
        if e["kind"] == "state":
            e["payload"]["x"] += 2.0  # Displace far away from dock
        return e
    b = _rebuild_chain_with_mutation(clean_abs, mutate)
    result = verify_bundle(b)
    assert not result["verified"]
    assert any("abstained only after unjustified displacement" in r or "initial state does not match" in r for r in result["failure_reasons"])


# ==============================================================================
# Category H: Harness & Event Schedule Completeness (35 - 37)
# ==============================================================================

def test_fixture_35_missing_action_observation_pairs():
    """35. Stripping observation events from simulation trace must fail action-observation pair completeness check."""
    b = _get_clean_bundle()
    def mutate(e):
        if e["kind"] == "observation":
            return None
        return e
    b_mut = _rebuild_chain_with_mutation(b, mutate)
    result = verify_bundle(b_mut)
    assert not result["verified"]
    assert any("missing action-observation pairs" in r for r in result["failure_reasons"])


def test_fixture_36_fault_schedule_omission():
    """36. Omission of scheduled injected faults (e.g. sensor dropout) must be detected."""
    b = _get_clean_bundle("warehouse-transfer", policy="route", seed=17)
    def mutate(e):
        if e["kind"] == "fault":
            return None
        return e
    b_mut = _rebuild_chain_with_mutation(b, mutate)
    result = verify_bundle(b_mut)
    assert not result["verified"]
    assert any("fault schedule incomplete" in r for r in result["failure_reasons"])


def test_fixture_37_terminal_event_missing_or_non_final():
    """37. Putting a state event after the terminal event must violate unique final terminal rule."""
    b = _get_clean_bundle()
    ledger = Ledger()
    for e in b["events"]:
        ledger.emit(e["tick"], e["kind"], e["payload"])
    # Append trailing event after terminal
    last_tick = b["events"][-1]["tick"]
    ledger.emit(last_tick + 1, "state", {"x": 1.0, "y": 1.0, "vx": 0.0, "vy": 0.0, "stage": 0})
    b_mut = copy.deepcopy(b)
    b_mut["events"] = ledger.events
    b_mut["manifest"]["ledger_root_sha256"] = ledger.root
    result = verify_bundle(b_mut)
    assert not result["verified"]
    assert any("missing unique final terminal event" in r for r in result["failure_reasons"])


# ==============================================================================
# Aggregate Verification of Gate 1 Acceptance Criterion
# ==============================================================================

ALL_FIXTURES = [
    test_fixture_01_hash_chain_payload_tamper,
    test_fixture_02_hash_chain_prev_hash_tamper,
    test_fixture_03_hash_chain_event_hash_tamper,
    test_fixture_04_hash_chain_event_deletion,
    test_fixture_05_hash_chain_event_insertion,
    test_fixture_06_hash_chain_event_reordering,
    test_fixture_07_manifest_ledger_root_mismatch,
    test_fixture_08_manifest_unknown_schema_version,
    test_fixture_09_tick_non_monotonic_sequence,
    test_fixture_10_scenario_contract_obstacle_shrink,
    test_fixture_11_scenario_contract_digest_tamper,
    test_fixture_12_clock_dt_mismatch,
    test_fixture_13_clock_step_limit_exceeded,
    test_fixture_14_manifest_step_count_mismatch,
    test_fixture_15_hmac_wrong_attestation_key,
    test_fixture_16_hmac_post_signing_manifest_alteration,
    test_fixture_17_external_telemetry_unattested_provenance,
    test_fixture_18_state_non_finite_coordinate,
    test_fixture_19_state_tick_gap,
    test_fixture_20_state_speed_limit_exceeded,
    test_fixture_21_state_kinematic_teleport,
    test_fixture_22_state_initial_position_mismatch,
    test_fixture_23_state_boundary_escape,
    test_fixture_24_state_obstacle_penetration,
    test_fixture_25_state_obstacle_tunneling_segment_hazard,
    test_fixture_26_state_forbidden_zone_intrusion,
    test_fixture_27_milestone_claimed_out_of_order,
    test_fixture_28_milestone_claimed_outside_tolerance,
    test_fixture_29_terminal_premature_completed_claim,
    test_fixture_30_terminal_unknown_status_claim,
    test_fixture_31_absent_target_false_positive_completion,
    test_fixture_32_abstention_without_sufficient_negative_evidence,
    test_fixture_33_abstention_on_present_target_scenario,
    test_fixture_34_abstention_after_excessive_dock_displacement,
    test_fixture_35_missing_action_observation_pairs,
    test_fixture_36_fault_schedule_omission,
    test_fixture_37_terminal_event_missing_or_non_final,
]


def test_gate1_adversarial_fixture_count_and_recall():
    """Preregistered Acceptance Gate 1:

    - At least 30 preregistered adversarial fixtures.
    - 100% detection rate across all defined tamper cases.
    """
    assert len(ALL_FIXTURES) >= 30, f"Expected >= 30 fixtures, found {len(ALL_FIXTURES)}"
    # Verify each fixture callable runs and successfully detects tampering
    for fixture in ALL_FIXTURES:
        fixture()
