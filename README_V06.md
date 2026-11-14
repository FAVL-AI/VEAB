# VEAB v0.6 — locked cross-engine replay (engineering candidate)

**This is an additive candidate, not an accepted native-simulation release.** Built against the locally available VEAB v0.5 Studio snapshot. The connected public GitHub `main` branch is not identical to that snapshot and could not be changed with the current read-only connection.

## Verified locally

- Frozen scenario/scene/seed/ENU-command-tape contract, reproducible SHA-256 identity and strict action/timestamp checks.
- Standard scene export and strict failure if native MuJoCo is absent.
- An Isaac Lab read-only native-state collector interface; it cannot step an environment by itself.
- Two-trace discrepancy report with position RMSE, p90, max, contact-data completeness and explicit non-equivalence status.
- New claims register, linting checks and PR workflow.

## Not verified here

Native MuJoCo physics, native Isaac Lab/PhysX physics, calibrated cross-engine dynamics, high-fidelity camera sensors, Gazebo world execution, ROS 2/MCAP ground truth, production OIDC or independent scientific validity. MuJoCo and Isaac Lab are absent in the build runtime.

**Preflight:** `python scripts/check_v06_base.py --root .` fails when the v0.5 prerequisite modules are not installed. In particular, the inspected GitHub `main` is not directly compatible with this patch.

## Reproduction

```bash
python -m pip install -e '.[test]' trimesh numpy
python -m pytest -q tests/test_locked_replay_v06.py tests/test_claims_v06.py
python scripts/check_claims.py
python scripts/veap_v06.py tape --scenario warehouse-transfer --steps 24 --out artifacts/v06/control-tape.json
# Requires a real native MuJoCo installation and does not fall back:
python scripts/veap_v06.py run-mujoco --tape artifacts/v06/control-tape.json --out artifacts/v06/mujoco
# Per-tick divergence localization on paired native traces:
python scripts/veap_v06.py diagnose \
  --tape artifacts/research/v06-control-tape.json \
  --left artifacts/research/v06-mujoco-locked-replay.json \
  --right artifacts/research/v06-isaaclab-locked-replay.json \
  --out artifacts/research/v06-pilot-per-tick-diagnostic.json
```

For science and release gates see [V06_NATIVE_ACCEPTANCE_PROTOCOL.md](docs/release/V06_NATIVE_ACCEPTANCE_PROTOCOL.md) and [VEAP_RELEASE_TRAIN_v0.6_to_v1.0.md](docs/release/VEAP_RELEASE_TRAIN_v0.6_to_v1.0.md).

Every claim must have an artifact, scope and limitations: [CLAIMS_POLICY.md](docs/CLAIMS_POLICY.md).
