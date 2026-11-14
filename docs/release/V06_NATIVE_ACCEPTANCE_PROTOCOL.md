# VEAB v0.6 — native-engine execution and calibration acceptance protocol

**Status: IMPLEMENTATION CANDIDATE. Native Isaac Lab and MuJoCo results not available in the current runtime.**

## Contract and execution model

1. Canonical bounded scenario → `veab-scene/2` with one frozen digest.
2. Scenario → `veab-control-tape/1` with ENU (x east, y north, z up), seconds, velocities in m/s, yaw rate rad/s, sample step, seed, controller identity, geometry and scenario hashes.
3. Both physics implementations consume the **same** open-loop control tape. Do not present independently generated closed-loop trajectories as a matched-physics experiment.
4. Capture actual physics engine root-state, contact, timing, model version, robot mass/inertia/damping/friction and asset hashes. Missing contact observations remain `null` (not zero).
5. The agent-independent monitor checks tape and geometry, and a separately implemented monitor must reconstruct reference outcomes before scientific validation.
6. Reports explicitly distinguish integrity, source provenance, physical calibration, and observational ground truth.

## What this patch actually executes

- `scripts/veab_v06.py tape` creates a frozen command sequence, and its schema and checksum are tested offline.
- `scripts/veab_v06.py run-mujoco` requests **native** `mujoco.MjModel` and `mj_step` execution. If missing, it exits with a nonzero code and states why. No toy-world fallback is permitted.
- `IsaacLabTapeCollector` accepts observations **only** from an externally stepped Isaac Lab environment. It cannot launch Isaac Lab, create an articulation, or claim a native run. Use a dedicated native Isaac Lab runner to produce the observations and record its build/physics backend.
- `scripts/veab_v06.py compare` requires matching tape, source scenario and timestamp grid. It reports discrepancies but always sets `eligible_for_physics_equivalence_claim=false` until calibration and independent evidence are separately reviewed.

## Offline reproduction

```bash
python -m pip install -e '.[test]' trimesh numpy
python -m pytest -q tests/test_locked_replay_v06.py tests/test_claims_v06.py
python scripts/veab_v06.py tape --scenario warehouse-transfer --steps 24 --seed 17 --out artifacts/v06/control-tape.json
python scripts/check_claims.py
```

## Native MuJoCo machine

```bash
python -m pip install -e '.[test]' trimesh numpy mujoco
python -m pytest -q tests/test_native_mujoco_v06.py
python scripts/veab_v06.py run-mujoco --tape artifacts/v06/control-tape.json --out artifacts/v06/mujoco
python scripts/veab_v06.py verify --tape artifacts/v06/control-tape.json --trace artifacts/v06/mujoco/native-locked-replay.json
```

Record exact installed MuJoCo, CPU, OS, `pip freeze`, model XML SHA and command tape digest with every run. Do not silently change physics options between engines. An uncalibrated planar research surrogate is not a vendor robot digital twin.

## Native Isaac Lab workstation (outstanding integration ticket)

- Pin Isaac Sim and Isaac Lab commits/versions, CUDA driver and physics backend.
- Import canonical OpenUSD for geometry and author an actual physics-enabled articulation. Visual-only `usda` is not a native-ready physics robot.
- Map control-tape ENU references to the same calibrated actuator controller as MuJoCo; document any mapping that cannot be equivalent.
- After **each actual native physics step**, pass root world position, XYZW quaternion, linear velocity, angular velocity, time and contact count to `IsaacLabTapeCollector.append_state`.
- Convert WXYZ quaternions explicitly if the installed API uses that convention. Do not guess.
- Export the native trace; independently verify the tape match and compare against a corresponding MuJoCo trace.
- Preserve unsuccessful runs, non-deterministic drift and contact discrepancies.

Check API compatibility against the pinned version; upstream documentation evolves and a stable import path cannot be assumed.

## Calibration conditions before meaningful sim-to-sim comparison

- Robot inertial mass, CoM, joint damping, actuation limits and friction independently measured or documented.
- Ground/obstacle materials and contacts matched at a declared abstraction level.
- World frames, initial pose, robot radius, integration step and sample clock matched.
- Input tape identical and no closed-loop controller recomputation between engines.
- Contact events independently derived from native physics, not fabricated from toy geometry.
- Independent scene authoring; >=20 held-out matched runs over >=2 task families for release evidence.

### Explicit failure modes

- Scene hash mismatch; tape mutation; dropped sample; command mismatch; timestamp drift; incomplete contact channels; uncalibrated models; hardware-stamp confusion; inconsistent quaternion ordering; native engine absent; empty external truth. All are blocked or disclosed, never silently upgraded into success.

## Required report fields

Engine/commit/build, model SHA, tape SHA, task and seed, sim time, trace root, contact missingness, RMSE/p90/max error, environment constraints, cost/latency, data provenance, limitations, external reviewer approval and decision against predeclared thresholds. Software checks alone cannot justify a `validated` label.
