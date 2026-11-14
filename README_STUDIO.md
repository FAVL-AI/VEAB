# VEAB Assurance Studio v0.5 — executable pilot

**What this release really does:** it extends the available VEAB v0.4 deterministic toy-world benchmark with a separate, tenant-scoped evidence service, UI, audited workflow and controlled human review. It is NOT the user's newer local 105-test native Rust/C++/Go branch, and it must not overwrite that branch. It contains **no ROS 2 actuation commands** and does not claim real-world safety, certified autonomy, external sensor authenticity, or production HA.

## Start locally (Python 3.10+, Linux/macOS)

```bash
cd veab-platform
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
python -m veap.enterprise.cli bootstrap --org "Industrial Robot Pilot" --email owner@example.org --name "Owner"
python -m veap.enterprise.cli add-user --tenant TENANT_ID --email reviewer@example.org --role reviewer
python -m uvicorn veap.enterprise.api:app --host 127.0.0.1 --port 8010
```

Visit **http://127.0.0.1:8010/studio** and supply the personal development bearer token from CLI bootstrap. Store the reviewer token separately. Do not commit tokens or copy them into documents. Tokens live in the browser's memory only and expire by default after 24 hours. This mode is suitable only for a localhost development/pilot environment; it is not enterprise SSO.

The existing benchmark UI remains in the source tree but is **not mounted** in the Studio service. Do not expose the legacy `veap.api:app` as a multi-tenant service.

### Working user flow

1. Connect as the owner through the local development token.
2. Create a named customer project in your organisation.
3. Choose a frozen public benchmark scenario, route/greedy baseline, seed and geometric gate; execute a task.
4. Inspect independently evaluated postconditions, trajectory, constraint violations and digest-linked bundle.
5. Upload a raw `.json`, strictly formatted positional `.jsonl` or `.mcap` file; check its recorded SHA-256. Imported MCAP is only header-checked and stored, **not decoded or validated as robot telemetry**.
6. Sign in with a different user holding the reviewer role to submit an assessment; self-review is rejected.
7. Check project report, export the evidence, inspect the audit-chain status and browse the available 3D scene exports.

### Scenario asset contract

Canonical `ENU_z_up_m` toy geometry is exported as OpenUSD (`.usda`), MuJoCo MJCF (`.xml`), Gazebo SDF (`.sdf`), URDF (`.urdf`), binary glTF (`.glb`) and JSON. Exports are usable interchange files, but the release does not execute Isaac Lab, native MuJoCo, Gazebo or Unreal in this environment. Robot CAD is a research surrogate, not calibrated hardware.

### Authentication and authorisation

- `dev-token` mode: CLI-generated 320-bit random bearer tokens stored as SHA-256 digests; server-side memberships enforce owner/researcher/reviewer/auditor/viewer permissions.
- `oidc` mode: RS256 JWT signature validation against HTTPS JWKS; strict configured issuer and audience; subject must be administrator-bound to a principal before access. JWT-provided tenant or role claims are ignored. This validation path is **implemented but has not been integrated or penetration-tested with a live identity provider**. Install `pip install -e '.[enterprise]'` for JWT support.
- `VEAB_STUDIO_RELEASE=production` **fails closed**. Operator must deliver the R2/R4 readiness evidence before creating a qualified production release.

### Files and operational limitations

`studio-data/` contains project records, identity mappings, hashed tokens, trajectories and uploaded evidence. The single-process SQLite WAL registry plus bounded in-process worker are suitable for **development and small pilot experiments only**. High availability, database migrations, external key custody, S3 object locking, signed container provenance and tenant-isolated worker sandboxes are **not implemented**. The audit chain provides local tamper evidence; database administrators can rehash it. Human reviews are separate judgements, not independently captured ground truth.

### Tests

`python -m pytest -q tests/test_enterprise_studio.py` checks tenant isolation, RBAC, worker execution, idempotency, provenance, audit-chain tampering, human review independence, endpoint isolation, uploaded file boundaries and explicit release failure modes.

Read `docs/enterprise/ARCHITECTURE.md`, `SECURITY_AND_THREAT_MODEL.md`, `SCIENCE_PROTOCOL.md`, `ACCEPTANCE_GATES.json`, `RELEASE_RUNBOOK.md` and `FUNDING_CASE.md` before planning a live customer deployment.

## Optional automated browser UI smoke check

The working source includes `tools/studio_browser_smoke.py`. Install Playwright and its Chromium browser, then run:

```bash
python -m pip install playwright
python -m playwright install chromium
python tools/studio_browser_smoke.py --out studio-browser-smoke.png
```

The script verifies actual browser controls against the FastAPI app using a **local in-memory test-client bridge** (no external network). It tests the rendered UI and API logic together, but not reverse-proxy TLS, public network exposure or live OIDC.
