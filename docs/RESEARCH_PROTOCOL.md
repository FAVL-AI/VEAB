# VEAP — Research, Experiment, and Verification Protocol

**Status: Laboratory research prototype.**

> **Core Definition:** VEAP is a **model- and harness-agnostic evaluation protocol** that jointly measures **task success**, **constraint violations**, **recovery**, **resource cost**, and **independently checkable evidence** under **controlled faults**.

## Canonical Research Narrative

The value proposition of VEAP is tested directly through empirical verification rather than narrative dramatization. We do not invent catastrophes, fictional character conflicts, or benchmark results to explain why the platform matters.

For the full nine-stage narrative, primary audience, and platform classification, see [CANONICAL_NARRATIVE.md](CANONICAL_NARRATIVE.md).

### The Primary Audience and Perspective
The primary decision-maker is the **robotics validation or safety-assurance engineer** responsible for determining whether an autonomous system satisfies defined operational acceptance criteria.

The central question: **Should completing the destination task count as success when the agent violates constraints along the way?**

### What the 60-Trial Factorial Evaluation Shows
Across five scenarios, three seeds, two policies, and two gate conditions:

| Configuration | Task completion | Verified completion | Safety violations |
|---|---|---|---|
| **Greedy, gate off** | 12/15 | 3/15 | 147 |
| **Greedy, gate on** | 12/15 | 12/15 | 0 |
| **Route, gate off** | 15/15 | 15/15 | 0 |
| **Route, gate on** | 15/15 | 15/15 | 0 |

#### The Core Narrative Anchor
**Nine of fifteen ungated greedy trials reached their task objectives but were rejected by the independent verifier because they violated safety constraints.**

For example, in `warehouse-transfer` (seed 0), the ungated greedy planner reached the goal with 22 geometric violations in 68 steps. With the geometric gate enabled, the planner completed with 22 safety interventions, 0 violations, and 83 steps. This exposes a measurable, reproducible trade-off between safety intervention and execution time.

### The Canonical Separation Example (Agent A vs. Agent B)

Consider two candidate deployment policies evaluated across 100 trials:
- **Agent A (Fast & Fragile):** Reaches the goal in 90% of trials, but violates a keep-out constraint in 30% of runs, recovers from only 20% of actuator stall faults, and consumes $2\times$ baseline energy.
- **Agent B (Verified & Resilient):** Reaches the goal in 90% of trials, has 0 constraint violations, recovers from 80% of faults ($4\times$ recovery advantage), and consumes half the energy of Agent A.

| Evaluation Metric | Agent A | Agent B | Evaluation Verdict |
|---|---|---|---|
| **Conventional Final-Success Benchmark** | **90%** | **90%** | **EQUIVALENT ($\Delta = 0.0$)** |
| **VEAP Verified Completion** | **60%** | **90%** | **$\Delta = +30.0\%$ advantage for Agent B** |
| **Keep-Out Constraint Violations** | 30% | 0% | Agent A breaches critical safety boundaries |
| **Fault Recovery Rate** | 20% | 80% | Agent B has $4\times$ higher recovery resilience |
| **Relative Energy Consumption** | $2.0\times$ | $1.0\times$ | Agent A imposes double the mechanical/battery cost |
| **Deployment Recommendation** | **REJECTED (Unsafe)** | **VERIFIED CANDIDATE** | **Stark Operational Divergence** |

> **Conclusion:** A conventional success-only benchmark ranks them identically, obscuring catastrophic deployment risks. VEAP exposes the true multidimensional operational gap.

### Formal Research Hypothesis

> **Hypothesis:** Under matched scenarios, seeds, and fault conditions, an evaluation architecture that jointly scores task completion, constraint violations, recovery behaviour, resource use, and trace-verifiable execution will identify reliability differences between agents that are not detectable using final task-success rate alone.

The present results motivate and support this hypothesis; future multi-simulator and physical validation trials will formally test its boundaries.

## 5W1H

**What:** Evaluate multi-stage embodied tasks in a reproducible benchmark measuring trajectory validity, task postconditions, safety violations, disturbances, intervention, time and an energy proxy.

**Why:** Binary task completion conceals violations, non-recovering agents and unsupported success claims. Zhu et al. (NeurIPS 2025; DOI: 10.52202/085713-5547) argue benchmarks require task, outcome and reporting validity; Zhou et al. (ICLR 2024) demonstrate reproducible execution-based evaluation in WebArena.

**Who:** Agent researchers and independent reviewers; a distinct verifier consumes immutable trace-format evidence without executing policy code. The present investigator is responsible for independently validating real robots and research claims.

**Where:** Stage A is an offline 2-D toy simulator; Stage B is Isaac Lab with recorded seeded scenes; Stage C is hardware shadow-mode telemetry and supervised trials.

**When:** Track progress against proposed research acceptance gates. Acceptance evidence is required before promoting each stage.

**How:** Freeze scenario identities and task definitions; preregister comparisons and safety bounds; pair seed/scene conditions; run all baselines; collect unmodified traces; independently verify postconditions; report intervals, invalid cases and failed runs.

## Research question and falsifiable hypotheses

**RQ1:** Can trace-level independent verification detect unsafe completions and false postconditions that a binary goal-reached metric would mark as successful?

- **H1:** Among agents with the same scenario and seed, the process verifier rejects at least one counterexample in which a naive binary evaluator would return success. The current warehouse greedy/no-gate demonstration is a local counterexample, not a general population estimate.
- **H2:** For matched scenario/seed pairs, the geometry gate reduces safety violations relative to the same planner without the gate, with a separately reported trade-off in task completion and time.
- **H3:** On genuine held-out Isaac Lab task families under disturbance, a safety-aware harness can retain verified completion while reducing unsafe events and recovery failures. **H3 is untested.**

**Nulls:** The verifier offers no additional detection beyond validated binary postconditions; gate does not affect violation rate or impairs completion. These are acceptable scientific outcomes and must be reported.

## Experimental design / controls

1. **Freeze:** Save each scenario contract's SHA-256 digest and code commit. Current demo split labels are *public*, not contamination-controlled.
2. **Factorial comparisons:** Two reference policies (greedy, route), two gate conditions (on/off), seeds 0/1/2 initially. `veap suite` pairs condition by scenario and seed.
3. **Adversarial challenges:** Observation dropout, actuator stall, perception noise, forbidden regions, narrow clearances, tampering with event payload/manifest, absent-object abstention, invalid trajectory and premature terminal claim.
4. **Process metrics:** Verified completion, partial completion, unsafe steps, min clearance, interventions, injected faults recovered, simulation time, and proxy motion energy. Track invalid/missing data separately.
5. **Statistics:** Report every trial, denominators, descriptive means, paired differences and resampled percentile intervals. Current three-seed values cannot establish general significance; later use preregistered scene-level cluster bootstrap and held-out families.
6. **Ablations:** Only change one axis at a time. For new foundation models, scaffold, tools, memory, shield and verifier are distinct factors. Never present a wrapper-on model as outperforming another without holding scaffold fixed.
7. **Device migration:** Block external autonomy pending simulator fidelity review, authoritative state capture, latency/energy instrumentation, hardware emergency-stop testing and independent sign-off.

## Initial experiment results (genuinely executed)

The initial v0.1 local warehouse trial, `route`, seed 17, gate ON, completed 3/3 milestones in 81 steps (16.2 simulated seconds) with zero geometric violations and eight geometric safety interventions. This is a demonstration that the code path can finish and pass its own independent geometric verifier. It is **not** evidence about physical navigation, uncertainty calibrated under real sensors or robust generalisation.

**Failures and corrections observed during development:**
- An early negative-target abstention initially terminated without a corresponding state sample, yielding a trace-length disagreement. Fixed by recording the terminal state before abstention.
- A hospital trial could finish before a future scheduled fault. The verifier initially demanded faults that should never have occurred in a completed episode. Fixed by checking only faults whose start ticks were reached.
- Browser test navigation in the restricted build environment was blocked; dashboard checks use a Playwright page with an API bridge, and FastAPI endpoints are separately tested in-process. This does not replace a real deployment-browser audit.

## Required SOTA evidence (not yet available)

- Physically meaningful manipulation/navigation tasks in an accepted simulator and at least one real platform.
- Independent, unreleased held-out task families with integrity-preserving task creation and contamination audit.
- Strong current baselines reimplemented under the same sensors, observations, compute budgets, model weights and scaffold.
- 5+ independently randomized scene/task seeds per family (increase based on power analysis), confidence intervals across scenes and multiple independent research replications.
- Hardware-level metrics: energy in Joules from meter/telemetry with uncertainty bounds; measured timing quantiles, inference/tokens/cloud costs, contact forces and physical emergency stops when applicable.
- Failure analysis including false-positive grading, invalid ground truth, uncertainty triggers and recovery safety.
- Threat review, consent/data privacy review for any identifiable hospital telemetry, and documented operator approval for experiments.

## Proposed Research Acceptance Gates

> **Note on status:** These are proposed acceptance gates from the research programme, not completed milestones. The research hypothesis is falsifiable: process-level verification must detect additional meaningful failures at an acceptable cost, without relying on invalid evaluation assumptions.

| Research Gate | Proposed Measurable Acceptance Criterion | Target Metric | Status |
|---|---|---|---|
| **Verifier hardening** | At least 30 preregistered adversarial fixtures; 100% detection of the defined integrity-tampering cases | Tamper detection recall $= 1.0$ | Milestone deliverable |
| **Reproducibility** | Identical trace digests across repeated deterministic executions with the same pinned environment | 0 digest drift | Open research gate |
| **Incremental diagnostic value** | Quantify additional true failures detected versus outcome-only evaluation, with false-positive rates | $\Delta \text{True Failure Rate} > 0$; $\text{FPR} = 0$ | Milestone deliverable |
| **Isaac Lab integration** | At least 20 replayable scenarios across two task families | Replay agreement | Milestone deliverable (contract) |
| **Baseline comparisons** | At least two external agents evaluated under matched observations and compute budgets | Standardized benchmark delta | Open research gate |
| **Physical evidence** | At least 30 supervised trajectories with independently checked provenance, latency and safety observations | Hardware safety rate | Open research gate |

## Immediate Milestone: Scientific Validation Release

Rather than further narrative iteration, the next development release focuses directly on scientific validation:
1. **Preregistered verifier hardening suite:** $\ge 30$ adversarial fixtures testing integrity tampering, kinematic fraud, collision bypasses, milestone jumps, and false abstentions.
2. **Diagnostic value quantification:** Formal comparison between outcome-only metrics and process-level verification across multi-seed suites.
3. **Isaac Lab integration contract:** Rigorous specification for scene exports, rigid-body poses, sensor provenance, and replayable execution.

Dashboard sample metrics are never substitutes for peer review or external replication. **Release criterion:** no real-world SOTA or production-safety statement without all device and validity gates met.

## SWOT for research programme

**Strength:** deterministic traces, independent process verifier, separable policies/gate, clear source labels.
**Weakness:** toy geometry, simplified obstacle semantics, public toy splits, HMAC single shared key, no calibrated uncertainty or real energy meter.
**Opportunity:** cross-domain embodied evaluation with real ROS2/Isaac evidence and formally specified safety postconditions.
**Threat:** simulator-reality gap, benchmark gaming, annotator leakage, corrupted sensor clocks, incomplete provenance, unmeasured energy/cost and misleading positive results.

## Reporting contract

Public reports should include the exact task manifest digest, dataset licence and provenance, code commit, model provider/weights, policy and harness versions, hardware, sensors, seeds, configuration, runtime settings, trial log hashes, invalid or aborted runs, verifier version, metrics with denominators, confidence intervals and independently witnessed certification limits.

*References are listed and linked in README.md. The user-provided research prospectus informed the scientific objective; its newer bibliographic claims have not been treated as independently verified peer review.*
