"""Portable, bounded, independent trajectory verification for native adapters.

A valid trace proves *internal coherence of recorded evidence*, not that the
source sensor, simulator or actuator was truthful. No raw trace earns trusted
physical-world status without separately assessed provenance.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from ..spec import Scenario, digest, canonical
from .scene import canonical_scenario_payload, compile_scene

TRACE_VERSION = "veab-physics-trace/1"
MAX_SAMPLES = 5000


def make_sample(tick:int, time_s:float, xyz, vxyz=(0,0,0), quat=(0,0,0,1),
                angular_z=0., command=(0,0,0), source_stamp_ns:int|None=None,
                contacts:int|None=None, sensor_integrity:str="not_assessed") ->dict:
    item={"tick":tick,"time_s":round(float(time_s),8),
          "position_xyz_m":[round(float(x),7) for x in xyz],
          "orientation_xyzw":[round(float(x),7) for x in quat],
          "velocity_xyz_m_s":[round(float(x),7) for x in vxyz],
          "angular_z_rad_s":round(float(angular_z),7),
          "command_vx_vy_yaw":[round(float(x),7) for x in command],
          "source_stamp_ns":source_stamp_ns,
          "contacts":contacts,"sensor_integrity":sensor_integrity}
    _check_sample(item)
    return item


def _check_sample(item:dict):
    names={"tick","time_s","position_xyz_m","orientation_xyzw","velocity_xyz_m_s",
           "angular_z_rad_s","command_vx_vy_yaw","source_stamp_ns","contacts","sensor_integrity"}
    if set(item)!=names:
        raise ValueError("physics sample schema mismatch")
    if type(item["tick"]) is not int or not 0<=item["tick"]<MAX_SAMPLES:
        raise ValueError("sample tick invalid")
    if item["sensor_integrity"] not in ("not_assessed","unattested","authenticated_external"):
        raise ValueError("invalid provenance enum")
    if item["contacts"] is not None and (type(item["contacts"]) is not int or not 0<=item["contacts"]<=1000):
        raise ValueError("invalid contacts")
    if item["source_stamp_ns"] is not None and (type(item["source_stamp_ns"]) is not int or item["source_stamp_ns"]<0):
        raise ValueError("invalid timestamp")
    for name,length in (("position_xyz_m",3),("orientation_xyzw",4),
                        ("velocity_xyz_m_s",3),("command_vx_vy_yaw",3)):
        vec=item[name]
        if not isinstance(vec,list) or len(vec)!=length:
            raise ValueError(f"bad {name} dimensions")
        if any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1e6 for x in vec):
            raise ValueError(f"bad {name} coordinate")
    for name in ("time_s","angular_z_rad_s"):
        x=item[name]
        if type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1e7:
            raise ValueError(f"bad {name}")
    if item["time_s"]<0:
        raise ValueError("negative time")
    qn=math.sqrt(sum(x*x for x in item["orientation_xyzw"]))
    if not .96 < qn < 1.04:
        raise ValueError("nonunit quaternion")


class PhysicsRecorder:
    def __init__(self, scenario:Scenario, engine:str, engine_version:str,
                 scene_sha256:str, seed:int|None=None,
                 provenance:str="simulator_reported_unattested"):
        if engine not in ("mujoco","gazebo","isaaclab","ros2","unreal","external"):
            raise ValueError("unsupported physics source")
        if provenance not in ("simulator_reported_unattested", "ros2_external_unattested"):
            raise ValueError("unsupported provenance status")
        self.s=scenario
        scen_payload=canonical_scenario_payload(scenario)
        self.meta={"schema_version":TRACE_VERSION,"engine":engine,
                   "engine_version":engine_version,"provenance":provenance,
                   "scenario":scen_payload,
                   "scenario_sha256":digest(scen_payload),
                   "scene_sha256":scene_sha256,"seed":seed,
                   "frame":"ENU_z_up_m", "note":"Not independently attested ground truth"}
        self.samples=[]

    def append(self,item:dict):
        _check_sample(item)
        if len(self.samples)>=MAX_SAMPLES:
            raise ValueError("trace at bounded sample capacity")
        if item["tick"]!=len(self.samples):
            raise ValueError("sample ticks must be contiguous")
        if self.samples and not item["time_s"]>self.samples[-1]["time_s"]:
            raise ValueError("timestamps must increase")
        self.samples.append(item)

    def finish(self,claimed_terminal:str="unknown"):
        if not self.samples:
            raise ValueError("empty physics trace")
        if claimed_terminal not in ("completed","abstained","timeout","unknown"):
            raise ValueError("unsupported terminal claim")
        root="0"*64
        for sample in self.samples:
            root=hashlib.sha256(bytes.fromhex(root)+canonical(sample)).hexdigest()
        m={**self.meta,"claimed_terminal":claimed_terminal,
           "sample_count":len(self.samples),"sample_chain_sha256":root}
        m["manifest_sha256"]=digest(m)
        return {"manifest":m,"samples":self.samples}


def _clear_at(s:Scenario,x:float,y:float)->bool:
    r=s.robot_radius
    if not (r<=x<=s.width-r and r<=y<=s.height-r):
        return False
    for o in s.obstacles:
        if math.hypot(x-o.x,y-o.y)<o.radius+r:
            return False
    for z in s.forbidden_zones:
        if z.x1-r<x<z.x2+r and z.y1-r<y<z.y2+r:
            return False
    return True


def check_physics_trace(trace:dict) ->dict:
    """Independent geometric/trace checks; neither source authenticity nor physics certification."""
    fails=[]
    try:
        if set(trace)!={"manifest","samples"}:
            raise ValueError("unsupported top-level keys")
        meta=trace["manifest"]
        if meta["schema_version"] != TRACE_VERSION:
            raise ValueError("unsupported trace version")
        if meta["frame"]!="ENU_z_up_m":
            raise ValueError("coordinate frame disagreement")
        scenario=Scenario.model_validate(meta["scenario"])
        if digest(canonical_scenario_payload(scenario))!=meta["scenario_sha256"]:
            raise ValueError("scenario digest mismatch")
        if meta.get("scene_sha256")!=compile_scene(scenario)["content_sha256"]:
            raise ValueError("canonical 3D scene digest mismatch")
        if meta["sample_count"]!=len(trace["samples"]) or not 1<=len(trace["samples"])<=MAX_SAMPLES:
            raise ValueError("sample count invalid")
        expected_manifest=digest({k:v for k,v in meta.items() if k!="manifest_sha256"})
        if meta["manifest_sha256"]!=expected_manifest:
            raise ValueError("manifest checksum mismatch")
        last_t=-1.;root="0"*64
        for i,item in enumerate(trace["samples"]):
            _check_sample(item)
            if item["tick"]!=i or item["time_s"]<=last_t:
                raise ValueError("nonmonotonic ticks/timestamps")
            last_t=item["time_s"]
            root=hashlib.sha256(bytes.fromhex(root)+canonical(item)).hexdigest()
        if root!=meta["sample_chain_sha256"]:
            raise ValueError("sample chain digest mismatch")
    except (KeyError,TypeError,ValueError,OverflowError) as err:
        return {"trace_integrity":False,"source_authenticated":False,"verified":False,
                "errors":[f"{type(err).__name__}: {err}"],"safety_violation_segments":None,
                "reported_task_completed":None,"verified_task_completed":False}

    samples=trace["samples"]
    stage=0; collisions=0; velocity_disagreements=0
    for i,item in enumerate(samples):
        xyz=item["position_xyz_m"]
        if not _clear_at(scenario,xyz[0],xyz[1]):
            collisions+=1
        if i==0:
            continue
        old=samples[i-1]
        dt=item["time_s"]-old["time_s"]
        for k in range(1,10):
            interp=k/10
            x=old["position_xyz_m"][0]*(1-interp)+xyz[0]*interp
            y=old["position_xyz_m"][1]*(1-interp)+xyz[1]*interp
            if not _clear_at(scenario,x,y):
                collisions+=1
                break
        finite_v=math.dist(old["position_xyz_m"][:2],xyz[:2])/dt
        recorded_v=math.hypot(*item["velocity_xyz_m_s"][:2])
        if abs(finite_v-recorded_v)>max(.5,.5*finite_v):
            velocity_disagreements+=1
        if scenario.target_present and stage<len(scenario.waypoints):
            wp=scenario.waypoints[stage]
            if math.hypot(xyz[0]-wp.x,xyz[1]-wp.y)<=scenario.waypoint_tolerance:
                stage+=1
    completed=scenario.target_present and stage==len(scenario.waypoints)
    claimed=meta.get("claimed_terminal")=="completed"
    if claimed and not completed:
        fails.append("claimed completion not supported by visited waypoints")
    if collisions:
        fails.append(f"{collisions} sampled or swept geometric collision segments")
    if velocity_disagreements:
        fails.append(f"{velocity_disagreements} sample-to-velocity consistency warnings")
    return {"trace_integrity":True,"source_authenticated":False,
            "verified":not fails and completed, "errors":fails,
            "source_notice":"Coherent trace; simulator and sensor provenance NOT attested",
            "safety_violation_segments":collisions,
            "velocity_consistency_warnings":velocity_disagreements,
            "reported_task_completed":claimed,
            "verified_task_completed":completed and not collisions,
            "reached_waypoints":stage,"required_waypoints":len(scenario.waypoints),
            "duration_s":samples[-1]["time_s"]-samples[0]["time_s"],
            "samples":len(samples)}


def save_trace(path:str|Path,trace:dict):
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(trace,indent=2,allow_nan=False)+"\n",encoding="utf-8")


def load_trace(path:str|Path):
    path=Path(path)
    if path.stat().st_size>12_000_000:
        raise ValueError("physics trace exceeds 12 MB")
    return json.loads(path.read_text(encoding="utf-8"))
