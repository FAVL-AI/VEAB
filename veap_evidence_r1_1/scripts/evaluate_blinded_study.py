"""Evaluate only public synthetic trace and contract inputs, not reference_only."""
from pathlib import Path
import json
import subprocess
import sys
from veap_evidence.verdict import load_record,evaluate
from veap_evidence.baselines import grade

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts'/'r1_blinded_synthetic'

def main():
    rows=[]
    for p in sorted((BASE/'evaluator_inputs').glob('*/contract.json')):
        c,_=load_record(p); t,raw=load_record(p.parent/'trace.json')
        cert=evaluate(c,t,raw)
        out=p.parent/'certificate.json';out.write_text(json.dumps(cert,indent=2,sort_keys=True)+'\n')
        cmd=[sys.executable,str(ROOT/'external_monitor'/'monitor.py'),str(p),str(p.parent/'trace.json'),str(out)]
        check=subprocess.run(cmd,text=True,capture_output=True)
        if check.returncode !=0:
            raise RuntimeError(f'Independent checker rejected {p.parent.name}: {check.stdout}{check.stderr}')
        result=json.loads(check.stdout)
        rows.append({'case':p.parent.name,'veap':cert['verdict'],
                     'checker':result['certificate_check'],
                     'baselines':{m:grade(c,t,m) for m in ['goal_only','sampled_safety','gap_aware']},
                     'requirements':{k:v['verdict'] for k,v in cert['requirements'].items()},
                     'unresolved_intervals':cert['unresolved_coverage'],
                     'evidence_sha256':raw,'certificate_sha256':cert['certificate_sha256']})
    (BASE/'evaluator_results.json').write_text(json.dumps({'study':'SYNTHETIC_ONLY',
       'never_used_reference_truth_as_evaluator_input':True,'cases':rows},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'case_results':[{k:r[k] for k in ('case','veap','checker','baselines')} for r in rows]},indent=2))

if __name__=='__main__':main()
