"""VEAP R1: three-valued, requirement-specific evidence-sufficiency certificates.

NOT a safety certification or a general temporal-logic model checker.
PASS requires declared/externally justified bounds on speed, pose error and
clock. Unattested observations cannot prove the truth of a physical sensor.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

STATES = {"COMPLIANT", "VIOLATING", "INCONCLUSIVE"}


class EvaluationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _reject_nonfinite(value):
    raise EvaluationError("Non-finite JSON token: " + value)


def load_record(path):
    data = Path(path).read_bytes()
    if len(data) > 10_000_000:
        raise EvaluationError("Input exceeds 10 MB bound")
    try:
        return json.loads(data, parse_constant=_reject_nonfinite), hashlib.sha256(data).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(str(exc)) from exc


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise EvaluationError(f"{name}: expected finite numeric value")
    return float(value)


def _signed_distance(pos, zone):
    """Signed point-to-closed-rectangle distance; negative means inside."""
    x, y = pos
    left, bottom, right, top = zone
    dx, dy = max(left-x, 0.0, x-right), max(bottom-y, 0.0, y-top)
    if dx or dy:
        return math.hypot(dx, dy)
    return -min(x-left, right-x, y-bottom, top-y)


def _validate(contract, trace):
    if not isinstance(contract, dict) or contract.get("schema") != "veap.evidence.contract/1":
        raise EvaluationError("Unsupported contract schema")
    if not isinstance(trace, dict) or trace.get("schema") != "veap.evidence.trace/1":
        raise EvaluationError("Unsupported trace schema")
    needed = ("mission_start_s", "mission_end_s", "max_speed_mps", "robot_radius_m",
              "position_uncertainty_m", "max_gap_s")
    for key in needed:
        finite(contract.get(key), key)
    start, end = contract["mission_start_s"], contract["mission_end_s"]
    if start >= end:
        raise EvaluationError("Mission window must have positive duration")
    if contract["max_speed_mps"] <= 0 or contract["robot_radius_m"] <= 0 or contract["max_gap_s"] <= 0 or contract["position_uncertainty_m"] < 0:
        raise EvaluationError("Invalid motion/evidence limits")
    z = contract.get("keepout")
    if not isinstance(z, list) or len(z) != 4:
        raise EvaluationError("keepout must be a rectangle")
    for i, v in enumerate(z):
        finite(v, f"keepout[{i}]")
    if z[0] >= z[2] or z[1] >= z[3]:
        raise EvaluationError("Inverted keepout")
    goal = contract.get("goal")
    if not isinstance(goal, dict):
        raise EvaluationError("Missing terminal goal")
    for k in ("x", "y", "tolerance_m"):
        finite(goal.get(k), f"goal.{k}")
    if goal["tolerance_m"] <= 0:
        raise EvaluationError("Goal tolerance must be positive")
    if not isinstance(contract.get("frame_id"), str) or not contract["frame_id"]:
        raise EvaluationError("Missing coordinate frame")
    topics = contract.get("required_topics")
    if not isinstance(topics, list) or not topics or any(not isinstance(t, str) or not t for t in topics):
        raise EvaluationError("Invalid required_pose_channels")
    if trace.get("source_kind") not in {"synthetic", "recorded_unattested", "native_sim_unattested"}:
        raise EvaluationError("Unknown evidence source category")
    obs = trace.get("samples")
    if not isinstance(obs, list) or len(obs) > 500_000:
        raise EvaluationError("Invalid or oversized observation sequence")
    for i, sample in enumerate(obs):
        if not isinstance(sample, dict):
            raise EvaluationError("Invalid observation object")
        for key in ("t_s", "x", "y"):
            if key in sample:
                finite(sample[key], f"samples[{i}].{key}")
        if "topics" in sample and (not isinstance(sample["topics"], list) or
                                   any(not isinstance(x, str) for x in sample["topics"])):
            raise EvaluationError("Invalid observation topic list")


def _status(fail, unknown):
    return "VIOLATING" if fail else "INCONCLUSIVE" if unknown else "COMPLIANT"


def evaluate(contract, trace, source_sha256=None):
    """Evaluate goal-at-deadline and continuous keep-out constraints.

    Proof rule: at time t, an observation with clearance d proves no footprint
    overlap for |t-t_obs| < (d - radius - pose_error)/speed. The union of those
    intervals must cover the mission window. This is a sufficient, not necessary,
    condition and is valid ONLY if the declared bounds hold physically.
    """
    _validate(contract, trace)
    start, end, speed = [contract[k] for k in ("mission_start_s", "mission_end_s", "max_speed_mps")]
    radius, uncertainty = contract["robot_radius_m"], contract["position_uncertainty_m"]
    failures, diagnostic, observations, witnesses, coverage = [], [], [], [], []
    last_seen_t = None
    refs_seen = set()
    for i, row in enumerate(trace["samples"]):
        ref = row.get("event_id", f"sample:{i}")
        if not isinstance(ref, str) or not ref or ref in refs_seen:
            diagnostic.append({"type":"untrusted_event_identifier", "row_index":i, "evidence_ref":str(ref)})
            continue
        refs_seen.add(ref)
        if any(k not in row for k in ("t_s", "x", "y")):
            diagnostic.append({"type":"missing_pose", "evidence_ref":ref})
            continue
        t, xy = row["t_s"], (row["x"], row["y"])
        if last_seen_t is not None and t <= last_seen_t:
            diagnostic.append({"type":"non_monotonic_clock", "evidence_ref":ref})
        last_seen_t = t
        if not start <= t <= end:
            diagnostic.append({"type":"outside_mission_window", "evidence_ref":ref})
            continue
        if row.get("frame_id") != contract["frame_id"]:
            diagnostic.append({"type":"unverified_frame", "evidence_ref":ref})
            continue
        if row.get("sensor_healthy") is not True:
            diagnostic.append({"type":"sensor_unhealthy", "evidence_ref":ref})
            continue
        missing = sorted(set(contract["required_topics"]) - set(row.get("topics", [])))
        if missing:
            diagnostic.append({"type":"missing_required_pose_channel", "evidence_ref":ref, "topics":missing})
            continue
        d = _signed_distance(xy, contract["keepout"])
        if d + uncertainty < radius:
            failures.append({"type":"confirmed_keepout_overlap", "evidence_ref":ref,
                             "t_s":t, "signed_clearance_m":round(d, 8)})
        safe_radius = max(0.0, (d - radius - uncertainty)/speed)
        observations.append((t, xy, ref, safe_radius))
        if safe_radius > 0:
            coverage.append((max(start, t-safe_radius), min(end, t+safe_radius), ref))

    # For conservatism, malformed clock order cannot be repaired by sorting.
    time_order_defect = any(x["type"] in ("non_monotonic_clock", "untrusted_event_identifier") for x in diagnostic)
    # A contradiction between two purportedly bounded-speed observations
    # invalidates any purported positive continuous-motion proof.
    if not time_order_defect:
        for a0,b0 in zip(observations,observations[1:]):
            t0,p0,ref0,_=a0
            t1,p1,ref1,_=b0
            displacement=math.hypot(p1[0]-p0[0],p1[1]-p0[1])
            if displacement > speed*(t1-t0) + 2*uncertainty + 1e-9:
                diagnostic.append({"type":"inconsistent_motion_bound", "evidence_refs":[ref0,ref1],
                                   "interval_s":[t0,t1],
                                   "request":"Reconcile clock, pose error, or maximum-speed assumption"})
                time_order_defect=True
    if not time_order_defect:
        for a0,b0 in zip(observations,observations[1:]):
            if b0[0]-a0[0] > contract["max_gap_s"]+1e-9:
                diagnostic.append({"type":"nominal_recording_gap", "interval_s":[a0[0],b0[0]],
                                   "not_automatically_inconclusive":True})
    if time_order_defect:
        # Conflicting clock/identity/kinematic evidence invalidates the common
        # motion model. Revoke provisional failure witnesses too: one cannot
        # treat an impossible trajectory as ground truth for an unsafe event.
        # Mere absence of a different observation is NOT a contradiction and
        # must never erase a well-supported violation.
        if failures:
            diagnostic.append({"type":"provisional_violation_withdrawn_due_to_trace_contradiction",
                               "evidence_refs":[f["evidence_ref"] for f in failures]})
        failures = []
        coverage = []
        observations = []
    else:
        coverage.sort(key=lambda x: (x[0], x[1]))

    open_intervals = []
    cursor = start
    attached = []
    for left, right, ref in coverage:
        if right <= cursor:
            continue
        if left > cursor + 1e-9:
            open_intervals.append({"interval_s":[round(cursor,8),round(left,8)],
                                   "type":"unproven_keepout_coverage",
                                   "request":"Obtain calibrated pose observations or tighter motion bounds"})
        cursor = right
        attached.append(ref)
    if cursor < end - 1e-9:
        open_intervals.append({"interval_s":[round(cursor,8),round(end,8)],
                               "type":"unproven_keepout_coverage",
                               "request":"Obtain calibrated pose observations or tighter motion bounds"})
    if not coverage and not open_intervals:
        open_intervals.append({"interval_s":[start,end],"type":"missing_whole_pose_trace"})

    keep_status = _status(failures, open_intervals)
    # One certified violation remains a VIOLATION, even with unrelated gaps.
    if failures:
        witnesses.extend(failures)
    elif keep_status == "COMPLIANT":
        witnesses.append({"type":"continuous_keepout_coverage", "evidence_refs":sorted(set(attached)),
                          "assurance":"conditional_motion_bound", "interval_s":[start,end]})

    goal_unknown, goal_fail, goal_witness = [], [], []
    if observations:
        t, pos, ref, _ = observations[-1]
        dist = math.hypot(pos[0]-contract["goal"]["x"], pos[1]-contract["goal"]["y"])
        epistemic_radius = uncertainty + speed*(end-t)
        tol = contract["goal"]["tolerance_m"]
        if dist + epistemic_radius <= tol + 1e-9:
            goal_witness.append({"type":"terminal_goal_certified", "evidence_ref":ref,
                                 "t_s":t,"distance_upper_bound_m":round(dist+epistemic_radius,8)})
        elif dist - epistemic_radius > tol + 1e-9:
            goal_fail.append({"type":"goal_not_reached_at_deadline", "evidence_ref":ref,
                              "distance_lower_bound_m":round(max(0.0,dist-epistemic_radius),8)})
        else:
            goal_unknown.append({"type":"terminal_goal_unresolved", "interval_s":[t,end],
                                 "evidence_ref":ref,"request":"Provide deadline-anchored pose evidence"})
    else:
        goal_unknown.append({"type":"terminal_goal_unresolved", "interval_s":[start,end],
                             "request":"Provide observed final robot position in calibrated frame"})
    goal_status = _status(goal_fail, goal_unknown)
    combined = _status(failures+goal_fail, open_intervals+goal_unknown)
    cert = {
        "certificate_schema":"veap.evidence.sufficiency/1",
        "verdict":combined,
        "contract_sha256":canonical_hash(contract),
        "trace_canonical_sha256":canonical_hash(trace),
        "source_sha256":source_sha256 or canonical_hash(trace),
        "source_hash_mode":"raw_bytes" if source_sha256 else "canonical_json",
        "source_kind":trace["source_kind"],
        "source_authenticity":"UNATTESTED",
        "scope":"Specified goal and exclusion-zone requirements under declared motion and pose-error bounds; no physical safety certification",
        "assumptions":["Maximum translational speed bound applies over every unobserved interval",
                       "Position error is never greater than the stated uncertainty",
                       "Frame, clock and mission window are correct, and source records are genuine"],
        "requirements": {
            "keepout_continuous":{"verdict":keep_status, "witnesses":failures if failures else witnesses,
                                  "unresolved_intervals":open_intervals},
            "goal_at_deadline":{"verdict":goal_status,"witnesses":goal_fail+goal_witness,
                                "unresolved_intervals":goal_unknown},
        },
        "confirmed_violations": failures+goal_fail,
        "missing_evidence_diagnostics":diagnostic,
        "unresolved_coverage":open_intervals+goal_unknown,
        "evidence_witnesses":witnesses+goal_witness,
        "observed_samples":len(trace["samples"]),
        "eligible_pose_samples":len(observations),
    }
    cert["certificate_sha256"] = canonical_hash(cert)
    return cert
