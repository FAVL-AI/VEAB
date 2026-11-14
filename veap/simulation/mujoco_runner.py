"""OPTIONAL real MuJoCo physics execution (requires `pip install mujoco`).

This drives a *planar-jointed research surrogate* with force-limited velocity
tracking. It does not claim differential drive, mecanum dynamics or rigid-body
contact equivalence with Gazebo/Isaac. No hardware commands are emitted.
"""
from __future__ import annotations
import math
import random
from pathlib import Path
from ..agents import BaselineAgent
from ..sim import shield_velocity
from ..spec import Scenario
from .scene import compile_scene
from .export import export_scene
from .telemetry import PhysicsRecorder, make_sample, check_physics_trace


def simulate_mujoco(s:Scenario,output_dir:str|Path,policy:str="route",seed:int=17,
                    shield:bool=True, max_steps:int|None=None)->dict:
    try:
        import mujoco
    except ImportError as e:
        raise RuntimeError("MuJoCo Python binding is not installed. Install 'mujoco' in a separate physics environment.") from e
    if policy not in {"route","greedy"}:
        raise ValueError("unsupported policy")
    if seed<0 or seed>2**32-1:
        raise ValueError("seed out of range")
    scene=compile_scene(s)
    target=Path(output_dir)
    assets=export_scene(scene,target)
    model=mujoco.MjModel.from_xml_path(str(target/assets["files"]["mjcf"]["name"]))
    data=mujoco.MjData(model)
    mujoco.mj_forward(model,data)
    body_id=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,"veab_scout")
    addr=[model.jnt_dofadr[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,"planar_"+axis)]
          for axis in ("x","y","yaw")]
    qpos_yaw=model.jnt_qposadr[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,"planar_yaw")]
    agent=BaselineAgent(policy,s)
    rng=random.Random(seed)
    r=PhysicsRecorder(s,"mujoco",getattr(mujoco,"__version__","unknown"),scene["content_sha256"],seed)
    stage=0; terminal="timeout"; prior_valid=0

    def state(tick,cmd):
        pos=data.xpos[body_id]
        yaw=data.qpos[qpos_yaw]
        v=[float(data.qvel[addr[0]]),float(data.qvel[addr[1]]),0.]
        q=[0.,0.,math.sin(yaw/2),math.cos(yaw/2)]
        return make_sample(tick, float(data.time), [float(pos[0]),float(pos[1]),float(pos[2])],
                           v,q,float(data.qvel[addr[2]]),cmd,contacts=int(data.ncon))

    r.append(state(0,(0.,0.,0.)))
    limit=min(max_steps if max_steps is not None else s.max_steps,s.max_steps)
    for tick in range(1,limit+1):
        x=float(data.xpos[body_id][0]); y=float(data.xpos[body_id][1])
        active=[f for f in s.faults if f.start_step<=tick<f.start_step+f.duration_steps]
        dropout=any(f.kind=="sensor_dropout" for f in active)
        stall=any(f.kind=="actuator_stall" for f in active)
        noise=any(f.kind=="perception_noise" for f in active)
        obs=(x,y)
        if noise: obs=(x+rng.uniform(-.24,.24),y+rng.uniform(-.24,.24))
        if not dropout: prior_valid+=1
        desired,_=agent.act(obs,stage,None if dropout else s.target_present)
        if not s.target_present and prior_valid>=3:
            terminal="abstained"
            break
        applied,_=shield_velocity(s,(x,y),desired,not dropout) if shield else (desired,None)
        if stall: applied=(0.,0.)
        desired_yaw=math.atan2(applied[1],applied[0]) if math.hypot(*applied)>.05 else float(data.qpos[qpos_yaw])
        def wrap(angle):return math.atan2(math.sin(angle),math.cos(angle))
        # Substep at the native MuJoCo dt; actuator controls are *forces*, not
        # kinematic teleportation. Safety gate is a desired-velocity filter.
        substeps=max(1,int(round(s.dt/model.opt.timestep)))
        for _ in range(substeps):
            dtheta=wrap(desired_yaw-float(data.qpos[qpos_yaw]))
            desired_w=max(-2.,min(2.,5*dtheta))
            target_velocity=[applied[0],applied[1],desired_w]
            gains=[22.,22.,4.]
            maxforces=[50.,50.,8.]
            for axis in range(3):
                error=target_velocity[axis]-float(data.qvel[addr[axis]])
                data.ctrl[axis]=max(-maxforces[axis],min(maxforces[axis],gains[axis]*error))
            mujoco.mj_step(model,data)
        r.append(state(tick,(applied[0],applied[1],desired_w)))
        if s.target_present and stage<len(s.waypoints):
            wp=s.waypoints[stage]
            if math.hypot(float(data.xpos[body_id][0])-wp.x,float(data.xpos[body_id][1])-wp.y)<=s.waypoint_tolerance:
                stage+=1
                if stage==len(s.waypoints):
                    terminal="completed"
                    break
    trace=r.finish(terminal)
    return {"trace":trace,"validation":check_physics_trace(trace),
            "assets":assets,"physical_model":"planar-constrained force-controlled surrogate, NOT vendor-calibrated"}
