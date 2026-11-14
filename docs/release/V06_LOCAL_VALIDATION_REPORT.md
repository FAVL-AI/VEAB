# VEAB v0.6 local software-contract validation — 12 November 2026

**Outcome:** CANDIDATE FOR NATIVE TESTING; not native simulator validation, physical safety validation or production acceptance.

## Source and environment

- Built additively against the **locally supplied v0.5 Studio source snapshot** (which included the v0.4 assurance controls), not the currently published `FAVL-AI/VEAB` main branch.
- Connected GitHub repo was inspected but is accessible with pull permission only; no push/PR/issue or release publication was performed.
- Native MuJoCo, Isaac Lab, Gazebo and ROS 2 are **not installed** in this execution environment.

## Executed tests

- `python -m pytest -q`: **103 passed, 1 skipped** in 34.19 seconds.
- The skipped test is `tests/test_native_mujoco_v06.py`, which explicitly requires the missing native MuJoCo binding.
- `python scripts/check_claims.py`: **3 registered evidence claims validated against local file digests; four controlled public-copy surfaces passed**.
- `python scripts/check_v06_base.py --root .`: **local v0.5 baseline prerequisites present**; older published GitHub main does not contain them and is not directly patch-ready.
- `python scripts/veab_v06.py tape --scenario warehouse-transfer --steps 24`: **frozen control tape generated** and stored under `artifacts/research/v06-control-tape.json`.
- `python scripts/veab_v06.py run-mujoco ...`: **correctly exited nonzero** with native MuJoCo requirement instead of falling back to toy physics.

## Positive evidence within tested scope

- Frozen command/scene/scenario hash binding, ENU velocity reference semantics, bounded input checks, mandatory timegrid checks.
- Altered command, dropped observation and metadata tamper rejected in synthetic software controls.
- Position RMSE/p90/max and contact-data completeness reported, without alleging either simulator is ground truth.
- Evidence register digest policy rejects modified artifacts, unsupported `VALIDATED` claims, and unqualified product language.

## Not tested or claimed

Native Isaac or MuJoCo physics results; robot inertia/contact equivalence; calibrated cross-engine accuracy; external provenance authenticity; hardware telemetry; independent external evaluation; production IAM/HA or security certification; scientific SOTA. The existing v0.5 Studio's local role implementation has not been independently penetration-tested.

## Next acceptance actions

1. Reconcile the patch with the user's current 105-test native worktree and publish via a reviewed feature branch (connected GitHub write permission is currently absent).
2. Execute `tests/test_native_mujoco_v06.py` on a pinned native MuJoCo environment, preserve runner logs and version/asset hashes.
3. Implement and execute an actual pinned Isaac Lab physics scene, then record its root-state/contact measurements using the v0.6 observer and locked command tape.
4. Calibrate equivalent robot/scene models and conduct preregistered matched tests with independently authored scenes.
5. Independently audit provenance, grading accuracy and product threat model before customer or funding qualification claims.
