#!/usr/bin/env python3
"""Fail-closed check before applying v0.6 patch to an existing VEAB checkout.

The public main branch (at review time) lacked the v0.5 Studio/simulation modules.
Do not deploy the standalone additive patch to that older tree without merging
its prerequisites first.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PREREQUISITES = [
 'veab/spec.py',
 'veab/simulation/scene.py',
 'veab/simulation/export.py',
 'veab/simulation/telemetry.py',
 'veab/enterprise/api.py',
 'assurance_controls/run_controls.py',
]


def check_base(root: str|Path) -> dict:
    root=Path(root)
    missing=[path for path in PREREQUISITES if not (root/path).is_file()]
    return {"eligible":not missing,"prerequisites":PREREQUISITES,
            "missing":missing,"interpretation":"Presence only; does not prove source compatibility or tests"}


def main(argv=None):
    parser=argparse.ArgumentParser(description="VEAB v0.6 pre-merge prerequisite check")
    parser.add_argument('--root',default='.')
    args=parser.parse_args(argv)
    result=check_base(args.root)
    print(json.dumps(result,indent=2))
    return 0 if result['eligible'] else 2


if __name__=='__main__':raise SystemExit(main())
