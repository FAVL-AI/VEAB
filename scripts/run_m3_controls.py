#!/usr/bin/env python3
"""Labelled synthetic controls, not preregistered empirical performance."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from veab.m3_replay.core import load_contract, audit_records, iter_jsonl

SPECPATH=ROOT/'external_monitor/m3_record_monitor.py'
spec=importlib.util.spec_from_file_location('m3_record_monitor',SPECPATH)
monitor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def evaluate():
    contract=load_contract(ROOT/'contracts/m3_nav_v1.template.json')
    root=ROOT/'examples/m3'
    label_set=json.loads((root/'FIXTURE_LABELS.json').read_text())['labels']
    confusion={'tp':0,'tn':0,'fp':0,'fn':0}
    disagreements=[]
    rows=[]
    for label in label_set:
        name=label['id']
        raw=root/(name+'.jsonl')
        a=audit_records(contract,iter_jsonl(raw),evidence_source='synthetic_unattested')
        b=monitor.independently_check(ROOT/'contracts/m3_nav_v1.template.json',raw)
        reject=a['status']!='CONTRACT_OBSERVED'
        independently_rejected=b['verdict']!='OBSERVED'
        invalid=not label['expected_topic_audit_pass']
        if reject and invalid:confusion['tp']+=1
        if not reject and not invalid:confusion['tn']+=1
        if reject and not invalid:confusion['fp']+=1
        if not reject and invalid:confusion['fn']+=1
        if reject!=independently_rejected:disagreements.append(name)
        rows.append({'fixture':name,'known_invalid_in_synthetic_contract':invalid,
                     'process_rejected':reject,'separate_monitor_rejected':independently_rejected,
                     'error_codes':[e['code'] for e in a['errors']]})
    sensitivity=confusion['tp']/(confusion['tp']+confusion['fn']) if confusion['tp']+confusion['fn'] else None
    specificity=confusion['tn']/(confusion['tn']+confusion['fp']) if confusion['tn']+confusion['fp'] else None
    return {'schema_version':'veab.m3.synthetic-controls/1',
            'status':'SYNTHETIC_MECHANISM_TEST_ONLY',
            'external_ground_truth':False,'robot_data_used':False,
            'scientific_performance_estimate':False,
            'sample_size':len(label_set),'confusion':confusion,
            'sensitivity_synthetic':sensitivity,'specificity_synthetic':specificity,
            'separate_monitor_disagreements':disagreements,'cases':rows}

if __name__=='__main__':
    r=evaluate()
    target=ROOT/'examples/m3/synthetic-control-results.json'
    target.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='cases'},indent=2))
