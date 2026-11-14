"""Prepare, but never fabricate, external EAI / ABC reproduction evidence.

Usage: python scripts/run_upstream_reproduction.py --eai-dir PATH --abc-dir PATH --out ...
This performs only local git revision and source-layout checks. Original
model/simulator evaluations must be run separately in pinned environments.
"""
from pathlib import Path
import subprocess, argparse, json, hashlib

PINNED = {
    'EAI': ('531c62f8df2cb392bdf1907923c76da41cad4fe6', 'README.md'),
    'ABC': ('ae1124758098876db04336e1d8c6e419a139c6e3', 'ABC.md'),
}

def inspect(name,path):
    ref,required=PINNED[name]
    if not path:
        return {'status':'NOT_RUN','reason':'No local checkout provided','expected_sha':ref}
    repo=Path(path)
    if not (repo/'.git').exists() or not (repo/required).exists():
        return {'status':'BLOCKED','reason':'Missing git checkout or required file','expected_sha':ref}
    p=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode:
        return {'status':'BLOCKED','reason':'git rev-parse failed','expected_sha':ref}
    h=p.stdout.strip()
    return {'status':'SOURCE_PIN_MATCH' if h==ref else 'SOURCE_PIN_MISMATCH',
            'expected_sha':ref,'actual_sha':h,
            'selected_source_sha256':hashlib.sha256((repo/required).read_bytes()).hexdigest(),
            'evaluation_status':'NOT_RUN'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--eai-dir');parser.add_argument('--abc-dir');parser.add_argument('--out',default='artifacts/upstream_status.json');args=parser.parse_args()
    result={'EAI':inspect('EAI',args.eai_dir),'ABC':inspect('ABC',args.abc_dir),
            'statement':'Source-pinning checks do not reproduce any upstream paper results.'}
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
