# VEAP Studio R0.3 — First-Party Physical AI Engineering Workbench

**Local integrated research-pilot software. No third-party visualisation application, extension, or hosted data platform required.**

VEAP is a **Verifiable Embodied Agent Platform**. This Studio integrates a first-party robotics workspace for artifact ingest, model/scene inspection, synthetic and recorded replay, contract checks, counterfactual perturbations, provenance, native simulator jobs, cross-physics discrepancies, and derived robotics-learning data.

## Install (Ubuntu workstation)

```bash
cd VEAP_Studio
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,geometry,mcap]'
python -m pytest -q
export VEAP_STUDIO_DATA="$HOME/veap-studio-data"
export VEAP_MUJOCO_PYTHON="$HOME/veap-envs/mujoco/bin/python"
export VEAP_ISAAC_PYTHON="$HOME/miniforge3/envs/isaac/bin/python"
# Optional: different Python environments for expensive ML / USD tools
# export VEAP_LEROBOT_PYTHON="$HOME/veap-envs/lerobot/bin/python"
# export VEAP_USD_PYTHON="$HOME/miniforge3/envs/isaac/bin/python"
python -m uvicorn veap_studio.api:app --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765>. R0.3 uses an original dark green engineering console with docked evidence streams, interactive scene views, playback, world inspection, reporting, and **Engine Runtime & Jobs**.

**Do not install LeRobot inside the existing Isaac or MuJoCo environments without compatibility testing.** Run in a separate environment. The same applies to USD and Gazebo native dependencies.

## Native workbench

The Runtime Workbench probes **the server's local configured Python interpreters** and reports a truthful runtime status. Runtime detection is not evidence of a successful physics run.

- **MuJoCo:** user-clicked `mujoco_fall` invokes a standalone `mj_step` worker in the configured runtime, storing a true native simulated trajectory, contact existence and solver metadata. Not a calibrated robot or digital twin.
- **Isaac Sim + Isaac Lab 2.3.x:** user-clicked `isaac_fall` invokes native `AppLauncher`, PhysX and a rigid sphere. Requires an existing Isaac Python 3.11 setup; headless GPU launch may take substantial time. Not run during this package's container tests.
- **Physics comparison:** only completed native Isaac and MuJoCo jobs may be compared. Includes 3D position RMSE, p90, max deviation and contact-comparability disclosure. Does not validate sim-to-real.
- **Gazebo:** export a bounded SDF reference scene. CLI may be detected; no Gazebo execution is claimed until instrumented native tests are collected.
- **World export:** an original reference world is emitted as textual OpenUSD, MJCF and SDF, with hashes and explicitly uncalibrated robot geometry. The native USD parser and native Gazebo physics are not executed in the base package.
- **MCAP:** source bytes are preserved. An optional `mcap-ros2-support` decoder extracts ROS 2 odometry and **only recorded** `/cmd_vel` actions from compatible profiles, retaining source lineage. No ROS message publishing.
- **LeRobot:** optional external Python runtime creates an offline local dataset **only when complete recorded state/action vectors and adequate sample rates are available**; refuses to fabricate actions from odometry. Never uploads automatically to Hugging Face.
- **ROS 2 recording:** `scripts/veap_record_ros2.sh --check` and `--record` are bounded first-party read-only capture commands, requiring active sensor topics and MCAP plugin. Not run by browser or on the unqualified Yahboom.
- **Large evidence:** place original files in `$VEAP_INBOX` (default `$VEAP_STUDIO_DATA/inbox`), then use *Data Registry → Scan local recording inbox* for explicit import. Source files are copied into the local vault only if at least 10 GiB storage headroom remains.

## Status of this build

| Component | Software presence | Native validation |
|---|---|---|
| Original VEAP browser replay, media/geometry previews, contracts and analytical faults | Implemented, regression tested | Synthetic-demo evaluation only |
| Bounded upload, local staged ingest, source SHA-256 | Implemented, regression tested | Source authenticity not established |
| MuJoCo 3D native worker | Code implemented | Requires execution on configured MuJoCo host |
| Isaac Lab 2.3.x native worker | Code implemented | Requires execution on RTX workstation |
| Native cross-engine comparison | Code implemented, synthetic fixture tested | Actual matched physics traces pending |
| ROS 2 MCAP decoder | Code implemented, mock-tested | Real MCAP profile testing pending |
| OpenUSD / MJCF / SDF reference export | Implemented, XML parsed and bytes hashed | USD parser / dynamics equivalence pending |
| LeRobotDataset exporter | Code implemented | Integration with installed LeRobot pending |
| Gazebo native simulation | SDF export only | Not connected |
| Photorealistic RTX/Unreal-quality engine | First-party projected viewport | Hardware-accelerated renderer not built |
| Physical M3 Pro | Historical sensor validation available separately | Current filesystem and sensor qualification hold |

No direct robot-control endpoint, hosted identity, enterprise HA, physical safety certification or scientifically established SOTA is claimed.

## Experiment and asset API

- `GET /api/health`, `/api/integrations`, `/api/assets`, `/api/inbox`, `/api/jobs`
- `POST /api/jobs` with `{"kind":"scene_export"}` or `{"kind":"mujoco_fall"}` or `{"kind":"isaac_fall"}`
- `POST /api/jobs` with `{"kind":"mcap_decode","source_id":"..."}` or `{"kind":"lerobot_dataset","source_id":"..."}`
- `GET /api/jobs/{id}`, `/api/jobs/{id}/artifact/veap_reference.usda`, and corresponding `.xml` / `.sdf` / `manifest.json`
- `POST /api/physics/compare` with a completed Isaac and MuJoCo job ID
- `POST /api/inbox/import` with an exact staged filename
- Existing trace, counterfactual, geometry and assurance endpoints remain available.

See `docs/RUNTIME_CONFIG.md`, `docs/ENGINE_ACCEPTANCE.md`, `docs/CLAIMS_POLICY.md`, and `docs/SECURITY_AND_EVIDENCE.md`.

## Deployment and security

This is a **single-user, localhost-only research pilot**. `VEAP_STUDIO_TOKEN` optionally restricts API access, but it is **not** OIDC or multi-tenant IAM. Do not expose port 8765 on an untrusted network. The jobs executor is a single worker process runner, not an isolated production orchestrator. Review source licenses, robot risks and third-party model/data rights before commercial deployment.

All original recordings and derived artifacts are separated by storage identifiers and source hashes. The evidence ledger alone does not prove truthful sensor capture.

## First-party contract authoring and agent-independent monitoring

The Assurance view now supports a **versioned 2D recorded-trajectory contract**. Register a contract from the JSON editor, select a trajectory, then click *Run separate-process monitor*. The monitor is implemented under `external_monitor/contract_monitor.py` using only the Python standard library and no VEAP simulator/verifier imports. It checks goal, keep-out segment crossings, finite-difference overspeed, missing command evidence, timestamp gaps and reported sensor faults.

Every result states `source_authenticity=NOT_ESTABLISHED` and `physical_safety=NOT_ESTABLISHED`. Contract calibration is user-declared, not independently verified. Recording success is not robot safety certification.

The earlier R0.2 fixed warehouse contract is **not automatically applied to uploaded or native traces**. Imported physical/simulator recordings show `NO_MATCHING_CONTRACT` until explicitly evaluated. Synthetic warehouse examples remain demonstration-only.
