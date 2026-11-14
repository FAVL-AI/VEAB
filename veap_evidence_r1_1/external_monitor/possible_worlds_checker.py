"""Standard-library-only checker of a constructive counterexample pair.

DOES NOT IMPORT the VEAP evaluator, simulator, or possible-world generator.
Proof scope: piecewise-linear continuous trajectories under a stated 2D
Euclidean speed bound, circular footprint, rectangular closed keep-out zone.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

EPS = 1e-8


def hash_json(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def point_rect_distance(x, y, rect):
    return math.hypot(max(rect[0]-x, 0, x-rect[2]),
                      max(rect[1]-y, 0, y-rect[3]))


def point_segment_distance(p, u, v):
    dx, dy = v[0] - u[0], v[1] - u[1]
    den = dx*dx + dy*dy
    if den <= 0:
        return math.dist(p, u)
    alpha = max(0., min(1., ((p[0]-u[0])*dx + (p[1]-u[1])*dy)/den))
    return math.dist(p, (u[0]+alpha*dx,u[1]+alpha*dy))


def intersects_closed_rect(u, v, rect):
    # Liang–Barsky segment/axis-aligned rectangle intersection.
    dx, dy = v[0]-u[0], v[1]-u[1]
    lo, hi = 0., 1.
    for p,q in [(-dx,u[0]-rect[0]),(dx,rect[2]-u[0]),
                (-dy,u[1]-rect[1]),(dy,rect[3]-u[1])]:
        if abs(p)<1e-14:
            if q<0:return False
            continue
        t=q/p
        if p<0:lo=max(lo,t)
        else:hi=min(hi,t)
        if lo>hi:return False
    return True


def segment_rect_distance(u,v,rect):
    if intersects_closed_rect(u,v,rect):return 0.
    out=[point_rect_distance(*u,rect),point_rect_distance(*v,rect)]
    for p in [(rect[0],rect[1]),(rect[0],rect[3]),
              (rect[2],rect[1]),(rect[2],rect[3])]:
        out.append(point_segment_distance(p,u,v))
    return min(out)


def check_world(contract, trace, knots):
    reasons=[]
    if not isinstance(knots,list) or len(knots)<2:
        return {"valid":False,"errors":["insufficient knots"]}
    start,end=contract["mission_start_s"],contract["mission_end_s"]
    v=contract["max_speed_mps"]
    uncertainty=contract["position_uncertainty_m"]
    if abs(knots[0]["t_s"]-start)>EPS or abs(knots[-1]["t_s"]-end)>EPS:
        reasons.append("world does not cover mission window")
    for a,b in zip(knots,knots[1:]):
        dt=b["t_s"]-a["t_s"]
        if dt<=0:reasons.append("nonmonotonic world knots");continue
        if math.dist((a["x"],a["y"]),(b["x"],b["y"]))>v*dt+EPS:
            reasons.append("speed bound violated")
    for obs in trace.get("samples",[]):
        if not all(k in obs for k in ("t_s","x","y")):continue
        if obs.get("sensor_healthy") is not True or obs.get("frame_id")!=contract["frame_id"]:continue
        if not set(contract["required_topics"]).issubset(obs.get("topics", [])):continue
        # Piecewise linear interpolation ensures an exact comparison to every
        # *eligible* observed sample, not only the end points.
        times=[p["t_s"] for p in knots]
        if obs["t_s"]<times[0]-EPS or obs["t_s"]>times[-1]+EPS:
            reasons.append("observed time outside completion");continue
        actual=None
        for a,b in zip(knots,knots[1:]):
            if a["t_s"]-EPS<=obs["t_s"]<=b["t_s"]+EPS:
                frac=max(0.,min(1.,(obs["t_s"]-a["t_s"])/(b["t_s"]-a["t_s"])))
                actual=(a["x"]+frac*(b["x"]-a["x"]),a["y"]+frac*(b["y"]-a["y"]))
                break
        if actual is None or math.dist(actual,(obs["x"],obs["y"]))>uncertainty+EPS:
            reasons.append("completion contradicts recorded observation")
    radius=contract["robot_radius_m"]
    zone=contract["keepout"]
    minimum=min(segment_rect_distance((a["x"],a["y"]),(b["x"],b["y"]),zone)
                for a,b in zip(knots,knots[1:]))
    safe=minimum>radius+EPS
    last=knots[-1]
    goal=contract["goal"]
    reached=math.hypot(last["x"]-goal["x"],last["y"]-goal["y"])<=goal["tolerance_m"]+EPS
    return {"valid":not reasons,"errors":reasons,
            "minimum_path_clearance_m":minimum,
            "keepout_overlap":not safe,"goal_reached":reached,
            "world_verdict":"VIOLATING" if not safe or not reached else "COMPLIANT"}


def verify_pair(contract, trace, pair):
    failures=[]
    stored=dict(pair)
    checksum=stored.pop("pair_sha256",None)
    if hash_json(stored)!=checksum:failures.append("pair checksum mismatch")
    if hash_json(contract)!=pair.get("contract_sha256"):failures.append("contract digest mismatch")
    if hash_json(trace)!=pair.get("available_trace_sha256"):failures.append("trace digest mismatch")
    if pair.get("schema")!="veap.r1.possible-world-pair/1":failures.append("wrong schema")
    if pair.get("source_authenticity")!="UNATTESTED":failures.append("unearned provenance assertion")
    if pair.get("required_joint_decision")!="INCONCLUSIVE":
        failures.append("unsupported epistemic decision assertion")
    assumptions=pair.get("assumptions",{})
    if (assumptions.get("frame_id")!=contract.get("frame_id") or
        assumptions.get("max_speed_mps")!=contract.get("max_speed_mps") or
        assumptions.get("position_uncertainty_m")!=contract.get("position_uncertainty_m")):
        failures.append("counterfactual assumptions do not match the contract")
    # The nominated gap must be delimited by actual eligible observations.
    midpoint=pair.get("constructed_midpoint_s")
    gap=pair.get("missing_interval_s")
    eligible=sorted(x["t_s"] for x in trace.get("samples",[]) if
        all(k in x for k in ("t_s","x","y")) and
        x.get("sensor_healthy") is True and
        x.get("frame_id")==contract.get("frame_id") and
        set(contract.get("required_topics",[])).issubset(x.get("topics",[])))
    if (not isinstance(midpoint,(float,int)) or isinstance(midpoint,bool) or
        not math.isfinite(midpoint) or not isinstance(gap,list) or len(gap)!=2 or
        any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in gap) or
        not (gap[0]<midpoint<gap[1]) or
        (gap[0],gap[1]) not in list(zip(eligible,eligible[1:]))):
        failures.append("declared missing interval is not a real observation gap")
    paths=pair.get("paths",{})
    for name in ("candidate_compliant","candidate_violating"):
        knots=paths.get(name,[])
        if isinstance(knots,list) and isinstance(midpoint,(int,float)):
            if sum(abs(x.get("t_s",float('inf'))-midpoint)<EPS for x in knots if isinstance(x,dict))!=1:
                failures.append(f"{name}: claimed synthetic midpoint missing")
    results={}
    for name in ("candidate_compliant","candidate_violating"):
        try:results[name]=check_world(contract,trace,paths[name])
        except (KeyError,TypeError,ValueError) as exc:
            failures.append(f"{name}: {exc}")
    if len(results)==2:
        for name,result in results.items():
            if not result["valid"]:
                failures += [f"{name}: {x}" for x in result["errors"]]
        if results["candidate_compliant"]["world_verdict"]!="COMPLIANT":
            failures.append("alleged compliant completion is unsafe or misses goal")
        if results["candidate_violating"]["world_verdict"]!="VIOLATING":
            failures.append("alleged violating completion never violates")
    return {"status":"PASS" if not failures else "FAIL","failures":failures,
            "world_results":results,"implementation_independence":"stdlib_no_veap_imports",
            "ground_truth_independence":"NOT_ESTABLISHED", "source_authenticity":"UNATTESTED"}


def main():
    if len(sys.argv)!=4:
        print('usage: possible_worlds_checker.py contract.json trace.json pair.json',file=sys.stderr)
        return 2
    try:
        args=[json.loads(Path(path).read_text()) for path in sys.argv[1:]]
        result=verify_pair(*args)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0 if result['status']=='PASS' else 1
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'FAIL','error':str(exc)}))
        return 2


if __name__=='__main__':raise SystemExit(main())
