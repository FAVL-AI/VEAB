"""Isaac Lab 2.3.x headless falling sphere -- native PhysX telemetry adapter.
Requires the pinned Isaac runtime; cannot run in a normal Python interpreter.
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
    # Isaac Sim must be launched before importing physics-dependent packages.
    from isaaclab.app import AppLauncher
    launcher=AppLauncher(headless=True)
    app=launcher.app
    started=time.monotonic()
    try:
        import isaaclab.sim as sim_utils
        from isaaclab.assets import RigidObject, RigidObjectCfg
        from isaaclab.sim import SimulationContext
        from importlib.metadata import version
        sim=SimulationContext(sim_utils.SimulationCfg(dt=args.dt,device='cuda:0'))
        ground_cfg=sim_utils.GroundPlaneCfg()
        ground_cfg.func('/World/ground',ground_cfg)
        cfg=RigidObjectCfg(
            prim_path='/World/VEAPSphere',
            spawn=sim_utils.SphereCfg(radius=.1,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(),
                mass_props=sim_utils.MassPropertiesCfg(mass=1.0),
                collision_props=sim_utils.CollisionPropertiesCfg()),
            init_state=RigidObjectCfg.InitialStateCfg(pos=(0.,0.,1.)))
        body=RigidObject(cfg=cfg)
        sim.reset()
        body.reset()
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open('w',encoding='utf-8') as f:
            for i in range(args.steps):
                body.write_data_to_sim()
                sim.step()
                body.update(args.dt)
                p=[float(x) for x in body.data.root_pos_w[0].cpu().tolist()]
                v=[float(x) for x in body.data.root_lin_vel_w[0].cpu().tolist()]
                row={'t_ns':int(round((i+1)*args.dt*1e9)), 'x_m':p[0],'y_m':p[1],'z_m':p[2],
                     'yaw_rad':0.,'speed_m_s':math.hypot(v[0],v[1]),'velocity_z_m_s':v[2],
                     'sensor_ok':True,'event':'','engine':'isaaclab_physx',
                     'source_type':'NATIVE_SIMULATOR_STATE','contact_count':None,
                     'calibration':'NOT_CALIBRATED'}
                f.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n')
        meta={'engine':'isaaclab_physx','engine_version':version('isaacsim'),
              'isaaclab_version':version('isaaclab'),'experiment':'falling_sphere_v1',
              'steps':args.steps,'dt_s':args.dt,'trajectory_sha256':hashlib.sha256(args.out.read_bytes()).hexdigest(),
              'ground_truth_status':'SIMULATOR_INTERNAL_ONLY',
              'contact_instrumentation':'NOT_IMPLEMENTED',
              'physics_equivalence':'NOT_ESTABLISHED',
              'wall_time_s':round(time.monotonic()-started,4)}
        args.meta.write_text(json.dumps(meta,indent=2),encoding='utf-8')
        print(json.dumps(meta),flush=True)
    finally:
        app.close()
if __name__=='__main__':main()
