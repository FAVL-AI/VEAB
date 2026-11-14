# VEAB-Nav — Prospective scientific validation protocol (unregistered)

**Document status:** prospectively drafted 2026-11-12, **NOT preregistered**, NOT a validated benchmark or real-robot assurance case. The existing five toy-world scenarios and 17 synthetic controls are public development data. They cannot be reused as independent held-out confirmatory evidence.

## Research problem and falsifiable hypothesis

**Who:** autonomous-robot development teams, external evaluators, research scientists. **What:** evaluate incremental validity of process-level verification. **Where:** independent scenes and eventually native Isaac Lab/MuJoCo, ROS 2/MCAP and supervised physical robots. **When:** freeze this protocol before creating and evaluating unseen tasks. **Why:** terminal success may overlook unsafe execution and missing evidence. **How:** pre-specified comparators, two independent reference channels, human adjudication and scene-clustered paired statistics.

Primary H1: Given matched scenes, policies, observations, control budgets, harnesses and disturbances, VEAB process verification identifies independently adjudicated unsafe **task-complete** runs missed by the **strongest practical safety-aware terminal grader**, at a prespecified false rejection rate no greater than 5% on good runs.

Null: VEAB adds no independently corroborated unsafe-task-completion detection beyond the safety-aware terminal grader, or it adds false rejections beyond the prespecified bound.

Secondary H2: Process verification identifies missing events, unsubstantiated recovery claims and invalid action/timing sequences otherwise missed by terminal grading, without unacceptable false rejection.

**Critical existing finding:** On 17 purpose-built synthetic controls, a reconstructed safety-aware baseline already detects all seven authored unsafe cases; VEAB's additional three detections concern evidence/claim validity, not additional unsafe-action detection. This is a mechanism regression suite, not support for H1.

## Evaluation comparators (same raw episodes)

1. Self-reported terminal status, weakest orientation comparator; never the only baseline.
2. Self-reported terminal safety counter; benchmark a common practical but untrusted alternative.
3. Reconstructed safety-aware terminal grader using an independently implemented geometry/temporal monitor (strong in-fixture comparator). Shared-monitor dependence must be disclosed.
4. VEAB process verifier, considering geometry, temporal contracts, recovery claims, event completeness and provenance state.
5. External embodied benchmark or established safety framework under matched observation/control assumptions (future native integration).
6. Two blinded human engineering adjudicators; their disagreements reported with Cohen's kappa and the number of uncertain/unresolved items.

## Independent evidence model

- Agent log: proposed actions, observations, internal outcome claims.
- Native simulator instrumentation: world states, contact and control telemetry, engine version, clock and calibration. **Not automatically truth**.
- Separate monitor: independent code path (separate process, no simulator or policy imports), reconstructing collision, keep-out, deadline, state/command consistency and fault stop conditions.
- External reference: separately instrumented sensor or calibrated witness; paired human review for ambiguous episodes. **Not implemented in this release**.
- Custody: hash chains permit tamper evidence after recording. HMAC with isolated key adds authentication to the signed content if custody is trustworthy. Neither establishes physical truth, provenance, time source or hardware attestation.

## Unit of analysis and sample size

- Unit of generalization = **independently authored scene**. Repeated seeds and frames are nested within scenes, NOT independent replications.
- Pre-register the minimal detectable difference, the between-scene SD of paired detection gain, two-sided alpha 0.05, power target 0.80 and the multiplicity rule for secondaries.
- An *illustrative-only* normal approximation, assumed scene SD 0.4 and target mean gain 0.2, suggests 32 independent scenes. This is NOT a study design commitment until variance is estimated in a separate pilot sample.
- Stratify by navigation, inspection, absence/rejection and fault family; freeze robot mass, geometry, sensors, tool budget and control horizon.
- Keep exploratory tuning scenes entirely outside confirmatory evaluation. Report all attempted episodes, failure and missingness.

## Primary outcomes

Independent human/monitor consensus unsafe-task-complete detection sensitivity; false-rejection rate for independently labelled good task-complete episodes. Compare process grading with reconstructed safety-aware grading on **paired scene clusters**, with bootstrap confidence intervals or pre-registered mixed-effects analysis. Report grader disagreement rather than suppressing it.

## Secondary outcomes / 7 KPIs

1. Unsafe-completion detection sensitivity / 95% CI.
2. Good-episode specificity and false-rejection rate / 95% CI.
3. Fault stop/recovery time and successful recovery after disturbance.
4. Event completeness and unsupported-claim detection.
5. Violations per 1,000 actions, with calibrated severity and uncertainty.
6. Inference/compute/communication cost and **measured** energy in joules when instrumented (proxy otherwise).
7. Cross-engine discrepancy (pose/velocity, contacts, timestamps, energy), using calibrated equivalent models and matched controls.

## Adversarial / negative controls

Public constructed controls: valid paths, narrow-clearance path, legitimate recovery, forbidden-zone intrusions (reported and unreported), swept collision, missed fault-stop deadline, unsupported recovery, unsupported goal completion, missing proposal, event-ordering fault, deadline and speed breach. Some labels target **evidence validity**, not physical safety. Never pool the latter with unsafe-action sensitivity without separate stratification.

**Provenance falsifier:** A coherent replay with forged but geometrically plausible states can pass a trace-only monitor. This weakness is reproduced as an explicit test. Do not imply third-party authenticity until protected external capture and audit are validated.

## Stage gates

**G0 — local contract controls:** >=15 constructed adversarial/positive fixtures and no failing automated tests; mark software regression only. Achieved for accessible base at 2026-11-12 with 17 controls and 55 tests, but not independently certified.

**G1 — independent reference creation:** >=32 new independent scenes *only if justified by pre-study variance/power*, blinded reference decisions and adjudicator agreement. If the evidence set does not satisfy this, H1 is not confirmatory.

**G2 — Isaac Lab native:** reproduce >=20 instrumented trajectories across >=2 task families, inspect contact, time synchronization and replay, and freeze native engine and asset versions. Not executed here.

**G3 — MuJoCo differential:** >=20 matched native trajectories per family, calibrated equivalent mass/inertia/geometry/control, with predeclared acceptable discrepancy and divergence reports. Not executed here.

**G4 — Gazebo/ROS 2:** known compatible ROS/Gazebo pairing, validated TF, sensor calibration, /cmd_vel, /emergency_stop, MCAP record/replay and clock source. No actual ROS graph run here.

**G5 — supervised hardware:** pre-approved risk assessment, hardware independent E-stop, operator override, velocity/geofence limits and measured stop latency; signed witness records, not merely robot self logs. Not executed here.

**G6 — external reproduction/SOTA:** compare independently reproduced embodied baselines, report confidence intervals, costs, failures, source code, trajectories and adverse/null findings. SOTA is conditional on this independent external evaluation.

## Boundary

These software tests do **not** establish physical fidelity, scientific hypothesis validation, model-generalization, regulatory compliance or certified safety. All physical actuation requires independent risk review and hardware controls.
