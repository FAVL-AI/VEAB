# VEAB Assurance Protocol — prospective research design

## Research question and falsifiable hypothesis

**H1:** Under matched scenes, tasks, policies, harnesses, sensors and injected disturbances, process-level verification identifies independently adjudicated execution/evidence failures missed by a credible safety-aware terminal evaluator, while maintaining a preregistered false-rejection ceiling. The current 17 synthetic controls are software fixtures, not confirmatory observations.

## Experiment

**Who:** evaluation engineers and two independent human adjudicators who do not know model configuration labels.

**What:** separate (A) terminal-success-only, (B) safety-aware terminal-state evaluator, (C) VEAB process verifier, (D) distinct external-reference monitor, and (E) blinded human panel.

**Where:** at least two calibrated simulators first (Isaac Lab, MuJoCo), then a supervised physical robot under an independently reviewed safety case. Gazebo/ROS 2 ingest is a separate middleware compliance study.

**When:** preregister *before* collecting unseen-scene results; record exact source revision, model weights, configs and hashes.

**Why:** falsify or support incremental diagnostic value relative to a strong comparator, not a weak straw-man benchmark.

**How:** author genuinely unseen scenes, specify independent scene as the clustering unit, lock the inference plan, run matched conditions including sensor dropout, actuator stall, contact risk, keep-out zones, latency and missing evidence. Compute sensitivity, specificity, false-rejection, false-acceptance, calibration and confidence intervals; report simulator disagreement and costs separately.

## Controls

Scene holdout and independent authorship; leakage checks; intervention/shield ablation; model/harness factorial ablations; signed replay manifest; separate-policy and separate-monitor implementations; negative-control traces; failure cases; inter-rater agreement and adjudication log.

Do not count three seeds of one scene as three independent environmental replications. Sample sizes must come from a prespecified effect size and scene-level power model, not p-value fishing. Publish negative/null outcomes and costs alongside positive results.

## Priority KPI definitions

| Metric | Target gate for confirmatory study | Measurement |
|---|---|---|
| Extra true failures detected | >=10 percentage points on a *predeclared error class*, if power permits | Blinded reference labels vs comparator B |
| False rejection | <=5% independently adjudicated good episodes | Case-level FPR with CI |
| Evidence completeness | >=99% required fields in telemetry eligible for assessment | Contract schema checker |
| Cross-engine consistency | Agree on qualitative safety outcome for >=95% of matched calibrated cases; deviations investigated | Isaac/MuJoCo paired replay + external monitor |
| Deterministic replay | 100% identical digests under frozen single-platform environments | Hash comparison, compiler/runtime pins |
| Human review time | >=30% median reduction vs a predeclared review baseline without sensitivity loss | Timed blinded reviewer study |

These are proposed success gates, not achieved results; they may be revised in the versioned protocol before preregistration. The 99.9% availability target is an operational SLA, not a scientific metric.
