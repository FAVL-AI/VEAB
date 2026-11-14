"""Prepare an illustrative blinded synthetic study; no physical ground truth."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json
import math
import hashlib

from veap_evidence.fixtures import cases,trace

ROOT=Path(__file__).resolve().parents[1]

PRIMARY=['compliant','observed_violation','missing_critical_interval','missing_irrelevant_camera',
         'violation_plus_missing','missing_safe_interval']


def make_reference(case_name):
    # Independent of evaluate(): full piecewise-linear trajectory used to
    # construct known toy-world truth, sampled at 0.01 seconds.
    original=trace()
    if case_name in ('observed_violation','missing_critical_interval','violation_plus_missing'):
        original['samples'][2]['y']=0.0
    if case_name=='missing_safe_interval':
        for sample in original['samples']:
            sample['y']=7.5
    points=original['samples']
    trajectory=[]
    for i in range(201):
        t=i/100
        idx=min(3,int(t*2))
        p0,p1=points[idx:idx+2]
        alpha=(t-p0['t_s'])/(p1['t_s']-p0['t_s'])
        trajectory.append({'t_s':t,'x':round(p0['x']+(p1['x']-p0['x'])*alpha,9),
                           'y':round(p0['y']+(p1['y']-p0['y'])*alpha,9)})
    return trajectory


def truth_status(c,reference):
    left,bottom,right,top=c['keepout'];r=c['robot_radius_m']
    bad=False
    for row in reference:
        dx=max(left-row['x'],0,row['x']-right)
        dy=max(bottom-row['y'],0,row['y']-top)
        if dx*dx+dy*dy<=r*r:
            bad=True
    terminal=reference[-1]
    goal=c['goal']
    goal_reached=math.hypot(terminal['x']-goal['x'],terminal['y']-goal['y'])<=goal['tolerance_m']
    return 'VIOLATING' if bad or not goal_reached else 'COMPLIANT'


def main():
    cases0=cases()
    root=ROOT/'artifacts'/'r1_blinded_synthetic'
    inputs=root/'evaluator_inputs';oracle=root/'reference_only'
    inputs.mkdir(parents=True,exist_ok=True);oracle.mkdir(parents=True,exist_ok=True)
    manifest={'schema':'veap.r1.synthetic-study/1','source':'SYNTHETIC_REFERENCE_ONLY',
              'not_a_human_or_hardware_ground_truth':True,'cases':[]}
    for name in PRIMARY:
        item=cases0[name]
        c,t=item['contract'],item['trace']
        dest=inputs/name;dest.mkdir(parents=True,exist_ok=True)
        (dest/'contract.json').write_text(json.dumps(c,indent=2,sort_keys=True)+'\n')
        (dest/'trace.json').write_text(json.dumps(t,indent=2,sort_keys=True)+'\n')
        ref=make_reference(name)
        truth={'case_id':name,'source':'AUTHOR_CONSTRUCTED_PIECEWISE_LINEAR_SYNTHETIC',
               'not_available_to_evaluator':True,'ground_truth_trajectory':ref,
               'synthetic_truth':truth_status(c,ref),
               'expected_epistemic_verdict':item['oracle']}
        (oracle/f'{name}.reference.json').write_text(json.dumps(truth,indent=2,sort_keys=True)+'\n')
        manifest['cases'].append({'case_id':name,'evaluator_directory':str(dest.relative_to(root)),
                    'reference_directory':'reference_only',
                    'expected_epistemic_verdict':item['oracle'],
                    'physical_trace_not_attested':True,
                    'trace_sha256':hashlib.sha256((dest/'trace.json').read_bytes()).hexdigest()})
    (root/'study_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'study':'VEAP_R1_SYNTHETIC_BLINDED_INPUTS','n':len(PRIMARY),
      'evaluator_inputs':str(inputs),'reference_truth_separate':str(oracle)},indent=2))

if __name__=='__main__':main()
