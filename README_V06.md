# VEAP v0.6 — Locked Cross-Engine Replay & Native Physics Acceptance

**Status:** Stages 1–4 executed locally on RTX 4080 SUPER (`MuJoCo 4.0.1` + `Isaac Lab 0.54.3 / Isaac Sim 5.1.0.0`); software and artifact verification passing in CI.  
**Claim boundary:** `eligible_for_physics_equivalence_claim = false`, `independently_attested_ground_truth = false`. All 40 held-out traces simulate an uncalibrated planar research surrogate (`z = 0.16 m`, `mass = 8.0 kg`, `simulator_reported_unattested` provenance).

---

## Verified Capabilities & Evidence Artifacts

| Stage | Deliverable | Artifact / Module | Key Result |
|---|---|---|---|
| **Stage 1 — Pilot Localization** | Per-tick divergence diagnostic & deterministic workstation repeatability | [`artifacts/research/v06-pilot-per-tick-diagnostic.json`](artifacts/research/v06-pilot-per-tick-diagnostic.json) | `0.20182817 m` pilot RMSE repeats with `0.0 m` drift; localized to tick-0 gravity drop + PhysX Coulomb static-friction stall (`ticks 2–18`) and `25/25` missing right contacts |
| **Stage 2 — Model Alignment & Contacts** | Aligned Isaac Lab runner (`ENU_z_up_m`, `WXYZ → XYZW`, `s⁻¹` damping, `ContactSensor`) | [`veap/simulation/isaaclab_native_runner.py`](veap/simulation/isaaclab_native_runner.py), [`artifacts/research/v06-stage2-contact-verification.json`](artifacts/research/v06-stage2-contact-verification.json) | Distinguishes observed zero contact (`0`), observed contact (`> 0`), and missing observation (`null`, never coerced to `0`) |
| **Stage 3 — Frozen Evaluation** | Versioned manifest preserving pilot baseline & freezing 20 `test`-split tapes | [`artifacts/research/v06-evaluation-manifest.json`](artifacts/research/v06-evaluation-manifest.json) | `manifest_sha256: 31bee016b771f47379fd3cb800251fddc737f4b58a652452bbbd1565528cc25d`; `max_position_rmse_m <= 0.100 m` retained |
| **Stage 4 — 40-Trace Release Gate** | 20 held-out paired runs (40 native traces) across 3 `test`-split task families + independent audit | [`artifacts/research/v06-release-gate-report.json`](artifacts/research/v06-release-gate-report.json), [`artifacts/research/v06-heldout-traces/`](artifacts/research/v06-heldout-traces/) | `mean_rmse = 0.0135539 m`, `max_rmse = 0.06157238 m`, `timegrid_err = 0.0 s`, `missing_contacts = 0`; `18/20` passed (`insp-07`, `insp-08` failed at `0.0769` contact-state disagreement due to 1-tick PhysX contact-offset lead) |

---

## Reproducible CLI Workflow

```bash
python -m pip install -e '.[test]' trimesh numpy
python -m pytest -q tests/test_locked_replay_v06.py tests/test_claims_v06.py
python scripts/check_claims.py

# 1. Generate or inspect a frozen control tape (does not step native physics)
python scripts/veap_v06.py tape --scenario warehouse-transfer --steps 24 --out artifacts/v06/control-tape.json

# 2. Step native MuJoCo (fails if mujoco is unavailable; no toy fallback)
python scripts/veap_v06.py run-mujoco --tape artifacts/v06/control-tape.json --out artifacts/v06/mujoco

# 3. Run Stage 1 per-tick divergence diagnostic on paired native traces
python scripts/veap_v06.py diagnose \
  --tape artifacts/research/v06-control-tape.json \
  --left artifacts/research/v06-mujoco-locked-replay.json \
  --right artifacts/research/v06-isaaclab-locked-replay.json \
  --out artifacts/research/v06-pilot-per-tick-diagnostic.json

# 4. Freeze Stage 3 evaluation manifest (criteria, asset hashes, 20 held-out tapes)
python scripts/veap_v06.py freeze-manifest --out artifacts/research/v06-evaluation-manifest.json

# 5. Evaluate Stage 4 40-trace release gate
python scripts/veap_v06.py evaluate-gate \
  --manifest artifacts/research/v06-evaluation-manifest.json \
  --traces-dir artifacts/research/v06-heldout-traces \
  --out artifacts/research/v06-release-gate-report.json
```

For science and release gates see [`docs/release/V06_NATIVE_ACCEPTANCE_PROTOCOL.md`](docs/release/V06_NATIVE_ACCEPTANCE_PROTOCOL.md), [`docs/release/VEAP_RELEASE_TRAIN_v0.6_to_v1.0.md`](docs/release/VEAP_RELEASE_TRAIN_v0.6_to_v1.0.md), and [`docs/CLAIMS_POLICY.md`](docs/CLAIMS_POLICY.md).
