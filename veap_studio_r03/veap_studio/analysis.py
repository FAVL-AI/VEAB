"""Model-agnostic 2D trace analysis for local, untrusted evidence.

This does not validate robot physics or sensor authenticity. Uploaded traces and
synthetic runs are both UNATTESTED without an external capture root of trust.
"""
from __future__ import annotations
import csv
import io
import json
import math
from pathlib import Path

SAMPLE_LIMIT = 300_000
MAX_LINE = 120_000
ZONE = {'x1': 3.75, 'x2': 5.65, 'y1': 2.3, 'y2': 4.55}
GOAL = (10.5, 7.2)


def finite(v):
    x = float(v)
    if not math.isfinite(x):
        raise ValueError('nonfinite coordinate or timestamp')
    return x


def normalize(row):
    if not isinstance(row, dict):
        raise ValueError('each trace record must be an object')
    def coalesce(*names):
        for name in names:
            if name in row and row[name] not in (None, ''):
                return row[name]
        return None
    t = coalesce('t_ns', 'timestamp_ns', 'time_ns', 'timestamp')
    if t is None:
        t_s = coalesce('time', 't', 'time_s', 'timestamp_s')
        if t_s is None:
            raise ValueError('missing timestamp')
        t = round(finite(t_s)*1e9)
    x = coalesce('x_m', 'x', 'pos_x', 'position_x')
    y = coalesce('y_m', 'y', 'pos_y', 'position_y')
    if x is None or y is None:
        raise ValueError('missing x/y position')
    speed_value=coalesce('speed_m_s', 'speed', 'velocity')
    clear_value=coalesce('clearance_m', 'clearance')
    latency_value=coalesce('latency_ms', 'latency')
    item = {
        't_ns':int(finite(t)), 'x_m':finite(x), 'y_m':finite(y),
        'yaw_rad':finite(coalesce('yaw_rad', 'yaw', 'heading') or 0),
        'speed_m_s':finite(speed_value) if speed_value is not None else None,
        'clearance_m':finite(clear_value) if clear_value is not None else None,
        'latency_ms':finite(latency_value) if latency_value is not None else None,
        'sensor_ok':str(coalesce('sensor_ok') if coalesce('sensor_ok') is not None else 'true').lower() not in ('false','0','no'),
        'event':str(coalesce('event') or ''),
    }
    if row.get('cmd_vel') is not None:
        cmd=row['cmd_vel']
        if not isinstance(cmd,list) or len(cmd)!=3:raise ValueError('recorded action must contain 3 components')
        item['cmd_vel']=[finite(x) for x in cmd]
    if item['t_ns'] < 0: raise ValueError('negative timestamp')
    return item


def load_trace(path: Path) -> list[dict]:
    path=Path(path)
    if path.suffix.lower() not in ('.jsonl','.csv','.json'):
        raise ValueError('trace extraction requires JSONL, JSON array or CSV')
    rows=[]
    with path.open('r',encoding='utf-8-sig',newline='') as stream:
        if path.suffix.lower()=='.csv':
            reader=csv.DictReader(stream)
        elif path.suffix.lower()=='.json':
            raw=json.load(stream)
            if not isinstance(raw,list): raise ValueError('expected JSON array')
            reader=raw
        else:
            def gen():
                for line in stream:
                    if len(line)>MAX_LINE: raise ValueError('line exceeds limit')
                    if line.strip(): yield json.loads(line)
            reader=gen()
        for row in reader:
            if len(rows)>=SAMPLE_LIMIT: raise ValueError('too many records')
            rows.append(normalize(row))
    if not rows: raise ValueError('empty trace')
    for i in range(1,len(rows)):
        if rows[i]['t_ns']<=rows[i-1]['t_ns']:
            raise ValueError(f'non-monotonic timestamp at sample {i}')
    return rows


def orient(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def intersects(a,b,c,d):
    eps=1e-10
    o1,o2,o3,o4=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
    if ((o1>eps and o2 < -eps) or (o1 < -eps and o2>eps)) and ((o3>eps and o4 < -eps) or (o3 < -eps and o4>eps)):return True
    def on(p,q,r):return min(p[0],r[0])-eps<=q[0]<=max(p[0],r[0])+eps and min(p[1],r[1])-eps<=q[1]<=max(p[1],r[1])+eps
    return ((abs(o1)<=eps and on(a,c,b)) or (abs(o2)<=eps and on(a,d,b)) or (abs(o3)<=eps and on(c,a,d)) or (abs(o4)<=eps and on(c,b,d)))


def crosses_rect(a,b,z):
    x1,y1,x2,y2=z['x1'],z['y1'],z['x2'],z['y2']
    if any(x1<=q[0]<=x2 and y1<=q[1]<=y2 for q in (a,b)):return True
    corners=[(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
    return any(intersects(a,b,corners[i],corners[(i+1)%4]) for i in range(4))


def inspect_trace(rows, zone=ZONE, goal=GOAL, max_speed=1.2, max_gap_s=.4):
    issues=[];events=[];dist=0.;gaps=0; crossings=0;overspeed=0;dropouts=0;kinematic_mismatch=0
    for i,r in enumerate(rows):
        if not r['sensor_ok']:
            dropouts+=1;events.append({'index':i,'kind':'SENSOR DROPOUT','severity':'warn','t_ns':r['t_ns']})
        if r.get('event'):
            events.append({'index':i,'kind':r['event'],'severity':'info','t_ns':r['t_ns']})
        measured_speed=r['speed_m_s']
        if i:
            prev=rows[i-1];dt=(r['t_ns']-prev['t_ns'])/1e9
            derived_speed=math.dist((r['x_m'],r['y_m']),(prev['x_m'],prev['y_m']))/dt
            if measured_speed is not None and abs(derived_speed-measured_speed)>max(.5,.35*max(derived_speed,measured_speed)):
                kinematic_mismatch+=1
            speed=max(derived_speed,measured_speed or 0)
        else:speed=measured_speed or 0
        if speed>max_speed:
            overspeed+=1;events.append({'index':i,'kind':'OVERSPEED','severity':'critical','t_ns':r['t_ns']})
        if i:
            p=rows[i-1]
            if r['t_ns']-p['t_ns']>max_gap_s*1e9:
                gaps+=1;events.append({'index':i,'kind':'TIMESTAMP GAP','severity':'warn','t_ns':r['t_ns']})
            a,b=(p['x_m'],p['y_m']),(r['x_m'],r['y_m'])
            dist+=math.dist(a,b)
            if crosses_rect(a,b,zone):
                crossings+=1;events.append({'index':i,'kind':'KEEP-OUT INTERSECTION','severity':'critical','t_ns':r['t_ns']})
    reached=math.dist((rows[-1]['x_m'],rows[-1]['y_m']),goal)<=.45
    if crossings:issues.append('Recorded path intersects modeled restricted region')
    if overspeed:issues.append('Recorded speed exceeds chosen analysis threshold')
    if gaps:issues.append('Evidence contains timestamp gaps')
    if kinematic_mismatch:issues.append('Reported velocity inconsistent with finite-difference displacement')
    if dropouts:issues.append('Evidence contains flagged sensor dropouts')
    if not reached:issues.append('Terminal target not reached under selected contract')
    accepted=not issues
    duration=(rows[-1]['t_ns']-rows[0]['t_ns'])/1e9
    latencies=[r['latency_ms'] for r in rows if r['latency_ms'] is not None]
    return {'task_complete':reached,'process_accepted':accepted,'violations':crossings,'kinematic_mismatch_count':kinematic_mismatch,'overspeed_count':overspeed,'dropouts':dropouts,'gaps':gaps,'path_m':round(dist,3),'duration_s':round(duration,3),'samples':len(rows),'events':events,'issues':issues,'max_latency_ms':round(max(latencies),2) if latencies else None,'analysis_scope':'RECORDED_2D_TRACE_ONLY','source_authenticity':'NOT_ESTABLISHED','independent_ground_truth':False,'verdict':('CONTRACT CHECK PASS' if accepted else 'REVIEW REQUIRED')}


def interpolate(rows,t):
    if t<=rows[0]['t_ns']:return rows[0]['x_m'],rows[0]['y_m']
    if t>=rows[-1]['t_ns']:return rows[-1]['x_m'],rows[-1]['y_m']
    lo,hi=0,len(rows)-1
    while hi-lo>1:
        mid=(lo+hi)//2
        if rows[mid]['t_ns']<t:lo=mid
        else:hi=mid
    a,b=rows[lo],rows[hi]
    u=(t-a['t_ns'])/(b['t_ns']-a['t_ns'])
    return (a['x_m']+u*(b['x_m']-a['x_m']), a['y_m']+u*(b['y_m']-a['y_m']))


def compare_traces(reference, candidate):
    # Elapsed-time alignment for demonstration. Not hardware clock synchronization.
    left0,right0=reference[0]['t_ns'],candidate[0]['t_ns']
    limit=min(reference[-1]['t_ns']-left0,candidate[-1]['t_ns']-right0)
    errors=[]; maxn=min(5000,len(reference))
    for r in reference[:maxn]:
        elapsed=r['t_ns']-left0
        if elapsed>limit:break
        x,y=interpolate(candidate,right0+elapsed)
        errors.append(math.hypot(r['x_m']-x,r['y_m']-y))
    if not errors:raise ValueError('recordings do not overlap')
    return {'rmse_m':round(math.sqrt(sum(e*e for e in errors)/len(errors)),4),'max_error_m':round(max(errors),4),'p90_error_m':round(sorted(errors)[int((len(errors)-1)*.9)],4),'aligned_samples':len(errors),'reference_duration_s':round((reference[-1]['t_ns']-left0)/1e9,2),'candidate_duration_s':round((candidate[-1]['t_ns']-right0)/1e9,2),'alignment':'ELAPSED_TIME_ONLY','physics_equivalence':'NOT_ESTABLISHED','reference_ground_truth':'NOT_ESTABLISHED','conclusion':'DISCREPANCY MEASURED; DIGITAL TWIN NOT VALIDATED'}


def inject_fault(rows, kind, severity, seed=13):
    import random
    rng=random.Random(seed)
    out=[dict(r) for r in rows]
    n=len(out); a=max(2,n//3);b=min(n-1,a+max(2,n//5))
    for i in range(a,b):
        if kind=='sensor_dropout':out[i]['sensor_ok']=False;out[i]['event']='INJECTED SENSOR DROPOUT'
        elif kind=='odometry_drift':out[i]['x_m']+=severity*(i-a+1)/max(1,b-a);out[i]['event']='INJECTED ODOMETRY DRIFT'
        elif kind=='actuator_stall':out[i]['x_m']=out[a-1]['x_m'];out[i]['y_m']=out[a-1]['y_m'];out[i]['speed_m_s']=0;out[i]['event']='INJECTED ACTUATOR STALL'
        elif kind=='command_delay':out[i]['latency_ms']=(out[i]['latency_ms'] or 0)+severity*100;out[i]['event']='INJECTED COMMAND DELAY'
        elif kind=='perception_noise':out[i]['x_m']+=rng.gauss(0,severity*.35);out[i]['y_m']+=rng.gauss(0,severity*.35);out[i]['event']='INJECTED PERCEPTION NOISE'
        else:raise ValueError('unknown fault type')
    return out
