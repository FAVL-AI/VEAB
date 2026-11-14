"""VEAP R1 research commands; read-only and synthetic by default."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from .verdict import load_record,evaluate,EvaluationError,canonical_hash
from .baselines import grade
from .fixtures import cases,contract


def main(argv=None):
    parser=argparse.ArgumentParser(description='VEAP R1 contract-conditioned evidence checks')
    sp=parser.add_subparsers(dest='cmd',required=True)
    demo=sp.add_parser('demo');demo.add_argument('--out',default='artifacts/synthetic_comparison.json')
    check=sp.add_parser('check');check.add_argument('contract');check.add_argument('trace');check.add_argument('--out')
    verify=sp.add_parser('verify-certificate');verify.add_argument('contract');verify.add_argument('trace');verify.add_argument('certificate')
    args=parser.parse_args(argv)
    if args.cmd=='demo':
        rows=[]; comparators=['goal_only','terminal_safety','sampled_safety','gap_aware']
        for key,item in cases().items():
            c=item['contract'];tr=item['trace'];cert=evaluate(c,tr)
            rows.append({'id':key,'oracle':item['oracle'],'truth_class_label':item['ground_truth_class'],
                         'veap':cert['verdict'],'baselines':{m:grade(c,tr,m) for m in comparators},
                         'certificate':cert})
        result={'study':'SYNTHETIC_MECHANISM_DEMO_NOT_EXTERNAL_VALIDATION',
                'reproduction':{'source':'local generated fixtures','upstream_EAI':'NOT_RUN','upstream_ABC':'NOT_RUN'},
                'n':len(rows),'cases':rows,
                'note':'Reference truth class is synthetic; the evaluator never consumes it.'}
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'output':str(out),'n':len(rows),
                          'veap_oracle_agreement':sum(r['veap']==r['oracle'] for r in rows),
                          'baseline_agreement':{m:sum(r['baselines'][m]==r['oracle'] for r in rows) for m in comparators}},indent=2))
        return 0
    try:
        c,_=load_record(args.contract);tr,source=load_record(args.trace)
        if args.cmd=='check':
            cert=evaluate(c,tr,source)
            output=json.dumps(cert,indent=2,sort_keys=True)+'\n'
            if args.out:
                d=Path(args.out);d.parent.mkdir(parents=True,exist_ok=True);d.write_text(output)
            print(output);return 0
        cmd=[sys.executable,str(Path(__file__).parents[1]/'external_monitor'/'monitor.py'),
             args.contract,args.trace,args.certificate]
        result=subprocess.run(cmd,check=False,text=True,capture_output=True)
        print(result.stdout or result.stderr)
        return result.returncode
    except (EvaluationError,OSError) as exc:
        print('INVALID INPUT:',exc,file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
