#!/usr/bin/env python3
"""VEAP v0.7 security hygiene CLI: CycloneDX SBOM generation and secret-pattern scan."""
from __future__ import annotations

import argparse
import importlib.metadata as importlib_metadata
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("generic_sk_live", re.compile(r"\bsk-[A-Za-z0-9]{24,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
)


def generate_cyclonedx_sbom() -> dict[str, Any]:
    """Build a CycloneDX 1.5 JSON SBOM from installed Python distributions."""
    components = []
    for dist in sorted(importlib_metadata.distributions(), key=lambda d: (d.metadata["Name"] or "").lower()):
        name = dist.metadata.get("Name")
        version = dist.version
        if not name:
            continue
        components.append({
            "type": "library",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name.lower()}@{version}",
        })
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "veap-platform",
                "version": "0.7.0-dev",
            }
        },
        "components": components,
    }


def scan_tracked_secrets(repo_root: Path = ROOT) -> dict[str, Any]:
    """Scan git-tracked text files for high-confidence secret patterns."""
    files = subprocess.check_output(
        ["git", "ls-files"], cwd=str(repo_root), text=True
    ).splitlines()
    findings: list[dict[str, Any]] = []
    scanned = 0
    for rel in files:
        if rel == "scripts/check_v07_security.py":
            continue
        p = repo_root / rel
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rule, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append({"file": rel, "line": lineno, "rule": rule})
    return {"scanned_files": scanned, "finding_count": len(findings), "findings": findings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VEAP v0.7 SBOM & secret-scan gate")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sbom_p = sub.add_parser("sbom")
    sbom_p.add_argument("--out", default="artifacts/v07/sbom.cdx.json")
    sub.add_parser("secret-scan")
    args = parser.parse_args(argv)
    if args.cmd == "sbom":
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc = generate_cyclonedx_sbom()
        out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"bomFormat": doc["bomFormat"], "components": len(doc["components"]), "out": str(out)}))
        return 0
    res = scan_tracked_secrets()
    print(json.dumps(res, indent=2))
    return 0 if res["finding_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
