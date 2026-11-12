# M3 Replay evidence register — 2026-11-12

| Claim ID | Claim status | Evidence | Scope / explicit limitation |
|---|---|---|---|
| M3-E001 | IMPLEMENTED | `tests/test_m3_contract.py` and CI report | Contract parser and read-only audit on synthetic envelopes; no robot |
| M3-E002 | DEMONSTRATED (synthetic) | `examples/m3/synthetic-control-results.json` | Constructed negative controls, not an independent benchmark |
| M3-E003 | IMPLEMENTED (not native-tested here) | `veab/m3_replay/rosbag2_adapter.py` | Uses ROS2 rosbag2 reader only; no actual MCAP opened in this environment |
| M3-E004 | IMPLEMENTED | `external_monitor/m3_record_monitor.py` | Separate Python implementation sharing untrusted input; not third-party IV&V |
| M3-E005 | IMPLEMENTED | `veab/m3_replay/attribution.py` | Candidate cause list only; no causal accuracy study |
| M3-E006 | NOT CLAIMED | None | Sensor authenticity, collision avoidance, recovery safety, autonomy deployment safety |
| M3-E007 | NOT CLAIMED | None | Scientifically validated improvement over strong embodied baselines |

**Interpretation:** PASS in source tests is evidence of implemented software conditions, not evidence that a physical robot would be safe or that the evaluation protocol is scientifically validated. The 11-recorded synthetic fixtures do not replace independent scene-level evaluation.
