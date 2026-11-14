"""Independent-implementation VEAP R1 certificate monitor.

Standard-library only. Does not import the agent, simulator, VEAP evaluator,
or a claimed verdict. Independently reconstructs evidence-sufficiency intervals
and checks proof obligations, witnesses and hashes—not merely result labels.

This is implementation independence with SHARED physical assumptions; it is
not independent sensor attestation, organisational IV&V or safety certification.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

EPS = 1e-8


def digest(obj):
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rect_clearance(x, y, zone):
    left, bottom, right, top = zone
    dx = max(left - x, x - right, 0.0)
    dy = max(bottom - y, y - top, 0.0)
    if dx or dy:
        return math.hypot(dx, dy)
    return -min(x - left, right - x, y - bottom, top - y)


def reconstruct(contract, trace):
    """Return independent rule verdicts plus self-computed proof obligations."""
    begin = float(contract["mission_start_s"])
    end = float(contract["mission_end_s"])
    speed = float(contract["max_speed_mps"])
    uncertainty = float(contract["position_uncertainty_m"])
    radius = float(contract["robot_radius_m"])
    pad = radius + uncertainty
    observed = []
    intervals = []
    by_id = {}
    bad_trace = False
    last_clock = None

    for index, record in enumerate(trace["samples"]):
        identity = record.get("event_id", f"sample:{index}")
        if not isinstance(identity, str) or not identity or identity in by_id:
            bad_trace = True
            continue
        by_id[identity] = record
        if not all(key in record for key in ("t_s", "x", "y")):
            continue
        t = record["t_s"]
        if last_clock is not None and t <= last_clock:
            bad_trace = True
        last_clock = t
        if not begin <= t <= end:
            continue
        if record.get("frame_id") != contract["frame_id"]:
            continue
        if record.get("sensor_healthy") is not True:
            continue
        if not set(contract["required_topics"]).issubset(record.get("topics", [])):
            continue
        clear = rect_clearance(record["x"], record["y"], contract["keepout"])
        overlaps = (clear + uncertainty < radius)
        item = {"t": t, "x": record["x"], "y": record["y"],
                "ref": identity, "clearance": clear, "overlap": overlaps}
        observed.append(item)
        horizon = max(0.0, (clear - pad) / speed)
        if horizon > 0:
            intervals.append((max(begin, t - horizon), min(end, t + horizon), identity))

    if not bad_trace:
        for before, after in zip(observed, observed[1:]):
            possible_movement = speed * (after["t"] - before["t"]) + 2 * uncertainty
            actual_movement = math.hypot(after["x"] - before["x"], after["y"] - before["y"])
            if actual_movement > possible_movement + 1e-9:
                bad_trace = True
                break

    if bad_trace:
        # Explicitly do not claim a violation from a mutually inconsistent
        # evidence record; such a witness may be physically impossible.
        observed, intervals = [], []

    # Endpoint scan is deliberately different from the evaluator's interval
    # construction and permits auditing the exact uncovered windows.
    open_windows = []
    cursor = begin
    for lo, hi, _ in sorted(intervals):
        if hi <= cursor:
            continue
        if lo > cursor + 1e-9:
            open_windows.append([round(cursor, 8), round(lo, 8)])
        cursor = max(cursor, hi)
    if cursor < end - 1e-9:
        open_windows.append([round(cursor, 8), round(end, 8)])

    zone_is_violating = any(record["overlap"] for record in observed)
    zone_is_compliant = bool(intervals) and not open_windows and not zone_is_violating
    zone = "VIOLATING" if zone_is_violating else "COMPLIANT" if zone_is_compliant else "INCONCLUSIVE"

    terminal = "INCONCLUSIVE"
    terminal_proof = None
    terminal_gap = None
    if observed:
        last = observed[-1]
        tolerance = float(contract["goal"]["tolerance_m"])
        dist = math.hypot(last["x"] - contract["goal"]["x"],
                          last["y"] - contract["goal"]["y"])
        reach = uncertainty + speed * (end - last["t"])
        if dist + reach <= tolerance + 1e-9:
            terminal = "COMPLIANT"
            terminal_proof = {"type": "terminal_goal_certified", "ref": last["ref"],
                              "upper": dist + reach}
        elif dist - reach > tolerance + 1e-9:
            terminal = "VIOLATING"
            terminal_proof = {"type": "goal_not_reached_at_deadline", "ref": last["ref"],
                              "lower": max(0.0, dist - reach)}
        else:
            terminal_gap = [round(last["t"], 8), round(end, 8)]
    else:
        terminal_gap = [round(begin, 8), round(end, 8)]

    combined = ("VIOLATING" if "VIOLATING" in (zone, terminal)
                else "INCONCLUSIVE" if "INCONCLUSIVE" in (zone, terminal)
                else "COMPLIANT")
    return {"verdict": combined, "keepout_continuous": zone,
            "goal_at_deadline": terminal, "open_windows": open_windows,
            "terminal_gap": terminal_gap, "terminal_proof": terminal_proof,
            "safe_intervals": intervals, "records": observed,
            "record_map": by_id, "trace_inconsistent": bad_trace,
            "observed_violation_refs": [v["ref"] for v in observed if v["overlap"]]}


def independent_verdict(contract, trace):
    calc = reconstruct(contract, trace)
    return {k: calc[k] for k in ("verdict", "keepout_continuous", "goal_at_deadline")}


def _interval_equal(left, right):
    return (isinstance(left, list) and isinstance(right, list) and
            len(left) == 2 and len(right) == 2 and
            all(isinstance(x, (float, int)) and isinstance(y, (float, int)) and
                abs(x - y) <= EPS for x, y in zip(left, right)))


def _exact_interval_set(reported, reference):
    return (isinstance(reported, list) and len(reported) == len(reference)
            and all(_interval_equal(x, y) for x, y in zip(reported, reference)))


def _interval_coverage_from_refs(calc, refs, contract):
    """Whether listed observations alone prove continuous exclusion-zone clearance."""
    if not isinstance(refs, list) or not refs:
        return False
    allowed = set(refs)
    if not allowed.issubset({p["ref"] for p in calc["records"]}):
        return False
    ordered = sorted((a, b) for a, b, ref in calc["safe_intervals"] if ref in allowed)
    if not ordered:
        return False
    cursor = contract["mission_start_s"]
    for lo, hi in ordered:
        if lo > cursor + 1e-9:
            return False
        cursor = max(cursor, hi)
    return cursor >= contract["mission_end_s"] - 1e-9


def inspect(contract, trace, cert, source_bytes=None):
    errors = []
    original = dict(cert)
    declared_checksum = original.pop("certificate_sha256", None)
    if digest(original) != declared_checksum:
        errors.append("certificate_sha256 mismatch")
    if digest(contract) != cert.get("contract_sha256"):
        errors.append("contract_sha256 mismatch")
    if digest(trace) != cert.get("trace_canonical_sha256"):
        errors.append("trace_canonical_sha256 mismatch")
    if cert.get("source_hash_mode") not in ("raw_bytes", "canonical_json"):
        errors.append("source hash mode unsupported")
    expected_hash = (hashlib.sha256(source_bytes).hexdigest()
                     if cert.get("source_hash_mode") == "raw_bytes" and source_bytes is not None
                     else digest(trace))
    if cert.get("source_sha256") != expected_hash:
        errors.append("source_sha256 mismatch")
    if cert.get("source_authenticity") != "UNATTESTED":
        errors.append("unsupported source authenticity assertion")

    calc = reconstruct(contract, trace)
    if cert.get("verdict") != calc["verdict"]:
        errors.append("verdict differs from reference implementation")
    for rule in ("keepout_continuous", "goal_at_deadline"):
        if cert.get("requirements", {}).get(rule, {}).get("verdict") != calc[rule]:
            errors.append(f"{rule}: reference disagreement")

    zone = cert.get("requirements", {}).get("keepout_continuous", {})
    goal = cert.get("requirements", {}).get("goal_at_deadline", {})
    windows = zone.get("unresolved_intervals", [])
    extracted_zone = [r.get("interval_s") for r in windows]
    if not _exact_interval_set(extracted_zone, calc["open_windows"]):
        errors.append("zone uncovered intervals are not justified by observations")
    expected_goal = [calc["terminal_gap"]] if calc["terminal_gap"] is not None else []
    extracted_goal = [r.get("interval_s") for r in goal.get("unresolved_intervals", [])]
    if not _exact_interval_set(extracted_goal, expected_goal):
        errors.append("goal unresolved interval is not justified by observations")
    combined_gaps = windows + goal.get("unresolved_intervals", [])
    if cert.get("unresolved_coverage", []) != combined_gaps:
        errors.append("summary unresolved coverage differs from requirement obligations")

    observed = {p["ref"]: p for p in calc["records"]}
    claims = cert.get("confirmed_violations", [])
    should_zone = set(calc["observed_violation_refs"])
    reported_zone = {w.get("evidence_ref") for w in claims if w.get("type") == "confirmed_keepout_overlap"}
    if should_zone != reported_zone:
        errors.append("reported exclusion-zone witnesses do not match provable overlaps")
    should_goal = set([calc["terminal_proof"]["ref"]]
                      if calc["terminal_proof"] and calc["terminal_proof"]["type"] == "goal_not_reached_at_deadline"
                      else [])
    reported_goal = {w.get("evidence_ref") for w in claims if w.get("type") == "goal_not_reached_at_deadline"}
    if should_goal != reported_goal:
        errors.append("goal failure witness does not match reference")
    if any(w.get("type") not in ("confirmed_keepout_overlap", "goal_not_reached_at_deadline") for w in claims):
        errors.append("unknown failure witness type")

    witnesses = cert.get("evidence_witnesses", [])
    for item in witnesses:
        role = item.get("type")
        ref = item.get("evidence_ref")
        if role == "continuous_keepout_coverage":
            if calc["keepout_continuous"] != "COMPLIANT" or not _interval_coverage_from_refs(calc, item.get("evidence_refs"), contract):
                errors.append("continuous coverage claim lacks sufficient evidence references")
        elif role == "terminal_goal_certified":
            if (not calc["terminal_proof"] or calc["terminal_proof"]["type"] != role or
                    ref != calc["terminal_proof"]["ref"]):
                errors.append("terminal goal witness is unsupported")
        elif role == "goal_not_reached_at_deadline":
            if ref not in reported_goal:
                errors.append("reported terminal failure evidence is unsupported")
        elif role == "confirmed_keepout_overlap":
            if ref not in should_zone:
                errors.append("reported zone violation evidence is unsupported")
        else:
            errors.append("unsupported evidence witness type")
    if calc["keepout_continuous"] == "COMPLIANT" and not any(
        w.get("type") == "continuous_keepout_coverage" for w in witnesses):
        errors.append("missing positive continuous-safety witness")
    if calc["goal_at_deadline"] == "COMPLIANT" and not any(
        w.get("type") == "terminal_goal_certified" for w in witnesses):
        errors.append("missing positive terminal-goal witness")

    return {"certificate_check": "PASS" if not errors else "FAIL",
            "reference_verdict": calc["verdict"],
            "per_requirement_reference": {"keepout_continuous": calc["keepout_continuous"],
                                          "goal_at_deadline": calc["goal_at_deadline"]},
            "errors": errors,
            "independence": "separate_implementation_same_stated_motion_assumptions",
            "source_authenticity": "UNATTESTED",
            "proof_obligations_checked": ["contract_trace_identity", "uncovered_intervals",
                                          "violation_witnesses", "positive_coverage_witnesses",
                                          "deadline_goal_witnesses"]}


def main():
    try:
        if len(sys.argv) not in (3, 4):
            print("Usage: python external_monitor/monitor.py contract.json trace.json [certificate.json]", file=sys.stderr)
            return 2
        contract = json.loads(Path(sys.argv[1]).read_text())
        raw = Path(sys.argv[2]).read_bytes()
        trace = json.loads(raw)
        if len(sys.argv) == 3:
            print(json.dumps({"monitor": "independent-implementation", "reference": independent_verdict(contract, trace)}, indent=2))
            return 0
        cert = json.loads(Path(sys.argv[3]).read_text())
        result = inspect(contract, trace, cert, raw)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["certificate_check"] == "PASS" else 1
    except Exception as exc:
        print(json.dumps({"certificate_check": "FAIL", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
