# VEAP Sovereign Studio R0.3 — Executable Architecture

```
                     FIRST-PARTY VEAP STUDIO (browser)
  ┌──────────────────────────────────────────────────────────────┐
  │ Replay │ 3D World │ Evidence Registry │ Policy │ Assurance │
  │                     Engine Runtime & Jobs                   │
  └──────────────────────────┬───────────────────────────────────┘
                             │ Localhost HTTP API (FastAPI)
       ┌─────────────────────┼─────────────────────────────────┐
       │                     │                                 │
  Raw data vault      Controlled job ledger             VEAP assessor
  SHA256 + SQLite     1 local worker / no shell         replay & contract
       │                     │                                 │
       │     ┌───────────────┼────────────────┐                │
       │     │               │                │                │
   ROS2 MCAP       Isaac Lab/PhysX       MuJoCo 4.x     Independent monitor
   decoders        (external py 3.11)    (external py)   (future external audit)
       │     │               │                │
       │     └───────────────┼────────────────┘
       │                     │
       │           Native 3D telemetry and metadata
       │                     │
       └─────────────────────┼─────────────────────────────────┘
                             │
                   Measurement, not certification
```

Native job input is a bounded built-in experiment, not arbitrary user Python or shell. The service enforces one worker, subprocess timeouts, source-preserving imports and explicit native job statuses. Native simulators run only when configured on the host; the local 2D renderer does not claim PhysX or RTX fidelity.

OpenUSD, MJCF and SDF reference assets are produced from one geometrical seed and carry a digest. Their surface syntax, physics properties and collision representations may differ. CAD/URDF source uploads remain protected raw artifacts, not automatic calibrated rigid-body models.

A native Physics comparison requires the same sample grid and different engine outputs; reports measure 3D divergences and disclose missing contact instrumentation. Any real robot comparison requires external measurements and independent calibration.

LeRobotDataset is a derived training representation, never the primary recording. Every local export preserves the original trace SHA; it rejects episodes with missing actions or irregular timestamps.
