# VEAB — Verifiable Embodied Agent Benchmark

**VEAB v0.4 — assurance-controls integration: internal validation only; no external, embodied, or deployment validation claimed.**

```
Status: INTERNAL ENGINEERING VALIDATION ONLY
Implemented:
- 17-episode synthetic assurance fixtures
- External monitor with no VEAB simulator/verifier imports
- Comparator runner
- Adjudication template generator
- Scene power-calculation utility
- 12 new assurance-control tests
- Documentation, prospective protocol, and native-backend integration guide
Not established:
- Calibrated detection performance
- External or blinded adjudication
- Isaac Lab, MuJoCo, Gazebo, ROS 2/MCAP, or physical-robot validation
- Physical safety, certification, trusted provenance, or SOTA performance
- Production SLA or enterprise readiness
```

An executable **evidence-first benchmarking platform**: deterministic toy-world tasks; distinct baseline planners, control gates, and trace verifier; auditable trajectories; split-labelled scenarios; a live isometric 3D-projection dashboard; and a reproducible ablation CLI.

> **Core Definition:** VEAB is a **model- and harness-agnostic evaluation protocol** that jointly measures **task success**, **constraint violations**, **recovery**, **resource cost**, and **independently checkable evidence** under **controlled faults**.

> **Important boundaries:** VEAB v0.1 executes a simplified **2-D kinematic toy simulator**, displayed with a 3-D isometric renderer. It is **not** a real robot control system, Isaac Lab integration, physically validated simulator, formal CBF, enterprise-certified deployment, or demonstrated SOTA result. Default mode does not issue robot commands or access cloud services.

## Canonical Research Narrative: From Apparent Success to Verifiable Autonomy

VEAB tests the value of process-level verification through empirical evidence rather than narrative dramatization. The central perspective is that of a **robotics validation engineer** deciding whether an autonomous agent is safe to deploy.

The core narrative anchor is drawn directly from the bundled 60-trial factorial evaluation (5 scenarios × 3 seeds × 2 policies × 2 safety gate settings):

| Configuration | Task completion | Verified completion | Safety violations |
|---|---|---|---|
| **Greedy, gate off** | 12/15 | 3/15 | 147 |
| **Greedy, gate on** | 12/15 | 12/15 | 0 |
| **Route, gate off** | 15/15 | 15/15 | 0 |
| **Route, gate on** | 15/15 | 15/15 | 0 |

> **Key Finding:** **Nine of fifteen ungated greedy trials reached their task objectives but were rejected by the independent verifier because they violated safety constraints.**

For example, in `warehouse-transfer` (seed 0), the unshielded greedy planner reaches the goal coordinates with 22 geometric violations in 68 steps (a conventional evaluator scores this as 100% success). With the geometric gate enabled, the planner finishes with 22 safety interventions, 0 violations, and 83 steps.

For the complete nine-stage development narrative, see [docs/CANONICAL_NARRATIVE.md](docs/CANONICAL_NARRATIVE.md).

> **Formal Research Hypothesis:** Under matched scenarios, seeds, and fault conditions, an evaluation architecture that jointly scores task completion, constraint violations, recovery behaviour, resource use, and trace-verifiable execution will identify reliability differences between agents that are not detectable using final task-success rate alone.

### Proposed Research Acceptance Gates

*These are proposed acceptance gates from the research programme, not completed milestones:*

| Research Gate | Proposed Measurable Acceptance Criterion | Target Metric | Status |
|---|---|---|---|
| **Verifier hardening** | At least 30 preregistered adversarial fixtures; 100% detection of the defined integrity-tampering cases | Tamper detection recall $= 1.0$ | Active milestone deliverable |
| **Reproducibility** | Identical trace digests across repeated deterministic executions with the same pinned environment | 0 digest drift | Open research gate |
| **Incremental diagnostic value** | Quantify additional true failures detected versus outcome-only evaluation, with false-positive rates | $\Delta \text{True Failure Rate} > 0$; $\text{FPR} = 0$ | Active milestone deliverable |
| **Isaac Lab integration** | At least 20 replayable scenarios across two task families | Replay agreement | Active milestone deliverable (contract) |
| **Baseline comparisons** | At least two external agents evaluated under matched observations and compute budgets | Standardized benchmark delta | Open research gate |
| **Physical evidence** | At least 30 supervised trajectories with independently checked provenance, latency and safety observations | Hardware safety rate | Open research gate |

### Next Milestone: Scientific Validation Release
Treat the next development release as a scientific validation milestone: independent ground-truth fixtures, adversarial verifier tests, diagnostic value quantification, and an Isaac Lab integration contract. Those deliverables advance VEAB towards a defensible research contribution rather than narrative iteration alone.

## Strategic Focus: Autonomous & Embodied AI Engineering

The VEAB project focuses exclusively on **autonomous and embodied AI engineering**, structured across seven technical pillars:

- **Simulation:** NVIDIA Isaac Lab, Isaac Sim, MuJoCo, Gazebo and Unreal Engine–quality 3D environments.
- **Robotics:** ROS 2, robot control, navigation, manipulation and hardware-in-the-loop (HIL) testing.
- **3D engineering:** CAD, OpenUSD, URDF, MJCF, SDF, digital twins and physically realistic environments.
- **Agent intelligence:** VLA/VLM models, world models, multi-agent orchestration and adaptive planning.
- **Safety and verification:** Independent verification, runtime assurance, fault injection and reproducible evidence.
- **SOTA benchmarking:** Cross-simulator evaluation, sim-to-real transfer, safety, reliability, latency and resource efficiency.
- **Enterprise infrastructure:** Cloud deployment, experiment orchestration, observability, security and evidence provenance.

## Quick start — Linux, macOS or Windows with Python 3.10+

```bash
cd veab-platform
python -m venv .venv
source .venv/bin/activate             # Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[test]'
python -m pytest -q
python -m uvicorn veab.api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Select a task, choose a baseline, enable/disable the geometric safety gate, and run the benchmark. Click a ledger row to inspect a specific run. Downloaded evidence JSON is independently verifiable.

No JavaScript dependencies, package manager, GPU, robot, network connection or model API key are needed for the UI/benchmark once the Python dependencies have been installed.

![VEAB research operations dashboard](docs/dashboard-after-run.png)

## What is implemented

| Capability | Version 0.1.0 status | Evidence/interpretation |
|---|---|---|
| 5 scenario contracts across train / validation / test | Implemented | Public **demonstration splits**, not contamination-controlled held-outs |
| Greedy and 8-neighbour A* route baseline | Implemented | Deterministic, explicit action proposals |
| Speed limits and optional geometric safety gate | Implemented | Clamping, redirection, emergency hold; **not** formal control barrier proof |
| Faults | Implemented | Sensor dropout, actuator stall, perception noise |
| Negative-target abstention | Implemented | Requires 3 valid negative observations; false completion not rewarded |
| Trace events and SHA-256-linked ledger | Implemented | State, observation, proposal, intervention, fault, milestone, terminal |
| Independent trace checker | Implemented | Geometry, dynamics, postconditions, event sequence, scenario digest |
| Optional manifest HMAC | Implemented | Must custody key outside benchmark data; hash alone is not authenticity |
| Live API, persistent JSON evidence, SQLite run index | Implemented | Local single-host, bounded worker pool |
| Browser 3-D projected scene and trajectory replay | Implemented | Visual extrusion of 2-D geometry, NOT Isaac Sim rendering |
| Read-only JSONL telemetry ingest | Implemented | **Unattested** external input never earns verified status |
| Multi-seed policy/shield factorial ablations | Implemented | Descriptive metric summaries and small-sample paired bootstrap |
| OpenRouter expert review | Optional | Advisory only, never evaluated as independent ground truth |
| Isaac Lab / ROS 2 native integration | **Not implemented** | Requires genuine simulator/hardware adapters and sensor provenance |
| Real energy in Joules, token cost, motor current | **Not implemented** | Current field is a dimensioned motion-energy *proxy* |
| Production tenant IAM, Kubernetes/HA, hardware safety certification | **Not implemented** | Not safe for exposed internet or autonomous hardware control |

## Command-line experiments

```bash
# Discover available tasks and frozen split labels
python -m veab scenarios

# Execute an auditable simulation trial with seed 17
python -m veab run --scenario warehouse-transfer --policy route --seed 17 --out artifacts/warehouse.json

# Re-check a standalone bundle, independently of the execution harness
python -m veab verify artifacts/warehouse.json

# Counterfactual ablation: remove safety gate from the greedy baseline
python -m veab run --scenario warehouse-transfer --policy greedy --no-shield --out artifacts/unsafe-baseline.json

# All 5 tasks × 3 seeds × 2 policies × 2 shield settings = 60 trials
python -m veab suite --seeds 0 1 2 --split all --out artifacts/suite-summary.json

# Read-only external telemetry import; provenance remains explicitly untrusted
python -m veab ingest --scenario campus-patrol --trace samples/trajectory.jsonl --out artifacts/external.json
```

**External telemetry JSONL schema:** one observation per line with keys `tick`, `x`, `y`, `vx`, `vy`; continuous ticks beginning at 0; coordinates in metres, velocities in m/s, and timestep fixed by the scenario. The importer verifies file structure and computes geometric postconditions but **will not** claim authenticated real-world success. See [docs/ADAPTER_CONTRACT.md](docs/ADAPTER_CONTRACT.md).

## Experimental controls

- **Task contract:** fixed, validated JSON schema; one SHA-256 digest of the full scenario record in each run manifest.
- **State and observations:** deterministic time step, seeded observation noise and injected faults; no runtime clock enters the hashed trace.
- **Process verification:** recomputed velocity consistency, obstacle/forbidden-zone intersection, checkpoint order, abstention evidence and constraint violations.
- **Ablations:** `policy ∈ {greedy, route}`, `shield ∈ {off, on}`; pair all settings over identical seed and scenario.
- **Integrity:** canonical JSON hash-linked event sequence; optional HMAC of the complete manifest (including event-chain root); no replay permits a self-reported terminal claim to substitute for checked postconditions.
- **Transparency:** deterministic route uses mapped obstacles. This is an information-rich baseline; it is not a learned visual-navigation policy.

See [docs/RESEARCH_PROTOCOL.md](docs/RESEARCH_PROTOCOL.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## Local REST API

`GET /api/health`, `GET /api/scenarios`, `POST /api/runs`, `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/bundle`. OpenAPI documentation at `/api/docs`.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id":"warehouse-transfer","policy":"route","seed":17,"shield":true}'
```

The job is queued and evaluated in a bounded worker pool. The dashboard polls the API to display in-progress trace records and verified outcomes. Records are persisted atomically to SQLite metadata and JSON bundles in `./artifacts` (change with `VEAB_DATA_DIR`).

### Security (development boundary)

The default API has **no authentication** and binds **only 127.0.0.1**. **Never bind it to 0.0.0.0 on an untrusted network** without authentication, TLS, network isolation, a reverse proxy and independent security review. You can set `VEAB_ADMIN_TOKEN` to enable one local bearer token. This is not a multi-user RBAC implementation. For signed bundles, set a strong `VEAB_ATTESTATION_KEY` in the isolated process environment; do not store keys in repository, evidence JSON or UI. If a key is not supplied during offline verification, a recorded signature cannot be independently validated.

A local-only Docker Compose example is provided. It maps `127.0.0.1:8000:8000`; moving it to a public interface is **not** a production readiness guarantee.

## Optional OpenRouter advisory review

```bash
export OPENROUTER_API_KEY='...'
export OPENROUTER_MODEL='provider/model-slug'
python -m veab expert-review --scenario warehouse-transfer --out artifacts/optional-expert.json
```

This sends the **public task JSON** to a third-party model provider. It is explicitly an **advisory critique**, not a benchmark decision, oracle, model baselining result, or verified scientific evidence. It is disabled by default; no background or automatic paid calls occur.

## Repository layout

```text
veab/                    Validated spec, planners, simulator, ledger, verifier,
                         ingest adapter, ablations, API, persistent store
veab/integrations/       Optional read-only external model analysis
scenarios/               Versioned public train / validation / test task contracts
web/                     Offline vanilla JS dashboard + isometric world renderer
artifacts/               Local evidence JSON and metadata (ignored by Git)
tests/                   Pytest specification, API, deterministic trace, attack tests
docs/                    Protocol, threat model, adapter contract, screenshots
Dockerfile               Non-root local container image
docker-compose.yml       Localhost-only deployment fixture
```

## Peer-reviewed foundations and implementation references

1. Zhou, S. et al. (2024). **WebArena: A Realistic Web Environment for Building Autonomous Agents.** ICLR 2024. https://proceedings.iclr.cc/paper_files/paper/2024/hash/4410c0711e9154a7a2d26f9b3816d1ef-Abstract-Conference.html
2. Zhu, Y. et al. (2025). **Establishing Best Practices in Building Rigorous Agentic Benchmarks.** NeurIPS 2025, Datasets and Benchmarks. DOI: **10.52202/085713-5547**. https://proceedings.neurips.cc/paper_files/paper/2025/hash/f316275b44ee2de533102913828a8107-Abstract-Datasets_and_Benchmarks_Track.html
3. Xie, T. et al. (2024). **OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments.** NeurIPS 2024. https://os-world.github.io/
4. Isaac Lab authors. Direct workflow environment documentation: https://isaac-sim.github.io/IsaacLab/develop/source/tutorials/03_envs/create_direct_rl_env.html
5. ROS 2 `rosbag2` reference and MCAP recording: https://github.com/ros2/rosbag2 and https://mcap.dev/guides/getting-started/ros-2
6. OpenRouter developer documentation: https://openrouter.ai/developers

**Validation status**: tested locally with `python -m pytest`; the suite does not establish predictive validity, independence of public test splits, or empirical SOTA performance. No hardware trial was executed.
