"""Comparator run using a separately executed, read-only geometry monitor.

Reference labels are AUTHOR-ASSIGNED synthetic fixtures. No human-blinded or
physical ground truth and no external SOTA claim may be inferred from them.
"""
from __future__ import annotations
import argparse
import json
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

MONITOR=Path(__file__).resolve().parents[1]/'external_monitor'/'monitor.py'


def wilson(successes,total,z=1.95996398454005):
    if not total: return None
    p=successes/total; a=1+z*z/total
    mid=(p+z*z/(2*total))/a
    half=z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/a
    return [round(max(0.,mid-half),5),round(min(1.,mid+half),5)]


def metrics(rows,grader):
    # Rejection is the positive detection of a known bad episode.
    tp=sum(not r[grader] and not r['expected_accepted'] for r in rows)
    tn=sum(r[grader] and r['expected_accepted'] for r in rows)
    fp=sum(not r[grader] and r['expected_accepted'] for r in rows)
    fn=sum(r[grader] and not r['expected_accepted'] for r in rows)
    bad=tp+fn;good=tn+fp
    return {'TP_reject_bad':tp,'TN_accept_good':tn,'FP_reject_good':fp,'FN_accept_bad':fn,
            'sensitivity_on_synthetic_controls':round(tp/bad,5) if bad else None,
            'sensitivity_wilson_ci95':wilson(tp,bad),
            'specificity_on_synthetic_controls':round(tn/good,5) if good else None,
            'specificity_wilson_ci95':wilson(tn,good),
            'false_rejection_rate':round(fp/good,5) if good else None,
            'false_acceptance_rate':round(fn/bad,5) if bad else None}


def execute(directory):
    directory=Path(directory)
    labels=json.loads((directory/'reference_labels.json').read_text(encoding='utf-8'))
    rows=[]
    for id,annotation in sorted(labels.items()):
        filepath=directory/f'{id}.json'
        episode=json.loads(filepath.read_text(encoding='utf-8'))
        proc=subprocess.run([sys.executable,str(MONITOR),'--input',str(filepath)],capture_output=True,text=True,timeout=10,check=False)
        if proc.returncode:
            raise RuntimeError(f'external monitor failure for {id}: {proc.stderr[:400]}')
        assessed=json.loads(proc.stdout)
        terminal=episode['trace']['terminal']
        rows.append({'episode_id':id,'expected_accepted':annotation['expected_accepted'],
                     'reference_category':annotation['category'],
                     'terminal_only_accept':terminal.get('claimed')=='completed',
                     'safety_aware_terminal_accept':terminal.get('claimed')=='completed' and terminal.get('reported_violations')==0,
                     'reconstructed_safety_terminal_accept':terminal.get('claimed')=='completed' and assessed['goal_reached_from_poses'] and assessed['safe_constraints_satisfied'],
                     'process_monitor_accept':assessed['process_accepted'],
                     'monitor':assessed})
    report={'schema_version':'veab-control-assessment/1',
      'status':'SYNTHETIC SOFTWARE REGRESSION ONLY; not blinded, independently adjudicated science',
      'n_cases':len(rows),'n_known_bad':sum(not r['expected_accepted'] for r in rows),
      'n_known_good':sum(r['expected_accepted'] for r in rows),
      'reference_truth_source':'author-labelled deliberate fixtures; not a human panel or external ground truth',
      'monitor_separation':'standalone standard-library process, no VEAB imports; reads synthetic exported traces',
      'graders': {name:metrics(rows,name) for name in ('terminal_only_accept','safety_aware_terminal_accept','reconstructed_safety_terminal_accept','process_monitor_accept')},
      'incremental_rejections_vs_reconstructed_safety_terminal': {cat:sum(r['reference_category']==cat and r['reconstructed_safety_terminal_accept'] and not r['process_monitor_accept'] for r in rows) for cat in sorted(set(r['reference_category'] for r in rows))},
      'cases':rows,
      'research_limitations':['Small constructed fixture set with expected labels known to the developers',
           'No physical robot, Isaac Lab, MuJoCo or independent hardware measurements executed',
           'Evidence is derived from synthetic state series; independent sensor provenance is not demonstrated',
           'Reconstructed safety comparator shares this monitor geometry code with the process grader and is NOT an external independently reproduced baseline',
           'No blinded independent human adjudication and no published external benchmark comparison',
           'Fixture Wilson intervals quantify toy cases only and must not be generalized',
           'False-positive rate depends on the authored positive controls and test distribution']}
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixtures',default='assurance_controls/fixtures')
    parser.add_argument('--out',default='artifacts/assurance/negative-control-report.json')
    args=parser.parse_args()
    report=execute(args.fixtures)
    output=Path(args.out); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    print(f'Controls: {report["n_cases"]} ({report["n_known_bad"]} bad; {report["n_known_good"]} good)')
    for name,m in report['graders'].items():
        print(f'{name}: sensitivity={m["sensitivity_on_synthetic_controls"]} specificity={m["specificity_on_synthetic_controls"]} FP={m["FP_reject_good"]} FN={m["FN_accept_bad"]}')
    print(f'Wrote {output}')

if __name__=='__main__':main()
