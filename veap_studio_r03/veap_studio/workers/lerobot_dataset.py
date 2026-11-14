"""Local, read-only-input conversion from recorded state/action traces to LeRobotDataset.
Never invents action from odometry. No Hub uploads. Requires LeRobot installed.
"""
from __future__ import annotations
import argparse,hashlib,json,statistics
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--trace',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--meta',type=Path,required=True)
    p.add_argument('--robot',default='unknown_robot');args=p.parse_args()
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    rows=[json.loads(l) for l in args.trace.open(encoding='utf-8') if l.strip()]
    if not 3<=len(rows)<=100_000:raise ValueError('episode length must be 3..100000')
    if any(r.get('cmd_vel') is None for r in rows):
        raise ValueError('Recorded actions missing: refuse to derive action labels from odometry')
    times=[int(r['t_ns']) for r in rows]
    intervals=[b-a for a,b in zip(times,times[1:])]
    if min(intervals)<=0:raise ValueError('timestamps not strictly increasing')
    median=statistics.median(intervals)
    fps=round(1e9/median)
    if not 1<=fps<=100:raise ValueError('unsupported sample rate')
    if any(abs(dt-median)>max(2_000_000,.1*median) for dt in intervals):
        raise ValueError('irregular episode timing; explicit resampling required')
    if args.out.exists():raise FileExistsError('target dataset directory already exists')
    source_sha=hashlib.sha256(args.trace.read_bytes()).hexdigest()
    feat={
     'observation.state':{'dtype':'float32','shape':(3,),'names':['x_m','y_m','yaw_rad']},
     'action':{'dtype':'float32','shape':(3,),'names':['vx_m_s','vy_m_s','wz_rad_s']}}
    ds=LeRobotDataset.create(repo_id='veap/local_navigation',root=args.out,fps=fps,
                             features=feat,robot_type=args.robot,use_videos=False)
    for r in rows:
        if not isinstance(r['cmd_vel'],list) or len(r['cmd_vel'])!=3:raise ValueError('action must have three components')
        ds.add_frame({'observation.state':[float(r['x_m']),float(r['y_m']),float(r['yaw_rad'])],
                      'action':[float(v) for v in r['cmd_vel']], 'task':'Replay recorded navigation controls'})
    ds.save_episode();ds.finalize()
    meta={'status':'DERIVED_DATASET','source_sha256':source_sha,'frames':len(rows),'fps':fps,
          'robot':args.robot,'source':'RECORDED_ACTIONS_ONLY','source_authenticity':'UNATTESTED',
          'conversion_evidence':'LOCAL_DATASET_CREATED_NO_HUB_UPLOAD',
          'synchronization':'FIXED_RATE_WITHIN_TOLERANCE','calibration':'NOT_ESTABLISHED'}
    args.meta.write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta))
if __name__=='__main__':main()
