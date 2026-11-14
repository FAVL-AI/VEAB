# VEAB Assurance Studio — Security model, v0.5 pilot

**System classification:** software research-pilot application handling potentially sensitive customer telemetry. No public internet exposure permitted pending external review. No safety-critical robot commands are implemented.

| Threat | Implemented pilot controls | Remaining blockers |
|---|---|---|
| Cross-tenant data disclosure | Every mutable/read path checks tenant membership and project membership; opaque record IDs | Adversarial authz review, database row policies, multi-node and external penetration testing |
| Credential theft | High-entropy tokens stored as SHA-256; no token kept in browser storage; token expiration | Production SSO and phishing-resistant MFA, credential rotation and revocation service |
| Forged JWT roles | OIDC RS256 signature, pinned issuer/audience, local subject mapping; ignores JWT role claims | Live IdP configuration, logout/revocation handling, JWKS rotation tests and security review |
| Malicious telemetry upload | 12 MiB bounded streaming, extension allowlist, strict JSONL schema, MCAP magic header check, no execution | Sandboxed MCAP parser, antivirus, quotas, asynchronous scan, zip-bomb tests |
| Overbroad experiment jobs | Bounded worker pool; fixed scenario/policy constraints; no shell/command arguments from API | Multi-process worker isolation, job-level CPU/memory/GPU limits and queue durability |
| Evidence tampering | SHA-256 upload digest; explicit integrity endpoint; per-tenant chained audit records | Independent event anchoring, KMS signatures, append-only/WORM storage |
| Spoofed physical evidence | Labels all uploads `unattested_external`; no robot safety claim | Hardware-backed capture, calibrated external ground truth, signed timestamps |
| Self-certification | Review author must differ from run author; reviewer role | Blind label allocation, inter-rater calibration, independent third-party auditors |
| Transport/interception | Bind loopback by default; no API cookies; security headers; remote dev-token exposure prohibited by configuration | TLS reverse proxy, mTLS service identities, WAF, external key custody |
| SQL injection / path traversal | Parameterised queries; tenant-bound IDs; strict filename whitelist and safe object paths | Independent fuzzing and SAST/DAST validation |
| Data retention & deletion | Data confined to local configured directory, excluded from source archive | Retention scheduler, data-subject request workflows, legal hold, tenant deletion tests, offsite backup |

**Evidence hierarchy:** (1) SHA-256 file consistency is NOT provenance; (2) externally keyed HMAC is NOT hardware attestation; (3) software monitoring is NOT certified safety; (4) offline reproduction is NOT real-world generalisation.

Developer bootstrap tokens are sensitive. The included Docker Compose fixture exposes localhost only; it is not a production deployment guide.
