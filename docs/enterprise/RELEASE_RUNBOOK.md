# Pilot deployment runbook and explicit production blockers

## Local single-host demo

1. Activate Python venv, install base/test requirements, and execute `python -m pytest -q`.
2. Use `python -m veap.enterprise.cli bootstrap ...` to create the first tenant and owner. Treat printed bearer token as secret.
3. Run `uvicorn veap.enterprise.api:app --host 127.0.0.1 --port 8010`.
4. Open `/studio`. Create project, run toy-world experiment, export evidence, add second distinct reviewer, verify audit chain and download the project report.
5. Stop the server. `studio-data/` retains database and evidence; back it up only to an access-controlled location.

## Docker development fixture

`docker compose -f docker-compose.studio.yml build` then `docker compose -f docker-compose.studio.yml run --rm studio python -m veap.enterprise.cli bootstrap ...` then `docker compose -f docker-compose.studio.yml up`.

The Compose configuration does not expose remote networking, grants no extra Linux capabilities, and uses a read-only root filesystem with a writable studio-data volume. Validate volume permissions and SELinux/AppArmor policies on the target host.

## Fail-closed rules

- `VEAB_STUDIO_RELEASE=production` fails startup on purpose.
- Do not bind developer-token mode to the public network; disable or isolate any reverse proxy that exposes it.
- Never enable robot actuation via the read-only Studio API.
- Do not label an MCAP upload as decoded/authenticated. Only its header has been checked.
- Never claim that validated hash chains prove true sensor observations.

## R2 prerequisite work

Replace dev-token with a production-reviewed OIDC implementation; deploy Postgres with tenant-aware row policies; external S3 object storage and retention locks; encrypted backups and tested restore; KMS-backed signatures; sandboxed, rate-limited worker services; security monitoring; request tracing; per-tenant quotas; a documented incident-response runbook; data retention and GDPR review.

## R4 production prerequisites

Independent penetration assessment and remediation; external infrastructure review; evidence custody and cryptographic key-rotation test; disaster-recovery exercise and RTO/RPO records; load tests; on-call and incident management; documented DPIA where applicable; paid pilot acceptance; independent safety-case review for any robot-connected service.

**Current verdict:** software pilot working; production qualification explicitly not passed. No enterprise SLA, formal safety certification, SOC2 or ISO 27001 certification asserted.
