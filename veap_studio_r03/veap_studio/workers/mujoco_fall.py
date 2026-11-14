"""Native MuJoCo rigid-body fall-to-ground benchmark. No robot actuation.
Launched only after explicit local user action by VEAP's controlled job queue.
"""
from __future__ import annotations
import argparse, hashlib, json, math, time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--meta',type=Path,required=True)
    ap.add_argument('--steps',type=int,default=400)
    ap.add_argument('--dt',type=float,default=.005)
    args=ap.parse_args()
    if not (10<=args.steps<=3000 and .001<=args.dt<=.05):raise ValueError('bounded simulation parameters required')
    import mujoco
    xml=f'''<mujoco model="veap_falling_sphere"><option timestep="{args.dt}" gravity="0 0 -9.81"/>
      <worldbody><geom name="floor" type="plane" size="2 2 0.1"/>
      <body name="sphere" pos="0 0 1"><freejoint/><geom name="sphere_geom" type="sphere" size="0.1" mass="1"/></body></worldbody></mujoco>'''
    model=mujoco.MjModel.from_xml_string(xml)
    data=mujoco.MjData(model)
    contact_steps=[];positions=[];previous=None;start=time.monotonic()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('w',encoding='utf-8') as f:
        for step in range(args.steps):
            mujoco.mj_step(model,data)
            p=[float(v) for v in data.qpos[:3]]
            vel=[float(v) for v in data.qvel[:3]]
            if data.ncon:contact_steps.append(step)
            row={'t_ns':int(round(float(data.time)*1e9)), 'x_m':p[0], 'y_m':p[1], 'z_m':p[2],
                 'yaw_rad':0., 'speed_m_s':math.hypot(vel[0],vel[1]), 'sensor_ok':True,
                 'event':'GROUND CONTACT' if data.ncon and previous is False else '',
                 'contact_count':int(data.ncon),'velocity_z_m_s':vel[2],
                 'engine':'mujoco','source_type':'NATIVE_SIMULATOR_STATE','calibration':'NOT_CALIBRATED'}
            f.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n')
            previous=bool(data.ncon);positions.append(p)
    digest=hashlib.sha256(args.out.read_bytes()).hexdigest()
    meta={'engine':'mujoco','engine_version':getattr(mujoco,'__version__','unknown'),
        'experiment':'falling_sphere_v1','steps':args.steps,'dt_s':args.dt,'duration_s':float(data.time),
        'first_contact_step':contact_steps[0] if contact_steps else None,'final_z_m':positions[-1][2],
        'wall_time_s':round(time.monotonic()-start,5),'trajectory_sha256':digest,
        'ground_truth_status':'SIMULATOR_INTERNAL_ONLY','robot_dynamics_calibrated':False,
        'physics_equivalence':'NOT_ESTABLISHED'}
    args.meta.write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta))
if __name__=='__main__':main()
