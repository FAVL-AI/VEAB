"""Strict experimental comparison of native 3D state traces.
Not a calibrated sim-to-real or physics-equivalence certification.
"""
from __future__ import annotations
import json,math,statistics
from pathlib import Path

def read_xyz(path):
    rows=[]
    with Path(path).open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():continue
            o=json.loads(line)
            t=int(o['t_ns']);p=[float(o[k]) for k in ('x_m','y_m','z_m')]
            if t<0 or not all(math.isfinite(v) for v in p):raise ValueError('invalid 3D state')
            if rows and t<=rows[-1][0]:raise ValueError('non-monotonic 3D states')
            rows.append((t,p,o.get('contact_count')))
            if len(rows)>50000:raise ValueError('excessive trajectory size')
    if len(rows)<2:raise ValueError('not enough 3D states')
    return rows

def compare_physics(ref_path,candidate_path,ref_meta=None,candidate_meta=None):
    ref=read_xyz(ref_path);other=read_xyz(candidate_path)
    if len(ref)!=len(other):raise ValueError('different sample counts; aligned resampling required')
    max_dt=max(abs(a[0]-b[0]) for a,b in zip(ref,other))
    if max_dt>1_000_000:raise ValueError('timestamps differ by more than 1 ms; not comparable')
    delta=[];zerr=[];xerr=[]
    for a,b in zip(ref,other):
        e=[aa-bb for aa,bb in zip(a[1],b[1])]
        delta.append(math.sqrt(sum(v*v for v in e)));zerr.append(abs(e[2]));xerr.append(abs(e[0]))
    has_ref=all(r[2] is not None for r in ref)
    has_other=all(r[2] is not None for r in other)
    contact_disagreements=sum(bool(a[2])!=bool(b[2]) for a,b in zip(ref,other)) if has_ref and has_other else None
    return {'scope':'NATIVE_3D_SIM_TO_SIM_TRACE_COMPARISON','samples':len(ref),
      'rmse_xyz_m':round(math.sqrt(sum(x*x for x in delta)/len(delta)),6),
      'rmse_z_m':round(math.sqrt(sum(x*x for x in zerr)/len(zerr)),6),
      'p90_xyz_m':round(sorted(delta)[int(.9*(len(delta)-1))],6),
      'max_xyz_m':round(max(delta),6),'max_time_difference_ns':max_dt,
      'contact_disagreements':contact_disagreements,
      'contact_comparable':has_ref and has_other,
      'ground_truth_independence':'NO_BOTH_SIMULATORS',
      'physics_equivalence':'NOT_ESTABLISHED',
      'calibration':'REQUIRES_MASS_GEOMETRY_SOLVER_FRICTION_AND_EXTERNAL_REFERENCES',
      'reference_metadata':ref_meta or {},'candidate_metadata':candidate_meta or {}}
