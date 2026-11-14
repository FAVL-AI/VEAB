"""Constructive ambiguity witness for a *specified synthetic* observation gap.

This is NOT a generic model checker and not a claim about real sensor truth.
A pair of bounded-speed piecewise-linear completions demonstrates that the
same available observations cannot decide a continuous keep-out requirement.
"""
from __future__ import annotations

from copy import deepcopy
from .verdict import canonical_hash, EvaluationError


def construct_gap_pair(contract: dict, trace: dict, at_time_s: float | None = None) -> dict:
    """Propose safe and violating completions, or refuse unsupported geometry.

    An external implementation MUST independently validate all knots, bound
    assumptions and geometry. The two candidate paths intentionally share the
    exact available observations, so this is an identifiability control.
    """
    good = []
    for event in trace.get("samples", []):
        if (all(k in event for k in ("t_s", "x", "y")) and
                event.get("sensor_healthy") is True and
                event.get("frame_id") == contract.get("frame_id") and
                set(contract.get("required_topics", [])).issubset(event.get("topics", []))):
            good.append(event)
    good.sort(key=lambda s: s["t_s"])
    if len(good) < 2:
        raise EvaluationError("Two usable observations are required")
    if len({e["t_s"] for e in good}) != len(good):
        raise EvaluationError("Duplicated observation timestamps")
    zone = contract["keepout"]
    xc, yc = (zone[0] + zone[2]) / 2, (zone[1] + zone[3]) / 2
    # Restrict to one truly missing observation interval, not an observed time.
    intervals = [(a, b) for a, b in zip(good, good[1:])
                 if a["t_s"] < (at_time_s if at_time_s is not None else (a["t_s"] + b["t_s"]) / 2) < b["t_s"]]
    if at_time_s is None:
        # Prefer a gap straddling the horizontal middle of the exclusion region.
        candidates = [(a, b) for a, b in zip(good, good[1:]) if a["x"] < xc < b["x"]]
        if len(candidates) != 1:
            raise EvaluationError("Cannot select an unambiguous observation gap")
        a, b = candidates[0]
        tm = (a["t_s"] + b["t_s"]) / 2
    else:
        if len(intervals) != 1:
            raise EvaluationError("Requested midpoint must fall inside one observation gap")
        a, b = intervals[0]
        tm = at_time_s
    alpha = (tm - a["t_s"]) / (b["t_s"] - a["t_s"])
    xm = a["x"] + alpha * (b["x"] - a["x"])
    ym = a["y"] + alpha * (b["y"] - a["y"])
    anchor = [{"t_s": float(e["t_s"]), "x": float(e["x"]), "y": float(e["y"])} for e in good]
    def insert(point):
        knots = deepcopy(anchor)
        knots.append({"t_s": float(tm), "x": float(point[0]), "y": float(point[1])})
        return sorted(knots, key=lambda p: p["t_s"])
    candidate = {
        "schema": "veap.r1.possible-world-pair/1",
        "contract_sha256": canonical_hash(contract),
        "available_trace_sha256": canonical_hash(trace),
        "required_joint_decision": "INCONCLUSIVE",
        "purpose": "One shared observation record admits both compliant and violating continuous trajectories",
        "source_authenticity": "UNATTESTED",
        "assumptions": {
            "frame_id": contract["frame_id"],
            "max_speed_mps": contract["max_speed_mps"],
            "position_uncertainty_m": contract["position_uncertainty_m"],
        },
        "paths": {
            "candidate_compliant": insert((xm, ym)),
            "candidate_violating": insert((xc, yc)),
        },
        "missing_interval_s": [a["t_s"], b["t_s"]],
        "constructed_midpoint_s": tm,
        "limitations": "Author-constructed piecewise-linear paths; does not attest to physical execution or sensor authenticity",
    }
    candidate["pair_sha256"] = canonical_hash(candidate)
    return candidate
