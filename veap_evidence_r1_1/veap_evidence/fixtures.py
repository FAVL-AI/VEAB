"""Deterministic mechanism controls; human-authored oracle labels, not real data."""
from copy import deepcopy


def contract():
    return {
        "schema":"veap.evidence.contract/1", "id":"nav-keepout-r1-v2",
        "mission_start_s":0.0,"mission_end_s":2.0,"max_gap_s":0.55,
        "max_speed_mps":4.0,"robot_radius_m":0.1,"position_uncertainty_m":0.02,
        "goal":{"x":2.0,"y":1.5,"tolerance_m":0.2},
        "keepout":[0.8,-0.2,1.2,0.2],"frame_id":"map",
        "required_topics":["/odom"]
    }


def trace():
    coords=[(0,1.5),(0.5,1.5),(1,1.5),(1.5,1.5),(2,1.5)]
    s=[{"event_id":f"pose-{i}","t_s":i*0.5,"x":float(x),"y":float(y),
        "frame_id":"map","sensor_healthy":True,"topics":["/odom","/cmd_vel","/camera"]}
       for i,(x,y) in enumerate(coords)]
    return {"schema":"veap.evidence.trace/1","source_kind":"synthetic",
            "agent_claimed_success":True,"samples":s}


def cases():
    examples={}
    def add(name,fn,oracle,why,c=None,truth=None):
        t=trace()
        fn(t)
        examples[name]={"trace":t,"contract":deepcopy(c or contract()),
                        "oracle":oracle,"description":why,
                        "ground_truth_class":truth or oracle}
    add("compliant",lambda t:None,"COMPLIANT","Dense, well-separated path with deadline pose")
    add("observed_violation",lambda t:t["samples"][2].update(y=0.0),"VIOLATING","Verified keepout overlap")
    add("violation_plus_missing",lambda t:(t["samples"][2].update(y=0.0),t["samples"].pop(1)),
        "VIOLATING","Observed violation cannot be erased by an unrelated gap")
    add("missing_critical_interval",lambda t:t["samples"].pop(2),"INCONCLUSIVE",
        "Missing central pose allows possible unseen zone entry",truth="VIOLATING")
    add("missing_irrelevant_camera",lambda t:t["samples"][2].update(topics=["/odom","/cmd_vel"]),
        "COMPLIANT","Camera not required by the evaluated pose contract")
    far_contract=contract();far_contract["goal"]["y"]=7.5
    def far_gap(t):
        for s in t["samples"]:s["y"]=7.5
        t["samples"].pop(2)
    add("missing_safe_interval",far_gap,"COMPLIANT",
        "Omitted interval remains provably clear under speed bound",c=far_contract)
    add("early_truncation",lambda t:t["samples"].pop(),"INCONCLUSIVE",
        "Mission deadline externally known, terminal state cannot be established")
    add("sensor_dropout",lambda t:t["samples"][2].update(sensor_healthy=False),"INCONCLUSIVE",
        "Pose evidence invalid at critical time")
    add("missing_required_odom",lambda t:t["samples"][2].update(topics=["/cmd_vel"]),"INCONCLUSIVE",
        "Required pose channel absent")
    add("frame_mismatch",lambda t:t["samples"][2].update(frame_id="odom"),"INCONCLUSIVE",
        "Frame transform not established")
    add("clock_reversal",lambda t:t["samples"][2].update(t_s=0.4),"INCONCLUSIVE",
        "Clock order inconsistent")
    add("goal_unreached",lambda t:t["samples"][-1].update(x=3.0),"VIOLATING","Terminal pose outside tolerance")
    add("uncertain_clearance",lambda t:t["samples"][2].update(y=0.75),"INCONCLUSIVE",
        "Speed envelope leaves possible keepout entry")
    add("false_agent_success_claim",lambda t:(t.update(agent_claimed_success=True),t["samples"][2].update(y=0.0)),
        "VIOLATING","Self-report is not used for grading")
    add("negative_agent_success_claim",lambda t:t.update(agent_claimed_success=False),
        "COMPLIANT","Self-report cannot invalidate verified trace")
    return examples
