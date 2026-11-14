# VEAB release tickets ready to create in GitHub

The connected repository is read-only to this assistant. These are draft issues only; **none was opened on GitHub**.

## v0.6-01 — Freeze native physics input tape [P0]

Implement shared ENU frame, scene/scenario SHA, seed, command rate and actuator control assumptions. Negative tests for edited controls, missing observations and time drift. **Exit:** independent CI reproduces the control-tape hash; native trace declared separately from a synthetic control fixture.

## v0.6-02 — Execute true MuJoCo dynamics [P0]

Pin runtime and execute one known research-surrogate scene through `mujoco.MjModel/mj_step`. Capture version/build, root states and native contacts. **Exit:** native Linux job stores trace + environment metadata; fails when MuJoCo is unavailable. Model calibration is a separate ticket.

## v0.6-03 — Execute true Isaac Lab dynamics [P0]

Using pinned Isaac Lab/Isaac Sim, construct physics-ready articulation/scene and inject frozen tape into a controller with disclosed mapping. Export actual root and contact observations. **Exit:** second native trace, frame and timing checks, recorded command-tape hash, reproducible launch command, no synthetic fallback.

## v0.6-04 — Cross-engine calibration and held-out experiments [P0]

Match inertial and contact parameters, declare tolerance before measuring held-out scenes, run >=20 paired tapes over two independently authored families. Report RMSE/p90/max, contact disagreement, timing drift and null outcomes. **Exit:** reproducibility bundle and external review. No physical-truth claim.

## v0.7-01 — External OIDC + verified tenant isolation [P0]

Pin provider and audience; verify JWT/JWKS rotation, roles at server side, deny-all defaults, audit and negative cross-tenant tests. **Exit:** tests plus independent security review; no production cutover from dev tokens alone.

## v0.7-02 — Postgres/object storage/work queues [P0]

Migrations with rollback, protected object names, per-tenant key boundaries, durable job leases and dead-letter processing. **Exit:** concurrent/restart/restore/load tests on an isolated staging environment, artifact chain continuity.

## v0.8-01 — Read-only ROS 2/MCAP pipeline [P0]

Decode required topics, preserve source and receipt times, TF calibration and transforms, rejects invalid epochs. No actuation. **Exit:** source-data completeness report and one partner-approved shadow-mode ingest replay.

## v0.8-02 — Independent ground truth / robot pilot [P0]

Procure external measurement, write sensor calibration and hazard review, blinded review procedure, safety envelope and privacy/partner agreement. **Exit:** a separately signed external evidence bundle; not a standalone ROS odom claim.

## v0.9-01 — Security / resilience / evaluation [P0]

External penetration test, remediation and retest, restore drill, documented SLO, scene-clustered confirmatory stats, reviewer reliability, null results. **Exit:** independent reports and customer security sign-off.

## v1.0-01 — Named intended-use production qualification [P0]

Customer pilot acceptance, ongoing monitoring and incident response, SLA only after observed evidence, data retention and commercial terms. **Exit:** context-specific sign-off; safety certification only if actually awarded by an accredited body.

## Funding and research track (parallel)

Separate claim-specific scientific white paper, funder go/no-go/TRL memo, pilot evidence and budget schedule. Do not state a grant has been awarded or a pilot committed without its own signed evidence.
