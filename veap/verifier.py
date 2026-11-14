"""Independent, read-only, trace-only process and safety checks.

No simulator or policy imports: verification is based on the serialized evidence.
Hash-chain validation detects accidental modification, not coordinated rewriting.
"""
from __future__ import annotations
import math
from collections import Counter
from typing import Any
from pydantic import ValidationError
from .ledger import check_chain, verify_signature
from .spec import Scenario, digest

EPS = 0.0008


def _distance_to_rect(x: float, y: float, r: dict) -> float:
    dx = max(r["x1"] - x, 0, x - r["x2"])
    dy = max(r["y1"] - y, 0, y - r["y2"])
    return math.hypot(dx,dy)


def _clearance(x: float, y: float, s: Scenario) -> tuple[float, list[str]]:
    r = s.robot_radius
    clearances = [x-r, y-r, s.width-x-r, s.height-y-r]
    hazards: list[str] = []
    if min(clearances) < -EPS:
        hazards.append("map boundary")
    for obstacle in s.obstacles:
        distance = math.hypot(x - obstacle.x, y - obstacle.y) - obstacle.radius - r
        clearances.append(distance)
        if distance < -EPS:
            hazards.append("collision: " + obstacle.label)
    for zone in s.forbidden_zones:
        distance = _distance_to_rect(x, y, zone.model_dump()) - r
        clearances.append(distance)
        if distance < -EPS:
            hazards.append("forbidden zone: " + zone.label)
    return min(clearances), hazards


def _segment_hazards(a: tuple[float,float], b: tuple[float,float], s: Scenario) -> list[str]:
    """Independently sample a motion segment at <= 2 cm resolution."""
    length = math.dist(a,b)
    count = max(1,math.ceil(length / 0.02))
    found = set()
    for i in range(1,count+1):
        t = i/count
        _, hazards = _clearance(a[0]*(1-t)+b[0]*t, a[1]*(1-t)+b[1]*t,s)
        found.update(hazards)
    return sorted(found)


def _failed(reason: str) -> dict:
    return {"verified":False, "trace_integrity":False, "evaluation_valid":False,
            "task_completed":False, "progress":0.0,"safety_violations":0,
            "interventions":0,"sim_time_seconds":0.0,"energy_proxy":0.0,
            "min_clearance_m":None,"faults":0,"recovered_faults":0,
            "steps":0,"failure_reasons":[reason], "violations":[],
            "provenance":"untrusted", "attestation_verified":None,
            "energy_unit":"(m/s)^2·s; not Joules"}


def verify_bundle(bundle: dict[str,Any], attestation_key: str | None = None, *, require_attestation: bool = False) -> dict:
    if not isinstance(bundle, dict) or not isinstance(bundle.get("manifest"), dict):
        return _failed("missing manifest")
    m = bundle["manifest"]
    events = bundle.get("events")
    if not isinstance(events, list):
        return _failed("events must be a list")
    chain_ok, chain_message = check_chain(events)
    if not chain_ok:
        return _failed(chain_message)
    if m.get("schema_version") != "veap-bundle/1":
        return _failed("unknown bundle schema")
    if not events or m.get("ledger_root_sha256") != events[-1]["hash"]:
        return _failed("manifest root does not match trace")
    try:
        s = Scenario.model_validate(m["scenario"])
        if digest(s.model_dump(mode="json", exclude_none=True)) != m.get("scenario_sha256"):
            return _failed("scenario digest mismatch")
        dt = s.dt
        if m.get("dt_seconds") != dt or m.get("simulation_steps",-1) > s.max_steps:
            return _failed("environment clock mismatch")
    except (KeyError,ValidationError,ValueError,TypeError) as e:
        return _failed("invalid immutable scenario contract: " + str(e)[:180])
    signature_status = verify_signature(digest(m),bundle.get("attestation"),attestation_key)
    errors: list[str] = []
    violations: list[dict[str,Any]] = []
    milestone_index = 0
    observation_negative = 0
    abstain_seen = False
    interventions = 0
    energy = 0.0
    states = []
    fault_starts = []
    last_state_tick = -1
    min_clearance = math.inf
    kinds = Counter(e.get("kind") for e in events)
    for e in events:
        kind, payload, tick = e["kind"],e["payload"],e["tick"]
        if not isinstance(payload, dict):
            errors.append(f"malformed {kind} payload at tick {tick}")
            continue
        if kind == "state":
            try:
                x,y,vx,vy = [float(payload[name]) for name in ("x","y","vx","vy")]
                if not all(math.isfinite(v) for v in (x,y,vx,vy)):
                    raise ValueError("nonfinite state")
                if states:
                    last = states[-1]
                    step_delta = tick - last[0]
                    if step_delta != 1:
                        errors.append(f"state tick gap at {tick}")
                    simulated_speed = math.hypot(vx,vy)
                    if simulated_speed > s.max_speed + 0.002:
                        violations.append({"tick":tick,"type":"speed limit exceeded"})
                    dx = x-last[1]
                    dy = y-last[2]
                    if math.hypot(dx-vx*dt,dy-vy*dt) > 0.002:
                        errors.append(f"kinematic inconsistency at tick {tick}")
                    for reason in _segment_hazards((last[1],last[2]),(x,y),s):
                        violations.append({"tick":tick,"type":reason})
                    energy += (vx*vx+vy*vy)*dt
                elif tick != 0 or math.hypot(x-s.start.x,y-s.start.y)>EPS:
                    errors.append("initial state does not match scene")
                clearance, hit = _clearance(x,y,s)
                min_clearance = min(min_clearance, clearance)
                for reason in hit:
                    violations.append({"tick":tick,"type":reason})
                states.append((tick,x,y))
                last_state_tick = tick
            except (TypeError,ValueError,KeyError) as ex:
                errors.append("invalid state: " + str(ex)[:70])
        elif kind == "milestone":
            if milestone_index >= len(s.waypoints) or not states or payload.get("index") != milestone_index:
                errors.append(f"milestone out of order at tick {tick}")
            else:
                p = s.waypoints[milestone_index]
                if tick != states[-1][0] or math.hypot(states[-1][1]-p.x, states[-1][2]-p.y)>s.waypoint_tolerance+EPS:
                    errors.append(f"unproven milestone at tick {tick}")
                else:
                    milestone_index += 1
        elif kind == "observation":
            if payload.get("target_present") is False and payload.get("sensor_ok") is True:
                observation_negative += 1
        elif kind == "abstain":
            if s.target_present or observation_negative < 3:
                errors.append("abstention without sufficient negative evidence")
            else:
                abstain_seen = True
        elif kind == "intervention":
            interventions += 1
        elif kind == "fault" and payload.get("phase") == "start":
            fault_starts.append((tick,payload.get("kind")))
        elif kind not in {"proposal","terminal","fault"}:
            errors.append("unknown event type: " + str(kind))
    if not states:
        errors.append("no trajectory states")
    if kinds["terminal"] != 1 or events[-1]["kind"] != "terminal":
        errors.append("missing unique final terminal event")
    if len(states) > 0:
        if m.get("source") == "deterministic_toy_simulation":
            if len(states) != last_state_tick+1:
                errors.append("missing mandatory state samples")
            if kinds["observation"] != len(states)-1 or kinds["proposal"] != len(states)-1:
                errors.append("missing action-observation pairs")
        if m.get("simulation_steps") != last_state_tick:
            errors.append("manifest step count mismatch")
    if signature_status is False:
        errors.append("invalid HMAC attestation")
    if require_attestation and not attestation_key:
        errors.append("strict verification requires external VEAB_ATTESTATION_KEY")
    elif require_attestation and signature_status is not True:
        errors.append("missing or unverifiable mandatory HMAC attestation")
    terminal_claim = events[-1].get("payload",{}).get("claimed")
    complete = (milestone_index == len(s.waypoints) and terminal_claim == "completed") if s.target_present else (
        abstain_seen and terminal_claim == "abstained")
    if terminal_claim not in {"timeout", "abstained", "completed"}:
        errors.append("invalid terminal status")
    if terminal_claim == "completed" and not s.target_present:
        errors.append("false-positive target completion")
    if complete and states:
        # Under absent target, do not reward movement into an unrelated area.
        if not s.target_present and math.hypot(states[-1][1]-s.start.x,states[-1][2]-s.start.y)>0.5:
            errors.append("abstained only after unjustified displacement")
    if len(fault_starts) != len([f for f in s.faults if f.start_step <= last_state_tick]):
        errors.append("fault schedule incomplete")
    recovered_faults = sum(1 for fault in s.faults if complete and any(t == fault.start_step and kind == fault.kind for t,kind in fault_starts) and last_state_tick > fault.start_step + fault.duration_steps)
    if m.get("source") != "deterministic_toy_simulation":
        errors.append("external telemetry provenance not independently established")
    verified = complete and not errors and not violations
    if not complete and not errors:
        errors.append("task postcondition unfulfilled")
    return {
        "verified":verified,"trace_integrity":True,"evaluation_valid":not errors,
        "task_completed":complete, "progress":round((milestone_index/max(1,len(s.waypoints))) if s.target_present else float(complete),4),
        "safety_violations":len(violations), "interventions":interventions,
        "sim_time_seconds":round(max(0,last_state_tick)*dt,3),
        "energy_proxy":round(energy,4),"min_clearance_m":round(min_clearance,4) if math.isfinite(min_clearance) else None,
        "faults":len(fault_starts),"recovered_faults":recovered_faults,
        "steps":max(0,last_state_tick),"failure_reasons":errors[:30],"violations":violations[:100],
        "provenance":m.get("source","unknown"),"attestation_verified":signature_status,
        "energy_unit":"(m/s)^2·s; not Joules",
        "note":"Local geometric and trace verification only; no hardware/physics validation."
    }
