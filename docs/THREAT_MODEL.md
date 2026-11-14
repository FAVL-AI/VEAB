# VEAP v0.1 threat model and operational boundary

## Trust model

The model/policy and the simulator are both untrusted sources of **claims**. A separate verifier reads the serialised trace and task contract. It checks geometry and trace integrity without importing the planner or simulator. That separation mitigates accidental self-grading but does **not** guarantee independence from common implementation assumptions or malicious forgeability.

## Specific threats / mitigations / residual risk

| Threat | Present mitigation | Residual risk |
|---|---|---|
| Agent reports task success without reaching its goal | Independent waypoint checks and ordered markers | Same simulator labels may still be wrong |
| Robot crosses a mapped obstacle between states | 2cm segment sampling in separate verifier | Thin, unmodelled physical objects or collisions below sampling resolution |
| Event file manually edited | SHA-256 hash-linked canonical events and manifest root | Whole chain can be rewritten by a malicious actor |
| Whole chain and manifest rewritten | Optional HMAC of full manifest including root | Shared key compromise; no hardware TPM or public-key notarisation |
| Fake external robot evidence | Import marks `external_unattested_telemetry` and cannot earn verified status | Human may still misinterpret raw data without provenance |
| Unauthorised use of run-control API | Localhost-only default, optional bearer token | No tenant RBAC, multi-user audit, quotas per principal or federated auth |
| Web prompt injection from external model | Model review is advisory only; no tool execution; output schema-check | Third-party provider receives selected public task contract; model text may be incorrect |
| Unbounded evaluation work | 2-worker thread pool; max 4 queued/running jobs | In-memory process supervision not multi-node robust; failure/restart recovery absent |
| Browser XSS / content injection | Escaped data fields, CSP, restrictive schema, same-origin API | External security assessment incomplete; no CSP reporting endpoint |
| False claim of certified control barrier safety | Clear distinction: geometric filtering, NOT HOCBF or formal proof | Unmodelled real dynamics, sensing delay, physical constraints |
| Leakage of hospital observation data | Demo uses synthetic coordinates only | Future real ROS data need privacy and security review |

## Deployment / escalation gates

1. Keep the default 127.0.0.1 bind. If containerised, publish localhost-only ports.
2. Before network exposure, add authenticated IAM, TLS termination, rate limits, policy isolation, observability, secrets management, CSRF assessment and multi-tenant data separation.
3. Never connect `veap.api` to `/cmd_vel`, actuator driver, MCU motion control or hazardous tool execution. A **separate hardware controller with emergency stop** must bound any future physical agent.
4. Collect independent, signed or hardware-attested sensor provenance before using the word **verified** for real-robot outcomes.
5. Sign benchmark snapshots with independently custodied keys; publish immutable object hashes to an external log to mitigate coordinated evidence rewriting.
6. Red-team all pipeline paths: model response, tool adapter, memory, replay data, partial messages, interface user input and artefact ingestion.

## Data classifications

`deterministic_toy_simulation` = internally simulated, trace checked, not physical.
`external_unattested_telemetry` = positional record imported, source authenticity not validated, never promoted to verified.
`HMAC-SHA256` = optional shared-secret integrity attestation only when independent key available.
