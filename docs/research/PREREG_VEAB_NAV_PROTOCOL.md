# VEAB-Nav — preregistration candidate for future confirmatory validation

**Status: planning document. NOT a registered study.** The fixed five public scenarios, existing seeds and all statistics in `examples/` / `artifacts/research/` have already been inspected and are **exploratory development data**. They must not be reclassified as held-out or confirmatory data.

## Problem, rationale and falsifiable hypotheses

**Who:** robotics research teams and independent safety engineers. **What:** compare final task-success scoring with actor-independent process grading. **Why:** terminal success can hide unsafe intermediate execution. **Where:** matched toy world and independently implemented high-fidelity simulator first, then supervised physical mobile robot. **When:** freeze before any future held-out trial. **How:** blind scenarios by environment identity, use external ground-truth annotations, independently replay trace contracts, predefine analysis and report null outcomes.

Primary hypothesis H1: Under matched scenario, seed, model, planner, harness, sensor, robot and fault conditions, the process-level evaluation identifies **additional independently confirmed unsafe task completions** beyond a terminal-success-only evaluator, at an acceptable predeclared false-rejection rate.

H0: additional true-unsafe-completion detection is zero or too low relative to evaluator cost and false rejections; reject any claim of evaluation advantage if ground-truth disagreement is not corroborated.

Secondary hypotheses: H2 process grading detects bounded-time recovery failures missed by terminal success; H3 engine transfer reveals environment-dependent changes in safety/efficiency, conditional on **calibrated identical robot model**.

## Experimental design to freeze **before** acquiring a new test set

- **Population:** task families navigation, target absence, disturbance recovery; expand to manipulation only after safe contact and force instrumentation exists.
- **Unit of generalization:** independent environment/scene, not step, frame, repeated deterministic seed or resampled identical layout.
- **Design:** scene-stratified paired factorial experiment with policy, planner/harness, safety-gate, fault type/severity, and simulator as separate factors. Freeze per-model observation/action schema and time/compute budget.
- **Control:** task-success-only grader applied to identical raw trajectories; independent process verifier blinded to the executing policy.
- **Reference truth:** third-party event monitor / independent calibrated simulator logger, with a blinded human engineering adjudication set. The executing policy and software verifier must not share an unexamined sole ground truth source.
- **Holdout:** new independently authored scenes, robot geometry and fault sequences not available during tuning. Hash preregistered task manifests before testing; do not disclose hidden assets to the policy.
- **Ground truth taxonomy:** actual collision/contact, keep-out intrusion, force-limit violation, failure to safely stop within T, target absence, unsupported terminal claims; label observability and uncertainty.
- **Safety boundary:** no commands issued from the web UI to physical actuators. In supervised trials use an external speed limiter, hardware E-stop, exclusion zone and independent operator.

## Metrics (report separately, no unvalidated single composite leaderboard score)

**Primary endpoint:** incremental sensitivity for detecting independently adjudicated unsafe *task-complete* episodes at a predeclared maximum false-positive rejection rate. Report absolute counts and scene-clustered confidence intervals. An outcome-only baseline is defined strictly by goal reach; an additional stronger safety-aware comparator must also be evaluated to avoid a straw-man comparison.

**Secondary:** verified success; violations per 1,000 actions; severity by force/margin/time; bounded fault recovery (safe-state deadline and subsequent completion); latency p50/p95; measured electrical energy per verified task in J where available; communication/token cost; missing-event rate; auditor disagreement; sim-to-sim trajectory divergence after matching mass, actuator control and sensing.

**Statistical plan:** blinded scenario-clustered paired analysis; select number of scenes using pilot effect variance and a documented power/MDE calculation *before* running the confirmatory study. Report sample size, all attempted trials and abstentions. Two-sided tests with alpha fixed in advance, adjust for predeclared secondary multiplicity. Report negative findings and uncertainty. The existing five-scene public sample is too small for credible generalization; a p-value derived from repeated seeds cannot substitute for independent scene sampling.

## Falsifiers and mitigation

- **Outcome grade beats or matches process grade on independent true-positive identification at equal false-rejection** → no claimed advantage; audit verifier complexity and false alerts.
- **Verifier disagreement originates from common simulator bug or privileged ground truth** → halt, recalibrate and re-run under independent supervision.
- **Safety gate reduces collisions but raises deadline breaches or other hazards** → include both in the safety case; do not collapse trade-offs.
- **Native engine traces diverge because physical robot specifications differ** → invalidate sim-to-sim comparison until dynamics/system identification match.
- **HMAC chain recreated under compromised custody** → mark evidence unauthenticated; require external signatures, key custody and sensor provenance.

## Engineering gates and decision criteria

| Gate | Proposed minimum condition for progressing |
|---|---|
| R1: Public toy validity | Every matched arm has the same scenario digest, no duplicated experiment rows; at least four deliberately corrupted-record cases rejected; disclose rehashed-stream attack limitation |
| R2: Experimental validity | External safety adjudication and blinded scenarios; demonstrate sensitivity/false-rejection estimates with scene-clustered uncertainty and preregistered analysis |
| R3: Simulation portability | 30 or more native trajectories across at least two task families and two calibrated engines; record native versions, coordinate conversion, contact and latency discrepancies |
| R4: Physical measurement | 30 or more witnessed supervised trajectories with an independent E-stop and calibrated onboard timing; no claims before safety review |
| R5: SOTA evaluation | Compare against the strongest relevant reproduced peer-reviewed embodied baselines with frozen budgets, independent evaluator and uncertainty; publish null or adverse outcomes |

No achieved threshold in this document implies independent safety certification.
