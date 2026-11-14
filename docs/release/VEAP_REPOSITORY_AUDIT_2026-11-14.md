# VEAP — live repository and scientific release audit

**Snapshot inspected:** `FAVL-AI/VEAP` `main@2d5d16cff552722ee9679d77146443ee71c0c99a` (2026-11-14 UTC).
**Audit type:** source/CI evidence review plus local unit tests of matching standalone research and Studio snapshots. **Not an independent safety or security assessment.**

## Findings

1. Repository rename from VEAB to VEAP is complete at the GitHub repository level. `FAVL-AI/VEAB` resolves to the same repository ID, `1454632734`.
2. The monorepo contains: `veap/` (core prototype), `veap/m3_replay/` (synthetic ROS evidence contract), `veap_evidence_r1_1/` (three-valued evidence research), and `veap_studio_r03/` (first-party UI/replay pilot). These are **different component maturity levels**, not a unified production release.
3. At inspected commit, GitHub Actions **core CI succeeded on Python 3.11, 3.12 and 3.13**. The Python 3.11 core CI log reported **137 passed, one warning**. The M3-specific job succeeded; its Python 3.11 log showed **44 passed**. These are overlapping suites: do not add 44 to 137.
4. Prior to the proposed new integrated workflow, `.github/workflows/ci.yml` ran `pytest` only under root `tests/`; it did **not** execute the standalone R1.1 or R0.3 Studio suites. Green CI did not establish those modules passed on GitHub.
5. `README.md` and root `pyproject.toml` still described the whole platform as v0.1.0 or a benchmark. Core package `veap-platform==0.1.0` is retained for compatibility, while the platform landing page should distinguish the R1.1 and R0.3 components.
6. There are no published GitHub Releases in the inspected repository. The `veap_evidence_r1_1` and `veap_studio_r03` directories are committed source trees, not signed/qualified releases.
7. The committed R1.1 experiment reports 96 correlated synthetic cases; VEAP and a strong separate reachability monitor both match all 96 author labels. It reports NO external holdout, NO physical measurements, and NO upstream EAI/ABC experiment reproduction.
8. The M3 validation register identifies EXT4 checksum faults and unresolved physical-sensor qualification. A [dated addendum](../m3/YAHBOOM_STATUS_ADDENDUM_2026-11-14.md) preserves the subsequently reported STOR-01 and STOR-02 backup results while maintaining the physical-sensor hold. New physical robot recording remains on hold until Jetson storage recovery and a supervised safety plan.
9. First-party Studio includes native worker entry points but has no demonstrated native Isaac Lab/MuJoCo/Gazebo acceptance from the audited repository. Software API coverage is not physics calibration.
10. The original root `veap/adapters/isaac_lab.py` generator still emits legacy `omni.isaac.lab.*` imports; the Studio worker uses the v2.3-style `isaaclab.*` API. Native interoperability requires explicit versioned execution tests rather than assuming both adapters work.
11. The root `veap/adapters/mujoco.py` labels `abs(torque_x * vx) + abs(torque_y * vy)` integrated over time as mechanical energy in joules. Unless those values are correctly defined as generalized **linear forces** for translational joints, the term is dimensionally inconsistent with torque–angular-velocity power. Audit actuator effort units, signs and physical meaning before publishing energy metrics.
12. GitHub connection has read-only (`pull`) permissions, no `push` or `admin`; no files were published through the connector.

## Local software regressions executed during the audit

| Suite | Local result | What this proves |
|---|---:|---|
| Evidence R1.1 original | 63/63 | Recovered matching source passes tests in audit environment |
| Evidence R1.1 with R1.2 assumptions | 70/70 | New assumption-envelope software regressions pass |
| Studio R0.3 | 42/42 | Recovered matching Studio source passes software tests |
| R1.1 stress regeneration | Byte-for-byte match | Original 96-case JSON output is deterministic in inspected environment |
| R1.2 assumptions | 180 synthetic variants, zero monitor/checker/monotonicity failures | Internal implementation control only, **not** 180 independent scenes |

Snapshot source hashes for selected R1.1/Studio files were checked against the live GitHub blob SHA to establish alignment of the recovered local packages. Native simulator runs and physical M3 telemetry were not executed in this audit environment.

## Ordered release gates

| Gate | Required acceptance evidence | State at audit |
|---|---|---|
| RG-0 | Green root, R1.1, Studio and M3 CI suites on same commit | Core/M3 green; integrated gate **not yet published** |
| RG-1 | Corrected landing-page claims and component-version matrix | Proposed patch only |
| RG-2 | Reproduce upstream EAI eight evaluation cells and ABC published flaw cases, recording differences | Not run |
| RG-3 | Independently authored and held-out robotic evidence with blinded adjudication | Not run |
| RG-4 | Strong runtime-verifier/human/script comparator, predeclared endpoints and power | Not run |
| RG-5 | Native Isaac+MuJoCo controls with measured and documented contact/clock/calibration | Not run for the integrated release |
| RG-6 | M3 ROS 2/MCAP capture after storage, sensors and safety gates | Blocked |
| RG-7 | External security, data controls, pilot acceptance, restoration and support gates | Not run |

**Permitted public claim:** VEAP provides software-tested research components for evidence-sufficient robot-execution evaluation, an M3 recording-contract prototype, and an early first-party Studio. **Not claimed:** independent physical validation, superior SOTA performance, trusted sensor provenance, safety certification or production qualification.
