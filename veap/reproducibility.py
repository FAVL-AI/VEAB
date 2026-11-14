"""Reproducibility report generator for VEAP.

Compiles:
1. Environment & software build version (Python, OS platform, git commit hash).
2. Pinned scenario contracts and SHA-256 digests.
3. Factorial execution traces and ledger root digests.
4. Bit-exact reproducibility audit across duplicate independent executions.
"""
from __future__ import annotations
import hashlib
import platform
import subprocess
import sys
from typing import Any
from pydantic import BaseModel
from .spec import list_scenarios, digest
from .sim import run_episode


class ReproducibilityReport(BaseModel):
    veap_version: str = "0.2.0"
    python_version: str
    os_platform: str
    git_commit: str
    scenario_digests: dict[str, str]
    seeds_audited: list[int]
    total_evaluations: int
    reproducibility_rate: float
    audit_verdict: str


def generate_reproducibility_report(seeds: list[int] | None = None) -> ReproducibilityReport:
    """Generate a publication-grade reproducibility report."""
    if seeds is None:
        seeds = [0, 1, 2]
        
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    
    # Git commit
    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        git_hash = "uncommitted_local_build"

    scenarios = list_scenarios()
    sc_digests = {s.id: digest(s.model_dump(mode="json", exclude_none=True)) for s in scenarios}
    
    total = 0
    matched = 0
    
    for s in scenarios:
        for seed in seeds:
            total += 1
            # Run trial A
            b_a = run_episode(s, "route", seed, True)
            root_a = b_a["manifest"]["ledger_root_sha256"]
            
            # Run trial B (fresh execution)
            b_b = run_episode(s, "route", seed, True)
            root_b = b_b["manifest"]["ledger_root_sha256"]
            
            if root_a == root_b:
                matched += 1

    rate = matched / max(1, total)
    verdict = (
        "100% DETERMINISTIC REPRODUCIBILITY CONFIRMED: All duplicate trials generated "
        "bit-exact identical SHA-256 event chains."
        if rate == 1.0 else f"REPRODUCIBILITY COMPROMISED: {rate:.1%} match rate."
    )

    return ReproducibilityReport(
        python_version=py_ver,
        os_platform=os_info,
        git_commit=git_hash,
        scenario_digests=sc_digests,
        seeds_audited=seeds,
        total_evaluations=total,
        reproducibility_rate=round(rate, 4),
        audit_verdict=verdict
    )

