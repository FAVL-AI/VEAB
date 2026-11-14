"""Score after predictions are committed; small author-constructed demo only."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'artifacts'/'r1_blinded_synthetic'

def main():
    predictions=json.loads((ROOT/'evaluator_results.json').read_text())
    rows=[]
    for pred in predictions['cases']:
        ref=json.loads((ROOT/'reference_only'/f"{pred['case']}.reference.json").read_text())
        rows.append({'id':pred['case'],'actual_synthetic_truth':ref['synthetic_truth'],
                     'expected_epistemic_verdict':ref['expected_epistemic_verdict'],
                     'veap':pred['veap'],'oracle_match':pred['veap']==ref['expected_epistemic_verdict'],
                     'checker':pred['checker'],'baselines':pred['baselines']})
    result={'study':'AUTHOR_SYNTHETIC_NOT_EXTERNAL_VALIDATION','n':len(rows),
            'no_claim_of_sota_or_novelty':True,'cases':rows}
    (ROOT/'scored_results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
