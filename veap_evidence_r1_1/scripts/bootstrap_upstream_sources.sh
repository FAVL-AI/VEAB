#!/usr/bin/env bash
set -euo pipefail
# OPT-IN NETWORK: run on the research workstation, not the robot.
# This script retrieves original upstream source code, NOT datasets or weights.
BASE="${1:-$HOME/veap-research/upstream}"
mkdir -p "$BASE"
if [[ -e "$BASE/EAI" || -e "$BASE/ABC" ]]; then
  echo 'Refusing to overwrite existing checkouts'; exit 2
fi
git clone https://github.com/embodied-agent-interface/embodied-agent-interface.git "$BASE/EAI"
git -C "$BASE/EAI" checkout --detach 531c62f8df2cb392bdf1907923c76da41cad4fe6
git clone https://github.com/uiuc-kang-lab/agentic-benchmarks.git "$BASE/ABC"
git -C "$BASE/ABC" checkout --detach ae1124758098876db04336e1d8c6e419a139c6e3
printf '\nPinned source checkouts: %s\n' "$BASE"
python scripts/run_upstream_reproduction.py --eai-dir "$BASE/EAI" --abc-dir "$BASE/ABC"
