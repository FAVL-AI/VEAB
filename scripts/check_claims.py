#!/usr/bin/env python3
"""Run from repository root: python scripts/check_claims.py"""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from veab.governance.claims import validate_registry,check_public_copy


def main():
    root=Path(__file__).resolve().parents[1]
    print(json.dumps({'evidence':validate_registry(root),'copy':check_public_copy(root)},indent=2))


if __name__=='__main__':main()
