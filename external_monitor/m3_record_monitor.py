#!/usr/bin/env python3
"""Second, separate-implementation monitor for exported M3 ROS evidence envelopes.

Does not import VEAB, agent, or simulation code. Reads a frozen JSON contract.
Both monitors may share the same untrusted data source: NO external ground truth
or organisational independence is implied.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys


def independently_check(contract_path: str | Path, jsonl_path: str | Path) -> dict:
    contract = json.loads(Path(contract_path).read_text(encoding='utf-8'))
    if contract.get('purpose') != 'read_only_evidence_audit' or contract.get('schema_version') != 'veab.m3.contract/1':
        raise ValueError('unsupported evidence contract')
    if contract.get('source_trust') != 'unattested':
        raise ValueError('unsupported source trust assertion')
    grouped = defaultdict(list)
    observed_times = []
    for index, line in enumerate(Path(jsonl_path).open(encoding='utf-8')):
        if not line.strip():
            continue
        if index >= 1_000_000 or len(line) > 1_048_576:
            raise ValueError('input bounds exceeded')
        r = json.loads(line)
        if not isinstance(r, dict) or r.get('schema_version') != 'veab.m3.record/1':
            raise ValueError('unsupported record schema')
        t = r.get('log_time_ns')
        if type(t) is not int or t < 0 or t > 10**20:
            raise ValueError('invalid timestamp')
        if not isinstance(r.get('topic'), str):
            raise ValueError('invalid topic')
        observed_times.append(t)
        grouped[r['topic']].append(r)
    errors = []
    if not observed_times:
        errors.append('EMPTY_RECORDING')
    start = min(observed_times) if observed_times else 0
    end = max(observed_times) if observed_times else 0
    if contract['window']['mode'] == 'explicit':
        start, end = contract['window']['start_ns'],contract['window']['end_ns']
    metrics = {}
    for label, c in contract['channels'].items():
        topic = c['topic']
        frames = grouped.get(topic,[])
        metrics[label]={'count':len(frames)}
        if not frames:
            if c['required']:
                errors.append(f'REQUIRED_TOPIC_MISSING:{label}')
            continue
        ts = [v['log_time_ns'] for v in frames]
        if any(b < a for a,b in zip(ts, ts[1:])):
            errors.append(f'TIME_REVERSED:{label}')
        if any(v.get('ros_type') != c['ros_type'] for v in frames):
            errors.append(f'TYPE_MISMATCH:{label}')
        maxgap = c.get('max_gap_ns')
        if maxgap is not None:
            sorted_ts=sorted(ts)
            gaps=[sorted_ts[0]-start, end-sorted_ts[-1]] + [b-a for a,b in zip(sorted_ts, sorted_ts[1:])]
            actual=max(gaps)
            metrics[label]['max_observed_gap_ns']=actual
            if actual>maxgap:
                errors.append(f'TOPIC_GAP:{label}')
        maxlag=c.get('max_header_lag_ns')
        if maxlag is not None:
            if any(type(v.get('header_stamp_ns')) is not int for v in frames):
                errors.append(f'HEADER_TIMESTAMP_MISSING:{label}')
            elif any(abs(v['header_stamp_ns']-v['log_time_ns'])>maxlag for v in frames):
                errors.append(f'HEADER_CLOCK_GAP:{label}')
        expected_frame=c.get('frame_id')
        if expected_frame is not None:
            seen=[v.get('frame_id') for v in frames]
            if any(frame != expected_frame for frame in seen):
                errors.append(f'FRAME_MISMATCH:{label}')
    return {
        'schema_version':'veab.m3.independent-monitor/1',
        'verdict':'OBSERVED' if not errors else 'INCOMPLETE',
        'read_only':True,
        'organisational_independence':False,
        'external_ground_truth':False,
        'record_count':len(observed_times),
        'channels':metrics,
        'errors':errors,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description='Independent implementation (not independent ground truth)')
    parser.add_argument('--contract',required=True)
    parser.add_argument('--jsonl',required=True)
    parser.add_argument('--out')
    args=parser.parse_args(argv)
    try:
        verdict=independently_check(args.contract,args.jsonl)
        output=json.dumps(verdict,indent=2,sort_keys=True)+'\n'
        if args.out: Path(args.out).write_text(output,encoding='utf-8')
        else: print(output,end='')
        return 0 if verdict['verdict']=='OBSERVED' else 3
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(json.dumps({'status':'INPUT_REJECTED','error':str(exc)}),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
