# VEAP v0.6 — native-engine execution and calibration acceptance protocol

**Status: PILOT DIAGNOSTIC COMPLETED (`0.20182817 m` RMSE localized); 20-tape / 40-trace held-out confirmatory campaign pending model calibration and contact instrumentation.**

## Contract and execution model

1. Canonical bounded scenario → `veab-scene/2` with one frozen digest.
2. Scenario → `veab-control-tape/1` with ENU (x east, y north, z up), seconds, velocities in m/s, yaw rate rad/s, sample step, seed, controller identity, geometry and scenario hashes.
3. Both physics implementations consume the **same** open-loop control tape. Do not present independently generated closed-loop trajectories as a matched-physics experiment.
4. Capture actual physics engine root-state, contact, timing, model version, robot mass/inertia/damping/friction and asset hashes. Missing contact observations remain `null` (not zero).
5. The agent-independent monitor checks tape and geometry, and a separately implemented monitor must reconstruct reference outcomes before scientific validation.
6. Reports explicitly distinguish integrity, source provenance, physical calibration, and observational ground truth.

## What the CLI executes (`scripts/veap_v06.py`)

- `python scripts/veap_v06.py tape` creates a frozen command sequence, and its schema and checksum are tested offline.
- `python scripts/veap_v06.py run-mujoco` requests **native** `mujoco.MjModel` and `mj_step` execution. If missing, it exits with a nonzero code and states why. No toy-world fallback is permitted.
- `IsaacLabTapeCollector` accepts observations **only** from an externally stepped Isaac Lab environment. It cannot launch Isaac Lab, create an articulation, or claim a native run. Use a dedicated native Isaac Lab runner to produce the observations and record its build/physics backend.
- `python scripts/veap_v06.py compare` requires matching tape, source scenario and timestamp grid. It reports discrepancies (`veab-locked-physics-comparison/1`) and always sets `eligible_for_physics_equivalence_claim=false` until calibration and independent evidence are separately reviewed.
- `python scripts/veap_v06.py diagnose` produces a per-tick cross-engine comparison (`veap-paired-physics-diagnostic/1`) localizing initial pose/velocity offsets, first planar and 3D divergence ticks, target-exceedance tick, peak position error, planar motion stalls under active commands, contact-channel completeness, and run-to-run repeatability when rerun traces (`--repeat-left` / `--repeat-right`) are supplied.

## Offline reproduction & pilot diagnostic

```bash
python -m pip install -e '.[test]' trimesh numpy
python -m pytest -q tests/test_locked_replay_v06.py tests/test_claims_v06.py
python scripts/veap_v06.py tape --scenario warehouse-transfer --steps 24 --seed 17 --out artifacts/v06/control-tape.json
python scripts/veap_v06.py diagnose \
  --tape artifacts/research/v06-control-tape.json \
  --left artifacts/research/v06-mujoco-locked-replay.json \
  --right artifacts/research/v06-isaaclab-locked-replay.json \
  --out artifacts/research/v06-pilot-per-tick-diagnostic.json
python scripts/check_claims.py
```

## Native MuJoCo machine

```bash
python -m pip install -e '.[test]' trimesh numpy mujoco
python -m pytest -q tests/test_native_mujoco_v06.py
python scripts/veap_v06.py run-mujoco --tape artifacts/research/v06-control-tape.json --out artifacts/v06/mujoco
python scripts/veap_v06.py verify --tape artifacts/research/v06-control-tape.json --trace artifacts/v06/mujoco/native-locked-replay.json
```

Record exact installed MuJoCo, CPU, OS, `pip freeze`, model XML SHA and command tape digest with every run. Do not silently change physics options between engines. An uncalibrated planar research surrogate is not a vendor robot digital twin.

## Workstation Pilot Localization (`warehouse-transfer`, tape `ba0d2388...`)

On the RTX 4080 SUPER workstation (`MuJoCo 4.0.1` vs `isaacsim-5.1.0.0/isaaclab-0.54.3`), rerunning `artifacts/research/v06-control-tape.json` reproduces both engine trajectories deterministically (`0.0 m` run-to-run drift, identical `sample_chain_sha256` in both engines) and localizes the `0.20182817 m` position RMSE (`artifacts/research/v06-pilot-per-tick-diagnostic.json`):

1. **Tick 0 (`t = 0.0 s`) initial vertical divergence (`0.0028649 m`, `0.1903532 m/s`):**
   - MuJoCo (`warehouse-transfer.xml`) constrains `veab_scout` (`height_m = 0.32`, half-height `0.16 m`) to planar joints (`planar_x`, `planar_y`, `planar_yaw`) at fixed `z = 0.16 m` with `vz = 0.0 m/s`.
   - The pilot Isaac Lab runner spawned an unconstrained 6-DOF cylinder with `height = 0.27 m` (half-height `0.135 m`) at `z = 0.16 m` (`0.025 m` above the ground collider) and stepped PhysX during `sim.reset()` before sampling tick 0, recording `z = 0.1571351 m` and `vz = -0.1903532 m/s`.
2. **Tick 1 (`t = 0.2 s`) airborne planar motion vs Tick 2 (`t = 0.4 s`) ground contact:**
   - At tick 1 while still airborne (`z = 0.137906 m`), Isaac Lab accelerated to `x = 1.208368 m` (`vx = 0.069449 m/s`), within `0.000431 m` horizontally of MuJoCo (`x = 1.208799 m`, `vx = 0.083513 m/s`).
   - At tick 2, the Isaac Lab cylinder landed on the ground plane at `z = 0.135 m` (`0.0195783 m` planar error, `0.031754 m` 3D error).
3. **Ticks 2–18 (`t = 0.4 s` to `3.6 s`) planar stiction stall in Isaac Lab vs viscous joint slide in MuJoCo:**
   - Once resting on the ground plane at `z = 0.135 m`, the pilot Isaac Lab runner's per-substep velocity write (`+0.0055 m/s` per `0.01 s` substep from `0 m/s`) fell below the single-step PhysX Coulomb static friction impulse on the `8.0 kg` free body, stalling horizontal motion (`|v_xy| < 0.005 m/s`) on **17 of 18** commanded motion ticks (`ticks 2..18`, position stuck at `[1.210722, 1.3, 0.135]`).
   - MuJoCo's constrained planar slide joints (`damping = 2.0`, zero floor contact `ncon = 0`) continued tracking the `+x`, `+y`, and `-x` velocity phases, crossing the `0.100 m` threshold at **tick 5** (`0.11704287 m`) and reaching peak divergence at **tick 13** (`0.27508361 m`).
4. **Contact channel missingness (`0 / 25` comparable samples):**
   - MuJoCo recorded `contacts = 0` on all 25 samples, while the pilot Isaac Lab runner passed `contacts = null` (`missing_right = 25`), leaving `contacts_comparable = false`.

## Native Isaac Lab workstation requirements before the 40-trace campaign

- Pin Isaac Sim and Isaac Lab commits/versions, CUDA driver and physics backend.
- Match the canonical `veab-scene/2` cylinder height (`0.32 m`, half-height `0.16 m`), initial pose (`z = 0.16 m` with zero pre-reset drop), and planar actuation/friction model between MuJoCo and Isaac Lab.
- Instrument native contact observations in both engines so zero-contact (`0`), active-contact (`>0`), and missing (`null`) states are explicitly distinguished.
- After **each actual native physics step**, pass root world position, XYZW quaternion (converted explicitly from WXYZ), linear velocity, angular velocity, time and contact count to `IsaacLabTapeCollector.append_state`.
- Freeze the evaluation manifest (position, timing, and contact thresholds, model/scene/tape hashes, and held-out split) before executing the >=20 held-out matched tapes (>=40 native traces across >=2 independently authored task families).
- Preserve the original `0.20182817 m` (`~0.202 m`) pilot baseline and every unsuccessful run, non-deterministic drift, and contact discrepancy.

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
