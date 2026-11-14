"""Repeatable experiment CLI and offline evidence verification."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from .spec import load_scenario, list_scenarios
from .sim import run_episode
from .verifier import verify_bundle


def write_json(path: str, data: dict):
    file = Path(path)
    file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="veap",description="VEAP verifiable embodied-agent research platform")
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("scenarios",help="List the immutable scenario contracts")
    run = sub.add_parser("run",help="Run a deterministic, read-only toy simulator trial")
    run.add_argument("--scenario",default="warehouse-transfer")
    run.add_argument("--policy",choices=["route","greedy"],default="route")
    run.add_argument("--seed",type=int,default=17)
    run.add_argument("--no-shield",action="store_true")
    run.add_argument("--out",default="artifacts/manual-run.json")
    expert = sub.add_parser("expert-review",help="Optional OpenRouter advisory review; sends PUBLIC task contract externally")
    expert.add_argument("--scenario",required=True)
    expert.add_argument("--model",default=None)
    expert.add_argument("--out",default="artifacts/expert-review.json")
    ingest = sub.add_parser("ingest",help="Import read-only positional JSONL (provenance remains unattested)")
    ingest.add_argument("--scenario",required=True)
    ingest.add_argument("--trace",required=True)
    ingest.add_argument("--out",default="artifacts/imported-trace.json")
    verify = sub.add_parser("verify",help="Verify a standalone bundle without running a model")
    verify.add_argument("bundle")
    verify.add_argument("--require-attestation",action="store_true",help="Require valid HMAC signature")
    suite = sub.add_parser("suite",help="Generate ablation data across seeds, split, policy and shield")
    suite.add_argument("--seeds",type=int,nargs="+",default=[0,1,2])
    suite.add_argument("--split",choices=["train","validation","test","all"],default="all")
    suite.add_argument("--out",default="artifacts/suite-summary.json")

    # Research v0.3.0 Tools
    res_analyse = sub.add_parser("research-analyse",help="Rerun numerical JSON process analysis from 60-trial summary")
    res_analyse.add_argument("summary",help="Path to 60-trial summary JSON")
    res_analyse.add_argument("--out",default="artifacts/research/process-analysis.json")

    res_run = sub.add_parser("research-run",help="Rerun factorial experiment suite")
    res_run.add_argument("--seeds",type=int,nargs="+",default=[0,1,2])
    res_run.add_argument("--split",choices=["train","validation","test","all"],default="all")
    res_run.add_argument("--out",default="artifacts/research/reexecuted-factorial.json")

    tamper = sub.add_parser("tamper-audit",help="Run evidence attack regression and custody audit")
    tamper.add_argument("--out",default="artifacts/research/tamper-audit.json")
    
    # Research Gate 4: NVIDIA Isaac Lab Direct RL / Manager-based Export
    exp_isaac = sub.add_parser("export-isaac",help="Export Isaac Lab Direct RL environment definition for a scenario")
    exp_isaac.add_argument("--scenario",required=True)
    exp_isaac.add_argument("--out",default=None,help="Output path for python environment script (stdout if omitted)")
    
    # Multi-Simulator: MuJoCo MJCF Model Export
    exp_mjcf = sub.add_parser("export-mjcf",help="Export MuJoCo MJCF XML physics model for a scenario")
    exp_mjcf.add_argument("--scenario",required=True)
    exp_mjcf.add_argument("--out",default=None,help="Output path for MJCF XML file (stdout if omitted)")
    
    # Research Gate 3: Incremental Diagnostic Value Evaluation
    diag = sub.add_parser("diagnostics",help="Evaluate incremental diagnostic value (outcome-only vs. process verification)")
    diag.add_argument("--suite",default=None,help="Path to suite-summary.json (runs fresh evaluation if omitted)")
    diag.add_argument("--out",default="artifacts/diagnostics-report.json")
    
    # Cross-Simulator Benchmarking & Fidelity Transfer
    bench = sub.add_parser("benchmark-transfer",help="Compare two simulator trajectories for fidelity/reality gap")
    bench.add_argument("--bundle-a",required=True,help="First evidence bundle (e.g. kinematic or sim)")
    bench.add_argument("--bundle-b",required=True,help="Second evidence bundle (e.g. MuJoCo, Isaac or hardware)")
    bench.add_argument("--out",default="artifacts/transfer-metrics.json")
    
    # 8-Metric Comprehensive Evaluation Matrix
    mat = sub.add_parser("run-matrix",help="Run comprehensive evaluation matrix reporting all 8 metrics separately")
    mat.add_argument("--seeds",type=int,nargs="+",default=[0,1,2])
    mat.add_argument("--out",default="artifacts/evaluation-matrix.json")
    
    args = parser.parse_args(argv)
    key = os.getenv("VEAP_ATTESTATION_KEY")
    if args.command == "scenarios":
        for s in list_scenarios(): print(f"{s.id:<26} {s.split:<11} {s.family:<12} {s.title}")
        return 0
    if args.command == "run":
        try:
            s = load_scenario(args.scenario)
            bundle = run_episode(s,args.policy,args.seed,not args.no_shield,attestation_key=key)
            report = verify_bundle(bundle,key)
        except (ValueError,FileNotFoundError) as e:
            parser.error(str(e))
        write_json(args.out,{**bundle,"verification":report})
        print(json.dumps({"output":args.out,"scenario":s.id,"verification":report},indent=2))
        return 0 if report["trace_integrity"] else 2
    if args.command == "expert-review":
        from .integrations.openrouter import review_scenario
        result = review_scenario(load_scenario(args.scenario),args.model)
        write_json(args.out,result)
        print(json.dumps({"output":args.out,"result":result},indent=2))
        return 0
    if args.command == "ingest":
        from .ingest import ingest_jsonl
        try:
            bundle = ingest_jsonl(load_scenario(args.scenario),args.trace)
        except (ValueError,FileNotFoundError) as e:
            parser.error(str(e))
        report = verify_bundle(bundle,key)
        write_json(args.out,{**bundle,"verification":report})
        print(json.dumps({"output":args.out,"verification":report},indent=2))
        return 0
    if args.command == "verify":
        bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
        if args.require_attestation and not key:
            report = {"verified": False, "failure_reasons": ["Attestation key required by --require-attestation"]}
            print(json.dumps(report, indent=2))
            return 2
        report = verify_bundle(bundle,key)
        if args.require_attestation and not report.get("attestation_verified"):
            report["verified"] = False
            report["failure_reasons"].append("Missing or invalid attestation signature under --require-attestation")
            print(json.dumps(report, indent=2))
            return 2
        print(json.dumps(report,indent=2))
        return 0 if report["verified"] else 2
    if args.command == "suite":
        records = []
        for s in list_scenarios():
            if args.split != "all" and s.split != args.split: continue
            for seed in args.seeds:
                for policy in ("greedy","route"):
                    for shield in (False,True):
                        bundle = run_episode(s,policy,seed,shield,attestation_key=key)
                        report = verify_bundle(bundle,key)
                        records.append({"scenario_id":s.id,"split":s.split,"seed":seed,
                                        "policy":policy,"shield":shield,
                                        "scenario_sha256":bundle["manifest"]["scenario_sha256"],
                                        "trace_sha256":bundle["manifest"]["ledger_root_sha256"],
                                        **report})
        from .statistics import group_metrics, paired_bootstrap
        groups = group_metrics(records)
        comparison = paired_bootstrap(records,("route",True),("route",False))
        document = {"experimental_notice":"Toy-world demo; NOT external SOTA or physical safety evidence",
                    "split":args.split,"seeds":args.seeds,"records":records,"groups":groups,"paired_comparison_route_shield_on_minus_off":comparison}
        write_json(args.out,document)
        print(json.dumps({"output":args.out,"groups":groups},indent=2))
        return 0
    if args.command == "research-analyse":
        from .research.analyse import run_process_analysis
        rep = run_process_analysis(args.summary, args.out)
        print(f"Generated research process analysis: {args.out}")
        return 0
    if args.command == "research-run":
        records = []
        for s in list_scenarios():
            if args.split != "all" and s.split != args.split: continue
            for seed in args.seeds:
                for policy in ("greedy", "route"):
                    for shield in (False, True):
                        bundle = run_episode(s, policy, seed, shield, attestation_key=key)
                        report = verify_bundle(bundle, key)
                        records.append({"scenario_id": s.id, "split": s.split, "seed": seed,
                                        "policy": policy, "shield": shield,
                                        "scenario_sha256": bundle["manifest"]["scenario_sha256"],
                                        "trace_sha256": bundle["manifest"]["ledger_root_sha256"],
                                        **report})
        from .statistics import group_metrics, paired_bootstrap
        groups = group_metrics(records)
        comparison = paired_bootstrap(records, ("route", True), ("route", False))
        document = {"experimental_notice": "Toy-world demo; NOT external SOTA or physical safety evidence",
                    "split": args.split, "seeds": args.seeds, "records": records, "groups": groups, "paired_comparison_route_shield_on_minus_off": comparison}
        write_json(args.out, document)
        print(f"Generated re-executed factorial suite ({len(records)} runs): {args.out}")
        return 0
    if args.command == "tamper-audit":
        from .research.attacks import run_tamper_audit
        rep = run_tamper_audit(args.out)
        print(json.dumps(rep, indent=2))
        return 0
    if args.command == "export-isaac":
        from .adapters.isaac_lab import export_isaac_lab_code
        sc = load_scenario(args.scenario)
        code = export_isaac_lab_code(sc)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(code, encoding="utf-8")
            print(f"Exported Isaac Lab environment definition to: {args.out}")
        else:
            print(code)
        return 0
    if args.command == "export-mjcf":
        from .adapters.mujoco import export_mjcf_xml
        sc = load_scenario(args.scenario)
        xml = export_mjcf_xml(sc)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(xml, encoding="utf-8")
            print(f"Exported MuJoCo MJCF XML model to: {args.out}")
        else:
            print(xml)
        return 0
    if args.command == "diagnostics":
        from .diagnostics import evaluate_trial_diagnostics
        if args.suite:
            data = json.loads(Path(args.suite).read_text(encoding="utf-8"))
            records = data.get("records", [])
        else:
            # Generate a fresh 60-trial suite for immediate analysis
            records = []
            for s in list_scenarios():
                for seed in (0, 1, 2):
                    for policy in ("greedy", "route"):
                        for shield in (False, True):
                            bundle = run_episode(s, policy, seed, shield, attestation_key=key)
                            report = verify_bundle(bundle, key)
                            records.append({"scenario_id": s.id, "policy": policy, "shield": shield,
                                            "seed": seed, **report})
        report = evaluate_trial_diagnostics(records)
        write_json(args.out, report.model_dump(mode="json"))
        print(json.dumps({"output": args.out, "diagnostics": report.model_dump(mode="json")}, indent=2))
        return 0
    if args.command == "benchmark-transfer":
        from .benchmark import compare_sim_trajectories
        bundle_a = json.loads(Path(args.bundle_a).read_text(encoding="utf-8"))
        bundle_b = json.loads(Path(args.bundle_b).read_text(encoding="utf-8"))
        metrics = compare_sim_trajectories(bundle_a, bundle_b)
        write_json(args.out, metrics.model_dump(mode="json"))
        print(json.dumps({"output": args.out, "transfer_metrics": metrics.model_dump(mode="json")}, indent=2))
        return 0
    if args.command == "run-matrix":
        from .evaluation_matrix import run_evaluation_matrix
        matrix_report = run_evaluation_matrix(args.seeds)
        write_json(args.out, matrix_report.model_dump(mode="json"))
        print(json.dumps({"output": args.out, "matrix": matrix_report.model_dump(mode="json")}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
