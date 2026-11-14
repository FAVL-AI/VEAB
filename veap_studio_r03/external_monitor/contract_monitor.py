#!/usr/bin/env python3
"""Independent-implementation, standard-library-only recorded 2D constraint monitor.

No VEAP imports. No ROS publishing. A correct trace is not proof of physical truth.
"""
from __future__ import annotations
import argparse,hashlib,json,math,sys
from pathlib import Path

def side(a,b,p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])

def intersection(a,b,c,d):
    def between(p,q,r):return min(p,r)-1e-10<=q<=max(p,r)+1e-10
    da,db=side(a,b,c),side(a,b,d)
    dc,dd=side(c,d,a),side(c,d,b)
    if (da*db<0 and dc*dd<0):return True
    return any(abs(s)<=1e-10 and between(x,u,y) and between(z,v,w) for s,x,u,y,z,v,w in
      [(da,a[0],c[0],b[0],a[1],c[1],b[1]),(db,a[0],d[0],b[0],a[1],d[1],b[1]),
       (dc,c[0],a[0],d[0],c[1],a[1],d[1]),(dd,c[0],b[0],d[0],c[1],b[1],d[1])])

def crosses_rect(a,b,z):
    x1,y1,x2,y2=(float(z[t]) for t in ('x1','y1','x2','y2'))
    if any(x1<=p[0]<=x2 and y1<=p[1]<=y2 for p in (a,b)):return True
    corners=[(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
    return any(intersection(a,b,corners[i],corners[(i+1)%4]) for i in range(4))

def evaluate(contract,rows):
    if not rows:raise ValueError('empty recorded trace')
    issues=[];events=[];violations=0;overspeed=0;gaps=0;missing_action=0;missing_sensor=0
    last=None
    for i,r in enumerate(rows):
        t=int(r['t_ns']);p=(float(r['x_m']),float(r['y_m']))
        if not all(map(math.isfinite,p)) or t<0:raise ValueError('invalid time/pose')
        if contract.get('require_actions') and r.get('cmd_vel') is None:
            missing_action+=1;events.append({'index':i,'code':'ACTION_EVIDENCE_MISSING'})
        if not r.get('sensor_ok',True):
            missing_sensor+=1;events.append({'index':i,'code':'SENSOR_FAULT_FLAGGED'})
        if last:
            old_t,old_p=last;dt=(t-old_t)/1e9
            if dt<=0:raise ValueError('non-monotonic time')
            if dt>contract['max_gap_s']:
                gaps+=1;events.append({'index':i,'code':'MISSING_WINDOW'})
            derived=math.dist(old_p,p)/dt
            if derived>contract['max_speed_m_s']+1e-9:
                overspeed+=1;events.append({'index':i,'code':'OVERSPEED'})
            for z in contract['forbidden_zones']:
                if crosses_rect(old_p,p,z):
                    violations+=1;events.append({'index':i,'code':'KEEP_OUT_CROSSING','region':z['label']})
        last=t,p
    g=contract['goal'];reached=math.dist((float(rows[-1]['x_m']),float(rows[-1]['y_m'])),(g['x'],g['y']))<=contract['goal_tolerance_m']
    if not reached:issues.append('GOAL_NOT_REACHED')
    if violations:issues.append('KEEP_OUT_CROSSING')
    if overspeed:issues.append('OVERSPEED')
    if gaps:issues.append('EVIDENCE_GAP')
    if missing_action:issues.append('RECORDED_ACTION_MISSING')
    if missing_sensor:issues.append('SENSOR_FAULT_FLAGGED')
    return {'schema':'veap.monitor.verdict/1','task_complete_within_record':reached,
            'recorded_contract_pass':not issues,'violations':violations,'overspeed_segments':overspeed,
            'missing_time_windows':gaps,'missing_actions':missing_action,
            'flagged_sensor_faults':missing_sensor,'issues':issues,'events':events[:1000],
            'source_authenticity':'NOT_ESTABLISHED','physical_safety':'NOT_ESTABLISHED',
            'reference_truth':'RECORDED_SOURCE_ONLY','monitor_independence':'CODE_SEPARATE_NOT_ORGANISATIONALLY_INDEPENDENT'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--contract',type=Path,required=True)
    ap.add_argument('--trace',type=Path,required=True);args=ap.parse_args()
    contract=json.loads(args.contract.read_text())
    rows=[]
    for line in args.trace.read_text(encoding='utf-8').splitlines():
        if line.strip():rows.append(json.loads(line))
        if len(rows)>300_000:raise ValueError('too many samples')
    print(json.dumps(evaluate(contract,rows)))
if __name__=='__main__':main()
