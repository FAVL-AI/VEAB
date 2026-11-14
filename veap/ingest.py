"""Read-only JSONL telemetry import from future ROS2/Isaac exporters.

Imported positional evidence is never classified as an authenticated robot run.
This adapter DOES NOT send motion commands, or claim MCAP parsing support.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from .ledger import Ledger
from .spec import Scenario, digest


def ingest_jsonl(scenario: Scenario, path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 8_000_000:
        raise ValueError("telemetry file missing or too large")
    samples = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item,dict) or set(item) != {"tick","x","y","vx","vy"}:
                raise ValueError("telemetry schema requires tick, x, y, vx, vy only")
            if not isinstance(item['tick'],int) or item['tick'] != len(samples):
                raise ValueError("ticks must be contiguous starting at 0")
            if not all(isinstance(item[k],(int,float)) and math.isfinite(item[k]) and abs(item[k]) < 100000 for k in ("x","y","vx","vy")):
                raise ValueError("invalid finite telemetry")
            samples.append(item)
            if len(samples) > scenario.max_steps + 1:
                raise ValueError("exceeds scenario max_steps")
    if len(samples) < 2:
        raise ValueError("need at least two telemetry states")
    ledger = Ledger()
    current_stage = 0
    for item in samples:
        tick = item["tick"]
        ledger.emit(tick,"state",{**{k:round(float(item[k]),5) for k in ("x","y","vx","vy")},"stage":current_stage})
        if scenario.target_present and current_stage < len(scenario.waypoints):
            wp = scenario.waypoints[current_stage]
            if math.hypot(item["x"]-wp.x,item["y"]-wp.y) <= scenario.waypoint_tolerance:
                ledger.emit(tick,"milestone",{"index":current_stage,"label":wp.label})
                current_stage += 1
    claim = "completed" if scenario.target_present and current_stage == len(scenario.waypoints) else "timeout"
    ledger.emit(samples[-1]["tick"],"terminal",{"claimed":claim,"claimed_stage":current_stage})
    m = {"schema_version":"veap-bundle/1","source":"external_unattested_telemetry",
         "environment":"External JSONL positional samples; source and sensor authenticity NOT verified",
         "scenario":scenario.model_dump(mode="json", exclude_none=True),"scenario_sha256":digest(scenario.model_dump(mode="json", exclude_none=True)),
         "policy":"external_unknown","seed":None,"shield_enabled":None,"harness_version":"0.1.0",
         "dt_seconds":scenario.dt,"simulation_steps":samples[-1]["tick"],"ledger_root_sha256":ledger.root,
         "input_sha256":__import__('hashlib').sha256(path.read_bytes()).hexdigest()}
    return {"manifest":m,"events":ledger.events,"attestation":None}
