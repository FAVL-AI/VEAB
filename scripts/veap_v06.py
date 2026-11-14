#!/usr/bin/env python3
"""Locked cross-engine replay CLI. No physical hardware or cloud actions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from veap.spec import load_scenario
from veap.simulation.locked_replay import (
    diagnose_paired_replay,
    paired_physics_report,
    standard_tape,
    validate_execution,
    validate_tape,
)


def load(path):
    p = Path(path)
    if p.stat().st_size > 12_000_000:
        raise ValueError("input larger than supported 12 MB")
    return json.loads(p.read_text(encoding="utf8"))


def save(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="VEAP locked cross-engine research replay")
    sub = parser.add_subparsers(dest="command", required=True)
    tape = sub.add_parser("tape", help="Create a bounded frozen control tape (NOT a native simulation)")
    tape.add_argument("--scenario", default="warehouse-transfer")
    tape.add_argument("--steps", type=int, default=24)
    tape.add_argument("--seed", type=int, default=17)
    tape.add_argument("--out", default="artifacts/v06/warehouse-control-tape.json")
    native = sub.add_parser("run-mujoco", help="Actually step native MuJoCo; fail if unavailable")
    native.add_argument("--tape", required=True)
    native.add_argument("--out", default="artifacts/v06/mujoco")
    verify = sub.add_parser("verify", help="Check a physics trace against the frozen tape")
    verify.add_argument("--tape", required=True)
    verify.add_argument("--trace", required=True)
    diff = sub.add_parser("compare", help="Compare two actually acquired physics traces")
    diff.add_argument("--tape", required=True)
    diff.add_argument("--left", required=True)
    diff.add_argument("--right", required=True)
    diff.add_argument("--rmse-target", type=float, default=0.1)
    diff.add_argument("--out", default="artifacts/v06/cross-engine-report.json")
    diag = sub.add_parser("diagnose", help="Produce per-tick divergence localization and repeatability report")
    diag.add_argument("--tape", required=True)
    diag.add_argument("--left", required=True)
    diag.add_argument("--right", required=True)
    diag.add_argument("--repeat-left", default=None)
    diag.add_argument("--repeat-right", default=None)
    diag.add_argument("--pos-threshold", type=float, default=0.001)
    diag.add_argument("--vel-threshold", type=float, default=0.01)
    diag.add_argument("--rmse-target", type=float, default=0.1)
    diag.add_argument("--out", default="artifacts/v06/pilot-per-tick-diagnostic.json")
    freeze = sub.add_parser("freeze-manifest", help="Freeze Stage 3 v0.6 evaluation manifest (criteria, assets, held-out tapes)")
    freeze.add_argument("--export-dir", default="artifacts/research/v06-assets")
    freeze.add_argument("--out", default="artifacts/research/v06-evaluation-manifest.json")
    gate = sub.add_parser("evaluate-gate", help="Evaluate 40+ native traces against a frozen v0.6 evaluation manifest")
    gate.add_argument("--manifest", required=True)
    gate.add_argument("--traces-dir", required=True)
    gate.add_argument("--out", default="artifacts/research/v06-release-gate-report.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze-manifest":
            from veap.simulation.v06_gate import build_v06_evaluation_manifest
            result = build_v06_evaluation_manifest(export_dir=args.export_dir)
            save(args.out, result)
            print(json.dumps({
                "result": "v0.6 evaluation manifest frozen",
                "manifest_sha256": result["manifest_sha256"],
                "held_out_summary": result["held_out_summary"],
                "out": args.out,
            }, indent=2))
            return 0
        if args.command == "evaluate-gate":
            from veap.simulation.v06_gate import evaluate_v06_release_gate
            manifest = load(args.manifest)
            traces_root = Path(args.traces_dir)
            paired_runs = []
            for entry in manifest["tapes"]:
                tid = entry["tape_id"]
                mj_path = traces_root / "mujoco" / f"{tid}.json"
                il_path = traces_root / "isaaclab" / f"{tid}.json"
                if not mj_path.is_file() or not il_path.is_file():
                    paired_runs.append({"tape_id": tid, "error": f"missing trace: mj={mj_path.is_file()}, il={il_path.is_file()}"})
                else:
                    paired_runs.append({"tape_id": tid, "mujoco": load(mj_path), "isaaclab": load(il_path)})
            report = evaluate_v06_release_gate(manifest, paired_runs)
            save(args.out, report)
            print(json.dumps({"gate_passed": report["gate_passed"], "summary": report["summary"], "out": args.out}, indent=2))
            return 0
        if args.command == "tape":
            s = load_scenario(args.scenario)
            result = standard_tape(s, seed=args.seed, steps=args.steps)
            save(args.out, result)
            print(json.dumps({"result": "control tape generated; native engine NOT executed", "tape_sha256": result["tape_sha256"], "out": args.out}))
            return 0
        t = load(args.tape)
        s = load_scenario(t["scenario_id"])
        validate_tape(s, t)
        if args.command == "run-mujoco":
            from veap.simulation.native_locked_runner import run_mujoco_tape
            result = run_mujoco_tape(s, t, args.out)
            dest = str(Path(args.out) / "native-locked-replay.json")
            save(dest, result)
            print(json.dumps({"result": "native MuJoCo completed", "out": dest, "trace_samples": len(result["trace"]["samples"])}))
            return 0
        if args.command == "verify":
            payload = load(args.trace)
            result = validate_execution(s, t, payload.get("trace", payload))
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "compare":
            l = load(args.left)
            r = load(args.right)
            result = paired_physics_report(s, t, l.get("trace", l), r.get("trace", r), max_position_rmse_m=args.rmse_target)
            save(args.out, result)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "diagnose":
            l = load(args.left)
            r = load(args.right)
            rep_l = load(args.repeat_left) if args.repeat_left else None
            rep_r = load(args.repeat_right) if args.repeat_right else None
            result = diagnose_paired_replay(
                s,
                t,
                l.get("trace", l),
                r.get("trace", r),
                position_divergence_threshold_m=args.pos_threshold,
                velocity_divergence_threshold_m_s=args.vel_threshold,
                max_position_rmse_m=args.rmse_target,
                repeat_left=rep_l.get("trace", rep_l) if rep_l else None,
                repeat_right=rep_r.get("trace", rep_r) if rep_r else None,
            )
            save(args.out, result)
            print(json.dumps({"summary": result["summary"], "localization": result["localization"], "repeatability": result["repeatability"]}, indent=2))
            return 0
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        parser.exit(3, "VEAP locked replay blocked: " + str(error) + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
