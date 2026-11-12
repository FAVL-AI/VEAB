#!/usr/bin/env bash
set -euo pipefail
if ! test -f pyproject.toml || ! test -d veab; then
  echo 'ERROR: run from the VEAB repository root' >&2
  exit 2
fi
python -m pytest -q tests/test_m3_contract.py
python scripts/run_m3_controls.py
python -m veab.m3_replay.cli --contract contracts/m3_nav_v1.template.json --jsonl examples/m3/clean.jsonl --out /tmp/veab-m3-clean-audit.json
python external_monitor/m3_record_monitor.py --contract contracts/m3_nav_v1.template.json --jsonl examples/m3/clean.jsonl >/tmp/veab-m3-monitor-audit.json
echo 'M3 REPLAY: SYNTHETIC SOFTWARE TESTS PASS; NATIVE ROS2/MCAP AND PHYSICAL SAFETY UNTESTED'
