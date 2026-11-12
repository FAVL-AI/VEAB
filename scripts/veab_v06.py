#!/usr/bin/env python3
"""Locked v0.6 replay CLI. No physical hardware or cloud actions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from veab.spec import load_scenario
from veab.simulation.locked_replay import standard_tape, validate_tape, validate_execution, paired_physics_report


def load(path):
    p=Path(path)
    if p.stat().st_size>12_000_000:
        raise ValueError('input larger than supported 12 MB')
    return json.loads(p.read_text(encoding='utf8'))


def save(path,obj):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf8')


def main(argv=None):
    parser=argparse.ArgumentParser(description='VEAB v0.6 locked cross-engine research replay')
    sub=parser.add_subparsers(dest='command',required=True)
    tape=sub.add_parser('tape',help='Create a bounded frozen control tape (NOT a native simulation)')
    tape.add_argument('--scenario',default='warehouse-transfer')
    tape.add_argument('--steps',type=int,default=24)
    tape.add_argument('--seed',type=int,default=17)
    tape.add_argument('--out',default='artifacts/v06/warehouse-control-tape.json')
    native=sub.add_parser('run-mujoco',help='Actually step native MuJoCo; fail if unavailable')
    native.add_argument('--tape',required=True)
    native.add_argument('--out',default='artifacts/v06/mujoco')
    verify=sub.add_parser('verify',help='Check a physics trace against the frozen tape')
    verify.add_argument('--tape',required=True)
    verify.add_argument('--trace',required=True)
    diff=sub.add_parser('compare',help='Compare two actually acquired physics traces')
    diff.add_argument('--tape',required=True)
    diff.add_argument('--left',required=True)
    diff.add_argument('--right',required=True)
    diff.add_argument('--rmse-target',type=float,default=.1)
    diff.add_argument('--out',default='artifacts/v06/cross-engine-report.json')
    args=parser.parse_args(argv)
    try:
        if args.command=='tape':
            s=load_scenario(args.scenario)
            result=standard_tape(s,seed=args.seed,steps=args.steps)
            save(args.out,result)
            print(json.dumps({'result':'control tape generated; native engine NOT executed','tape_sha256':result['tape_sha256'],'out':args.out}))
            return 0
        t=load(args.tape)
        s=load_scenario(t['scenario_id'])
        validate_tape(s,t)
        if args.command=='run-mujoco':
            from veab.simulation.native_locked_runner import run_mujoco_tape
            result=run_mujoco_tape(s,t,args.out)
            dest=str(Path(args.out)/'native-locked-replay.json')
            save(dest,result)
            print(json.dumps({'result':'native MuJoCo completed','out':dest,'trace_samples':len(result['trace']['samples'])}))
            return 0
        if args.command=='verify':
            payload=load(args.trace)
            result=validate_execution(s,t,payload.get('trace',payload))
            print(json.dumps(result,indent=2))
            return 0
        if args.command=='compare':
            l=load(args.left);r=load(args.right)
            result=paired_physics_report(s,t,l.get('trace',l),r.get('trace',r),max_position_rmse_m=args.rmse_target)
            save(args.out,result)
            print(json.dumps(result,indent=2))
            return 0
    except (ValueError,RuntimeError,OSError,KeyError,TypeError) as error:
        parser.exit(3,'VEAB v0.6 blocked: '+str(error)+'\n')
    return 1


if __name__=='__main__':
    raise SystemExit(main())
