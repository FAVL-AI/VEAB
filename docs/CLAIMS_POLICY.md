# VEAB claims policy — 2026-11-12

**Canonical rule:** No public capability, benchmark, deployment, safety, reliability, or funding statement may exceed the recorded evidence scope.

## Evidence labels

| Label | Required support | Permitted wording |
|---|---|---|
| IMPLEMENTED | Versioned code and passing specified checks | Implemented; locally tested |
| DEMONSTRATED | Named repeatable experiment and recorded result under a stated scope | Demonstrated under the specified conditions |
| VALIDATED | Independently collected evidence of fitness for a named intended use | Validated for that named use only |
| CERTIFIED | Applicable accredited external certificate and stated scope | Certified only for the certified scope |

**Verification** asks whether requirements were implemented correctly; **validation** evaluates fitness for intended use. A separately implemented monitor does not automatically confer organisational independence. A checksum or HMAC does not authenticate the original sensor observation.

## Every outward-facing claim requires

A claim ID; exact claim text; evidence artifact and digest; scope (scene, versions, hardware, protocol, samples, seeds); limitations; evaluation party; decision status. `docs/CLAIMS_REGISTER.json` is machine checked. New controlled public copy includes `docs/PUBLIC_PRODUCT_CLAIMS.md`, `docs/release/V06_FUNDING_POSITION.md`, `web/v06_product_positioning.md`, and the PR template. All must pass the scoped scanner before publishing. Historical public materials require separate manual migration.

## Gated maturity

- **G0 — implemented:** code and unit/integration tests satisfy specified software requirements.
- **G1 — demonstrated:** frozen settings, trace outputs, negative controls and repeatable result.
- **G2 — validated:** independently sourced truth, held-out scenes, appropriate blinded adjudication, confidence intervals, bounded false acceptance/rejection, and fit for named use.
- **G3 — operationally assured for a context:** relevant hazards, controls, monitored operation, incident response, customer acceptance and independent safety engineering. G3 is not certification.

Planned claims such as TRL 5–6, 99.9% SLA, real-world robustness, calibrated cross-engine dynamics and external safety certification must remain targets, not current results, without designated evidence.

## Mandatory PR and funding checklist

- [ ] Every positive capability claim maps to a current evidence ID.
- [ ] The code revision, method, data split and limitations are recorded.
- [ ] Simulator and external-sensor records are explicitly distinguished.
- [ ] A forged-but-rehashed trace is **not** represented as source-authenticated.
- [ ] No raw task completion metric is promoted to verified physical safety.
- [ ] Null results, adverse comparisons and incompletely collected evidence remain visible.
- [ ] Funding technology-readiness statements cite the specific funder's TRL definition.
- [ ] No release is called production-ready or SOTA without separate external qualification.

Use `python scripts/check_claims.py` in CI. This scanner covers newly controlled copy; it does **not** certify the completeness or truthfulness of all historical repository documentation.
