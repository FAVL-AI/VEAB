"""Cross-engine regression compares matched time and scene conditions.

Disagreement measures are observations, not proof of either simulator's truth.
"""
from __future__ import annotations
import math
from .telemetry import check_physics_trace


def compare_traces(left:dict,right:dict,position_tolerance_m:float=.10) ->dict:
    a,b=left["manifest"],right["manifest"]
    if a["scenario_sha256"]!=b["scenario_sha256"] or a["scene_sha256"]!=b["scene_sha256"]:
        raise ValueError("different scenario or asset scene digests cannot be compared")
    la=check_physics_trace(left); lb=check_physics_trace(right)
    if not la["trace_integrity"] or not lb["trace_integrity"]:
        raise ValueError("invalid trace integrity")
    # This is tick-aligned; it explicitly cannot align dissimilar sample rates.
    if len(left["samples"])!=len(right["samples"]):
        raise ValueError("traces must contain same number of samples; resampling must be preregistered")
    accum=0.;maxerr=0.;disagreements=0
    for pa,pb in zip(left["samples"],right["samples"]):
        if abs(pa["time_s"]-pb["time_s"])>1e-5:
            raise ValueError("timestamps do not align; no implicit interpolation")
        delta=math.dist(pa["position_xyz_m"],pb["position_xyz_m"])
        accum+=delta*delta
        maxerr=max(maxerr,delta)
        disagreements+=delta>position_tolerance_m
    return {"schema_version":"veab-differential/1",
            "scenario_sha256":a["scenario_sha256"],
            "scene_sha256":a["scene_sha256"],
            "engine_a":a["engine"],"engine_b":b["engine"],
            "sample_count":len(left["samples"]),
            "position_rmse_m":round(math.sqrt(accum/len(left["samples"])),8),
            "maximum_position_difference_m":round(maxerr,8),
            "disagreement_count_above_tolerance":disagreements,
            "position_tolerance_m":position_tolerance_m,
            "geometric_violation_segments_a":la["safety_violation_segments"],
            "geometric_violation_segments_b":lb["safety_violation_segments"],
            "external_ground_truth":False,
            "interpretation":"Cross-engine divergence only; not a simulator accuracy certification"}
