# VEAB Release Train — v0.6 to v1.0

**Date:** 12 November 2026  
**Repository:** https://github.com/FAVL-AI/VEAB  
**Scope:** autonomous/embodied AI evaluation only.  
**Current evidence:** verified local v0.5 source snapshot, additive v0.6 software contracts.  
**No native Isaac Lab or MuJoCo run is claimed by this document.**

## Release philosophy

VEAB Research is an open, model-and-harness-agnostic scientific evaluation programme. VEAB Replay / Assurance Studio is a read-only, multi-tenant analytics product for recorded and shadow-mode robot operations. The two share a trace contract but must maintain separate research, product, safety and certification claims.

**Hypothesis H1:** Compared with the strongest reproduced safety-aware outcome grader, process-level verification detects additional independently adjudicated evidence/recovery failures under paired held-out conditions without exceeding a prespecified false rejection rate. Do not redefine the error class after observing the results.

**Hypothesis H2:** With an identical control tape, calibrated equivalent robot assets and matched integration timing, Isaac Lab and MuJoCo reveal measurable differences in trajectory/contact outcomes; their comparison improves discrepancy diagnosis but neither simulator automatically supplies external ground truth.

**Method:** freeze task contracts and controls; run native engines in pinned containers; independently record state and contacts; audit provenance; compare on predeclared metrics; blind human reviewers to policy labels; include negative controls and null results.

### Release levels and mandatory exit decisions

| Release | Objective | Minimum externally inspectable deliverables | Stop/no-go rules |
|---|---|---|---|
| **v0.6 — Native evidence** | True Isaac Lab and MuJoCo stepping plus cross-simulator comparisons | 2 independently executed native physics traces for each of at least 20 matched input tapes across two task families; native version/build IDs, scene and tape hashes, command/timing checks, geometry/contact results, independent discrepancy report | NO acceptance when only MJCF/USD exports exist, recorder takes mock inputs, timebases diverge, source is unlabelled or robot assets are uncalibrated |
| **v0.7 — Production security foundation** | OIDC, Postgres, protected object storage, durable workers and tenant isolation | External IdP integration tests; tenancy-escape negative tests; migration/rollback; scoped object-store access; queue leasing and poison-message handling; SBOM and secret scans | No hosted customer trial when authentication, tenant isolation, backup restore or worker isolation fails |
| **v0.8 — ROS 2/MCAP & shadow pilot** | Read-only robot fleet evidence ingestion and an external monitor | ROS 2 time/TF/IMU/odom/control channel schema; authenticated recording manifest; independent ground-truth device; one partner-approved shadow-mode trial; documented data consent | NO robot command endpoint or unaudited autonomous operation; no sourced-ground-truth claim from ROS odometry alone |
| **v0.9 — Operational qualification** | Security review, restore, load tests, independent scientific evaluation | Penetration-test report and re-test; SLO and observed service metrics; chaos and restore drills; reproducible held-out scenes; blinded adjudication and inter-rater agreement; customer security review | No production claim with unresolved high-severity security risk, inadequate sample size, or missing recovery evidence |
| **v1.0 — Qualified assurance service** | Limited, named intended-use production deployment | Approved threat/risk assessment, customer acceptance, runbooks, incident ownership, documented service boundaries, paid pilot or contract, external scientific results where claimed | Release remains blocked absent independent sign-off and operational proof; certification is not implied |

## Scientific progress gates (separate from release numbers)

- **G0 implemented:** tests and versioned code meet stated software requirements.
- **G1 demonstrated:** a named reproducible experiment has evidence within a bounded scope.
- **G2 validated:** independently obtained reference data and powered, held-out results establish a named intended use.
- **G3 assured operationally:** context-specific risk assessment, management controls, production history, external audit, customer acceptance. No accredited certification unless actually awarded.

A release tag may be created at G0/G1 as an engineering candidate but must not inherit G2/G3 language.

## SMART release KPIs — PROPOSED (not measured or achieved)

| KPI | Operational definition | Proposed acceptance and deadline |
|---|---|---|
| Paired native coverage | Count of matched command-tape/scene pairs actually executed in **both** physics engines | >=20 pairs across >=2 independently authored task families before v0.6 exit |
| Timebase consistency | 99th percentile absolute deviation from recorded frozen commands/grid | <2 ms at the sampling boundary, or report preregistered engine-specific exceptions |
| Cross-simulator error | P90 position error, max position error, and contact mismatch on calibrated assets | Define thresholds from pilot calibration before held-out confirmatory runs; report every failure |
| Incremental verifier value | Difference in independently labelled failure recall between VEAB and safety-aware comparator | Predeclare target >=10 pp for specified evidence/recovery errors while false rejection <=5% in powered study; not a current finding |
| Evidence completeness | Required data fields present/eligible fields expected per real evidence schema | >=99% for in-scope replay packets at v0.8 pilot exit |
| Service recovery | Recovered state, accepted run count and audit continuity after documented fault injection | 100% completion of predeclared backup/restore test cases before v0.9 qualification; no availability SLA inferred |

## Research phases

**Initial observation:** The toy-world mechanism demo contains task-complete traces that the verifier rejects, and synthetic controls distinguish evidence omissions from physical violations. These are not independent scientific effectiveness estimates.

**Failures/challenges:** public scenes, uncontrolled generalisation, same-source monitor truth, forged coherent histories, uncalibrated robot surrogate, absent native simulations, and non-durable local worker.

**Refinement:** lock inputs and timebases, require two physics engines, add independently authored scenes, separate monitor custody, external reference measurements and blinding.

**Further experiments:** calibrated system identification, matched control tapes in Isaac and MuJoCo, independent collision/contact annotation, shift tests, fault sweeps, scene-clustered comparisons, cost/provenance tests, human review time trials.

**Final conclusion boundary:** v0.6 software contracts cannot prove SOTA, certified safety, fidelity, independently authenticated source data, or production readiness; such claims remain conditional on named gates.

## Funding sequencing and IP

A production assurance proposal and an early-stage controllable-AI research proposal are distinct applications. Claim technology readiness only with the funding body's definitions and documented externally inspectable evidence. Confirm applicant ownership, research collaboration/IP licences, information security, partner commitments and budget eligibility before submission. The indicative £480,000 twelve-month envelope is a planning model, not an awarded grant or eligible cost schedule.

## Sources and standards to consult

- Official Isaac Lab docs: https://isaac-sim.github.io/IsaacLab/main/source/how-to/launch_app.html
- Official MuJoCo Python API: https://mujoco.readthedocs.io/en/stable/python.html
- NASA software independent verification and validation: https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695499/SWE-141+-+Software+Independent+Verification+and+Validation
- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- NIST SSDF: https://csrc.nist.gov/Projects/ssdf

This programme uses the cited references as engineering guidance; following them does not confer accreditation or regulatory approval.
