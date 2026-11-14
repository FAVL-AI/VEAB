"""Blind review templates and Cohen's kappa on independently supplied labels.

Does not create human judgments, and never treats synthetic labels as humans.
"""
from __future__ import annotations
import argparse
import csv
import json
import random
from collections import Counter,defaultdict
from pathlib import Path

VALID={'accept','reject','uncertain'}


def make_blinded_template(fixture_dir,output, *, review_export=None, mapping_output=None):
    fixture_dir=Path(fixture_dir)
    ids=sorted(f.stem for f in fixture_dir.glob('*.json') if f.name!='reference_labels.json')
    random.Random(20261112).shuffle(ids)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    mapping={f'VEAB-R-{i:04d}':id for i,id in enumerate(ids,1)}
    with output.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['episode_id','reviewer_id','verdict','reason','reviewer_blinded_to_policy'])
        w.writeheader()
        for alias in mapping:
            w.writerow({'episode_id':alias,'reviewer_id':'','verdict':'','reason':'','reviewer_blinded_to_policy':''})
    if review_export:
        review_dir=Path(review_export);review_dir.mkdir(parents=True,exist_ok=True)
        for alias,original in mapping.items():
            record=json.loads((fixture_dir/f'{original}.json').read_text(encoding='utf-8'))
            record['episode_id']=alias
            # Remove administrative source labels; the original reference_labels.json is NEVER copied.
            record.pop('provenance',None)
            (review_dir/f'{alias}.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if mapping_output:
        mapping_path=Path(mapping_output);mapping_path.parent.mkdir(parents=True,exist_ok=True)
        mapping_path.write_text(json.dumps(mapping,indent=2)+'\n',encoding='utf-8')
    return len(ids)

def analyse_adjudication(file):
    with Path(file).open(newline='',encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    by_case=defaultdict(dict)
    for row in rows:
        if not row.get('reviewer_id') or not row.get('verdict'):
            continue
        id,reviewer,label=row['episode_id'].strip(),row['reviewer_id'].strip(),row['verdict'].strip().lower()
        if label not in VALID: raise ValueError(f'unrecognised verdict {label!r}')
        if not id: raise ValueError('empty episode_id')
        if reviewer in by_case[id]: raise ValueError(f'duplicate {id}/{reviewer}')
        by_case[id][reviewer]=label
    raters=sorted({r for votes in by_case.values() for r in votes})
    if len(raters)!=2:
        return {'status':'not_evaluable','n_reviewers':len(raters),'n_paired_items':0,
                'message':'requires exactly two distinct actual reviewers with paired judgments; no human evaluation has been performed'}
    complete=[v for v in by_case.values() if all(r in v for r in raters) and all(v[r]!='uncertain' for r in raters)]
    if len(complete)<2:
        return {'status':'not_evaluable','n_reviewers':2,'n_paired_items':len(complete),'message':'at least two non-uncertain paired judgments required'}
    n=len(complete)
    observed=sum(v[raters[0]]==v[raters[1]] for v in complete)/n
    counts_a=Counter(v[raters[0]] for v in complete)
    counts_b=Counter(v[raters[1]] for v in complete)
    expected=sum(counts_a[k]*counts_b[k] for k in ('accept','reject'))/n**2
    kappa=(observed-expected)/(1-expected) if expected < 1 else (1.0 if observed==1 else None)
    return {'status':'human_labels_reported_not_authenticated','reviewers':raters,'n_paired_items':n,
            'n_uncertain_or_unpaired':len(by_case)-n,
            'observed_agreement':round(observed,5),'chance_agreement':round(expected,5),
            'cohens_kappa':None if kappa is None else round(kappa,5),
            'warning':'This tool computes agreement; it cannot prove reviewer identity, blindness, or calibration'}


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest='command',required=True)
    t=sub.add_parser('template');t.add_argument('--fixtures',default='assurance_controls/fixtures');t.add_argument('--out',default='artifacts/assurance/reviewer-template.csv');t.add_argument('--review-export',default='artifacts/assurance/reviewer-packets');t.add_argument('--mapping-output',default='artifacts/assurance/PRIVATE-reviewer-id-map.json')
    a=sub.add_parser('analyse');a.add_argument('--input',required=True)
    args=p.parse_args()
    if args.command=='template': print(f'Generated {make_blinded_template(args.fixtures,args.out,review_export=args.review_export,mapping_output=args.mapping_output)} anonymised episode rows: {args.out}')
    else: print(json.dumps(analyse_adjudication(args.input),indent=2))

if __name__=='__main__':main()
