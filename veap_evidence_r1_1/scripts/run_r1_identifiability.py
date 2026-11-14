"""Deterministic, author-constructed geometry transformations and ablations.

Important: Rigid translations of a single task family are CORRELATED stress
cases, not independent held-out scenes. No scientific confidence intervals or
novelty claims are justified by this output.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path

from veap_evidence.fixtures import cases
from veap_evidence.verdict import evaluate, canonical_hash
from veap_evidence.baselines import grade
from veap_evidence.possible_worlds import construct_gap_pair
from external_monitor.monitor import inspect, independent_verdict
from external_monitor.possible_worlds_checker import verify_pair

CONDITIONS = [
    "compliant", "observed_violation", "missing_critical_interval",
    "missing_irrelevant_camera", "missing_safe_interval", "violation_plus_missing"
]
COMPARATORS = ["goal_only", "sampled_safety", "gap_aware"]


def translated_variant(contract, trace, index):
    """Rigid translation preserves all geometric distances and physical bounds.

    This is deliberately *not* a new independent scene; translations are used
    to test frame arithmetic and brittle hard-coded coordinate assumptions.
    """
    dx = ((index * 7) % 17) * .13
    dy = ((index * 11) % 19) * .07
    c, tr = deepcopy(contract), deepcopy(trace)
    c["id"] += f"-translate-{index:03}"
    c["keepout"] = [c["keepout"][0]+dx,c["keepout"][1]+dy,
                    c["keepout"][2]+dx,c["keepout"][3]+dy]
    c["goal"]["x"] += dx
    c["goal"]["y"] += dy
    for row in tr["samples"]:
        if "x" in row:row["x"] += dx
        if "y" in row:row["y"] += dy
    return c,tr


def run_study(transforms: int = 16):
    if not 1 <= transforms <= 256:raise ValueError("transforms must be 1–256")
    base = cases()
    rows=[]
    for index in range(transforms):
        for condition in CONDITIONS:
            example=base[condition]
            contract,trace=translated_variant(example["contract"],example["trace"],index)
            cert=evaluate(contract,trace)
            sep=inspect(contract,trace,cert)
            monitor=independent_verdict(contract,trace)
            score={name:grade(contract,trace,name) for name in COMPARATORS}
            pair=None
            if condition=="missing_critical_interval":
                proposed=construct_gap_pair(contract,trace)
                checked=verify_pair(contract,trace,proposed)
                pair={"checksum":proposed["pair_sha256"],
                      "check":checked["status"],
                      "worlds":{k:{"verdict":v["world_verdict"],
                                   "min_clearance_m":round(v["minimum_path_clearance_m"],6)}
                                for k,v in checked["world_results"].items()}}
            rows.append({
                "case_id":f"translation_{index:03}/{condition}",
                "condition":condition,
                "transformation_id":index,
                "oracle_is_author_constructed":True,
                "expected_epistemic_verdict":example["oracle"],
                "full_trace_truth_class":example["ground_truth_class"],
                "veap_verdict":cert["verdict"],
                "checker_status":sep["certificate_check"],
                "separate_checker_verdict":monitor["verdict"],
                "comparators":score,
                "contract_sha256":canonical_hash(contract),
                "available_trace_sha256":canonical_hash(trace),
                "certificate_sha256":cert["certificate_sha256"],
                "unresolved_coverage":cert["unresolved_coverage"],
                "possible_worlds_pair":pair,
            })
    def match_rows(name):
        return sum((row["veap_verdict"] if name=="veap"
                    else row["separate_checker_verdict"] if name=="separate_monitor"
                    else row["comparators"][name])==row["expected_epistemic_verdict"]
                   for row in rows)
    result={
        "schema":"veap.r1.identifiability-study/1",
        "study":"AUTHOR_CONSTRUCTED_DETERMINISTIC_STRESS_TEST",
        "conditions":CONDITIONS,"number_of_geometry_translations":transforms,
        "unit_of_scientific_generalisation":"NOT_ESTABLISHED",
        "n_cases":len(rows),
        "no_independent_scenes":True,
        "no_experimental_p_value_or_sota_claim":True,
        "upstream_EAI_reproduction":"NOT_RUN",
        "upstream_ABC_reproduction":"NOT_RUN",
        "source_authenticity":"UNATTESTED",
        "method":"Rigid translations of author-specified examples; do not treat as independent replications",
        "summary":{
            "expected_epistemic_verdicts":dict(Counter(x["expected_epistemic_verdict"] for x in rows)),
            "correct_by_method":{method:match_rows(method) for method in ["veap","separate_monitor",*COMPARATORS]},
            "accepted_veap_certificates":sum(r["checker_status"]=="PASS" for r in rows),
            "accepted_counterfactual_ambiguity_witnesses":sum(r.get("possible_worlds_pair",{}).get("check")=="PASS"
                for r in rows if r["possible_worlds_pair"] is not None),
            "correlated_stress_cases_not_holdout_scenes":len(rows),
        },
        "cases":rows,
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--transforms',type=int,default=16)
    p.add_argument('--out',default='artifacts/r1_identifiability/stress_report.json')
    a=p.parse_args()
    out=Path(a.out)
    result=run_study(a.transforms)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'out':str(out), 'cases':result['n_cases'],
                      'summary':result['summary']},indent=2))

if __name__=='__main__':main()
