# Integrating v0.4 assurance controls into the reported native VEAB tree

**Important:** This v0.4 additive bundle was created from the v0.3.0 source available in this conversation. The user-reported Rust, C++20, Go 1.26, formal-contract, ROS 2/MCAP, Yahboom and 93-test worktree was **not available for direct inspection**. We did not build or certify those native binaries or 93 tests. Do not overwrite that local tree with this older full source package.

## Safe merge strategy

Copy only `assurance_controls/`, `external_monitor/`, `tests/test_assurance_controls.py` and the new `docs/` files into a feature branch based on the newer local tree. Keep existing `backend/`, `veab/native.py`, real-robot profiles and simulator adapters unchanged. Run their existing 93 tests and the new tests as a single suite after integration. Resolve naming/contracts explicitly rather than assuming compatibility.

## Contracts to implement in native adapters

`veab-monitor-input/1` is currently a standalone test schema. Convert native simulator captures into **separate exported evidence** with:

- Scenario geometry: metres, world frame, robot collision radius, goals, forbidden zones, calibrated contact geometry.
- Pose samples: `t_s`, `x`, `y` with monotonic timestamps; future extension includes SE(3), full-body kinematics and joint covariance.
- Events: `start`, `observation`, `proposal`, `state`, `fault`, `fault_clear`, `recovery`, `intervention`, `terminal` with synchronized timestamps.
- Terminal report: claimed task status, self-reported violation count, recovery claim.
- Source provenance: actual engine name/version, robot profile SHA-256, collision geometry SHA-256, calibration SHA-256, clock source, log-capture witness ID and trust level.

Create a **separate process boundary**: native engine owns raw immutable-on-capture log output; policy must not be able to rewrite monitor evidence. A file naming convention is not isolation. Cross-check timestamps and privileged ground-truth channels; prevent learner access to unavailable future state.

## Native Rust verification

- Verify FIPS 180-4 SHA-256 against published NIST known-answer vectors and canonical JSON cross-language serialization.
- Make a second independently implemented trace checker run on exported records; compare exact accept/reject outputs and documented tolerances.
- Test forged event streams and coordinated rehashing. A self-contained SHA-256 implementation does not certify FIPS compliance by itself.
- Measure p50/p95 latency over controlled trace lengths and hardware; a single sub-2ms claim is insufficient without configuration details.

## Native C++ simulation

- Provide fixed compiler flags, container/CPU architecture, FPU rounding semantics, integration step and fixed seed, with cross-host determinism tests.
- Mechanical work `integral(tau*omega dt)` is signed and can be negative: distinguish positive mechanical input, regeneration and electrical input; do not label a signed sum as battery energy consumed.
- Compare contact mechanics/constraint behavior to independently instrumented MuJoCo/Isaac runs; CAD mesh visual agreement does not prove mass/inertia/contact equivalence.

## Go orchestration

- Verify deterministic seed assignment, exactly-once result IDs, scenario digest checks, cancellation/retry semantics, exception safety, worker process isolation and paired scene-level analysis.
- Distinguish worker count from independent environmental sample size.

## ROS 2 and physical hardware

- Verify the actual ROSMASTER bill of materials and calibration: Jetson variant, RPLIDAR model and RGB-D unit differ across revisions. Do not infer hardware from a generic profile.
- Verify `/emergency_stop` wired to independent motor power cutoff; ROS message delivery alone does NOT prove a hard E-stop.
- Treat 50 ms stop-latency and 0.40 m/s/1.0 rad/s limits as **proposed acceptance thresholds**, not observed data, until tested with external instrumentation.
- Fault-recovery backoff motion must not occur in a blind or obstacle-uncertain state without an independent safety supervisor.

## Scientific split

The 17 constructed fixtures are public smoke tests. A confirmatory study requires independently authored hidden scenes, preregistration, external monitor/witness ground truth and blinded reviewers. Never combine 43 historical tests, 11 v0.4 tests and the user-reported 93 into a single verified test claim without rerunning the combined codebase.
