# VEAB — From Apparent Success to Verifiable Autonomy
## Consolidated Review and Canonical Platform Narrative

**Document status:** Canonical engineering narrative and research positioning for VEAB.
**Primary audience:** Robotics validation or safety-assurance engineers responsible for deployment decisions.
**Current classification:** Experimental benchmarking and execution-verification platform (prototype v0.1.0).

> **Core Definition:** VEAB is a **model- and harness-agnostic evaluation protocol** that jointly measures **task success**, **constraint violations**, **recovery**, **resource cost**, and **independently checkable evidence** under **controlled faults**.

---

### What the Actual Experiment Shows

The recorded experiment contains five toy-world scenarios, three seeds per scenario, two planning policies, and two safety-gate conditions (60 total trials):

| Configuration | Task completion | Verified completion | Safety violations |
|---|---|---|---|
| **Greedy, gate off** | 12/15 | 3/15 | 147 |
| **Greedy, gate on** | 12/15 | 12/15 | 0 |
| **Route, gate off** | 15/15 | 15/15 | 0 |
| **Route, gate on** | 15/15 | 15/15 | 0 |

*Source: Bundled VEAB v0.1.0 60-trial summary; deterministic simplified 2D simulation. Descriptive development results, not independent external benchmark results.*

#### The Core Narrative Anchor
**Nine of fifteen ungated greedy trials reached their task objectives but were rejected by the independent verifier because they violated safety constraints.**

This demonstrates a concrete, reproducible disagreement between task completion and verified completion within the current simulator. It does not yet demonstrate superior real-world safety or generalisation. It is a measurable engineering failure that can be reproduced, inspected, and used to establish the next research hypothesis.

Re-execution of the complete 60-trial suite confirms that all 60 trace digests and scenario digests match the bundled results, establishing reproducibility for this local software environment.

#### The Canonical Benchmark Separation Example (Agent A vs. Agent B)
Consider two candidate deployment policies evaluated across 100 trials:
- **Agent A (Fast & Fragile):** Reaches the goal in 90% of trials, but violates a keep-out constraint in 30% of runs, recovers from only 20% of actuator stall faults, and consumes $2\times$ baseline energy.
- **Agent B (Verified & Resilient):** Reaches the goal in 90% of trials, has 0 constraint violations, recovers from 80% of faults ($4\times$ recovery advantage), and consumes half the energy of Agent A.

| Evaluation Metric | Agent A | Agent B | Benchmark Verdict |
|---|---|---|---|
| **Conventional Final-Success Benchmark** | **90%** | **90%** | **EQUIVALENT ($\Delta = 0.0$)** |
| **VEAB Verified Completion** | **60%** | **90%** | **$\Delta = +30.0\%$ advantage for Agent B** |
| **Keep-Out Constraint Violations** | 30% | 0% | Agent A breaches critical safety boundaries |
| **Fault Recovery Rate** | 20% | 80% | Agent B has $4\times$ higher recovery resilience |
| **Relative Energy Consumption** | $2.0\times$ | $1.0\times$ | Agent A imposes double the mechanical/battery cost |
| **Deployment Recommendation** | **REJECTED (Unsafe)** | **VERIFIED CANDIDATE** | **Stark Operational Divergence** |

> **Conclusion:** A conventional success-only benchmark ranks them identically, obscuring catastrophic deployment risks. VEAB exposes the true multidimensional operational gap.

#### Scientific Clarifications
1. **No unrelated domain analogies:** VEAB does not invent catastrophes, fictional character conflicts, or irrelevant domain analogies.
2. **Tamper evidence vs. authenticity:** SHA-256 chaining provides tamper evidence against post-hoc modification; it does not guarantee immutability or physical sensor authenticity.
3. **Attestation status:** Optional HMAC signing is an existing implemented mechanism in v0.1.0. Enterprise identity, external key custody, and independently trusted attestation remain future work.

#### Formal Research Hypothesis
> **Hypothesis:** Under matched scenarios, seeds, and fault conditions, an evaluation architecture that jointly scores task completion, constraint violations, recovery behaviour, resource use, and trace-verifiable execution will identify reliability differences between agents that are not detectable using final task-success rate alone.

---

## The Nine-Stage Development Outline

### 1. Opening — The Success Score That Concealed a Failure
A robotics validation engineer must determine whether an autonomous agent is suitable for a defined operational task. Conventional task-success reporting provides part of the answer, but may not reveal the full execution history.

The VEAB warehouse-transfer demonstration illustrates the problem. In a deterministic 2D simulation, the ungated greedy planner completes the required task, yet the recorded trajectory contains 22 geometric safety violations. A task-completion indicator reports success; VEAB's independent verifier rejects the outcome.

The central question becomes: **Should completing the destination task count as success when the agent violates constraints along the way?**

### 2. Inciting Incident — The Executor Loses Authority Over Its Own Result
VEAB establishes a separation between execution and verification.

The execution system generates actions and observations. The independent trace-checking component examines recorded states, trajectory consistency, geometric constraints, scenario requirements and terminal postconditions.

Task completion is no longer sufficient to establish verified completion.

For the warehouse-transfer example, the verifier distinguishes reaching the required destination from reaching it while satisfying the modelled safety constraints.

The architectural principle is that claims must be supported by independently evaluated evidence, rather than accepted solely from an execution system's reported outcome.

### 3. Key Decision — Make Every Capability Claim Testable
The development programme commits to explicit task contracts, reproducible experiments, separated execution and verification components, fault injection, and controlled ablations.

Every claimed capability must have a measurable acceptance condition.

A benchmark result must identify the scenario, policy, safety configuration, random seed, software version, execution trace and verification result.

Unsupported claims remain unvalidated. Failed experiments are retained as research evidence rather than omitted from the results.

### 4. First Implementation — Building VEAB v0.1.0
The first implementation provides an integrated, local evaluation environment.

Its capabilities include five demonstration scenario contracts, greedy and route-planning baselines, an optional geometric safety gate, configurable disturbances, negative-target abstention, an evidence ledger, a trace verifier, a local REST API and an interactive isometric dashboard.

The system supports multi-seed experimental comparisons and records simulation trajectories for inspection.

The initial automated test suite contains 27 passing tests (extended to 65 with adversarial fixtures). The bundled 60-trial factorial experiment can be reproduced with matching deterministic trace digests.

The implementation establishes a working research foundation, but its physics and environmental assumptions remain deliberately simplified.

### 5. Midpoint — Task Success and Verified Success Diverge
The platform's first important experimental finding arises from comparing the same planning policy with and without its safety gate.

Across 15 ungated greedy trials, 12 reached their defined task objectives, but only three satisfied the verifier's full conditions.

Nine task-complete trials were rejected because of recorded safety violations.

With the geometric gate enabled, the greedy policy again completed 12 of 15 tasks, but all 12 completed tasks were verified without geometric safety violations.

For the warehouse-transfer scenario at seed zero, the safety-gated greedy policy completed with 22 safety interventions and no recorded violations, compared with 22 violations without the gate. The gated run required 83 simulation steps rather than 68.

This exposes a measurable trade-off between safety intervention and execution time.

The experiment supports a narrow conclusion: process-level evaluation changes how outcomes are classified in this simplified environment. It does not establish that the same effect will generalise to real robots.

### 6. Rising Challenges — Evidence Integrity Is Not Physical Truth
The development team must address limitations that cannot be solved through more elaborate dashboards or additional hash functions.

A hash-linked trace can support detection of changes to recorded data, but it cannot establish whether an external sensor originally measured the world correctly.

A verifier can check constraints against recorded simulator states, but those states may not faithfully represent physical dynamics, contact interactions, sensor uncertainty, actuation delays or real-world obstacles.

Similarly, a safety gate that enforces geometric conditions in a toy environment does not constitute a formally verified control-barrier safety controller.

These limitations define the next research problems: independent ground truth, trustworthy capture, simulator fidelity, sensor provenance, calibrated uncertainty and operationally meaningful safety conditions.

### 7. Critical Boundary — The Simulator Cannot Certify the Robot
VEAB v0.1.0 reaches its current evidence boundary.

It can demonstrate repeatable execution and trace checking inside its own deterministic simulator. It cannot yet establish reliable performance on physical robots or under realistic environmental disturbances.

Native Isaac Lab integration, authenticated ROS 2 and MCAP telemetry, real energy measurements, physical emergency-stop testing and external validation remain incomplete.

Public demonstration splits also prevent claims of contamination-controlled benchmark generalisation.

The correct engineering decision is to retain the prototype's demonstrated claims while withholding broader assertions about physical safety, enterprise readiness or state-of-the-art autonomy.

### 8. Decisive Scientific Test — Does Process Verification Add Independent Value?
The next research phase must test whether VEAB's additional evidence identifies important failures beyond a properly implemented outcome-only evaluator.

The study should use preregistered scenarios, controlled faults, independently labelled ground truth and strong reference baselines.

Agents and harnesses should be evaluated under matched task, sensor, tool and computational conditions.

The decisive measurements are incremental failure detection, false rejection rates, verified task completion, constraint violations, recovery behaviour and evaluation overhead.

If process verification fails to detect additional relevant failures, introduces unacceptable false positives or depends on privileged simulator information unavailable in deployment, those results must be published and used to refine the method.

Success would mean demonstrating a reproducible and independently substantiated evaluation advantage, not merely producing a larger collection of metrics.

### 9. Resolution — A Staged Path to Autonomous-System Assurance
The longer-term platform develops through controlled scientific and engineering milestones.

The next stage strengthens the verifier against adversarial traces and reporting errors.

The following stages introduce realistic Isaac Lab experiments, held-out scenario families, multiple external agent baselines, authenticated robotics telemetry and supervised physical trials.

Only after these stages satisfy their acceptance criteria should the programme progress towards enterprise workspaces, authenticated multi-user access, stronger attestation, scalable execution and formal deployment governance.

VEAB's intended contribution is an evidence infrastructure that allows developers and decision-makers to answer a precise question:

> **What can this autonomous agent demonstrably accomplish, under which conditions, with which safety and resource constraints, and with what independently checkable evidence?**

The objective is not to make every autonomous-system claim positive. It is to make every claim testable, traceable and appropriately limited by the evidence.

---

## Three-Paragraph Platform Narrative

**Beginning**  
VEAB begins with a problem in autonomous AI evaluation: reaching a goal is not equivalent to completing a task safely and reliably. A robot or autonomous agent may achieve its final objective while violating operational constraints along the way. Without examining the execution process, a success score may conceal failures that matter to researchers, engineers and deployment decision-makers. The first VEAB implementation demonstrates this distinction using deterministic navigation tasks and an independent trace verifier.

**Middle**  
The platform develops an evidence-first evaluation architecture in which task execution, safety intervention and outcome verification are separate components. Researchers can compare planning policies, inject disturbances, inspect actions and review recorded trajectories. Initial toy-world experiments reveal cases where task completion and verified completion disagree. This provides a concrete foundation for studying the value of process-level evidence. At the same time, development reveals limitations in simulated dynamics, sensor authenticity, benchmark independence and real-world transfer, requiring stronger experimental controls and realistic validation environments.

**End and Long-Term Direction**  
VEAB aims to evolve into a reproducible evaluation and assurance infrastructure for autonomous agents operating across simulation and physical environments. Its future development will require independent scenario validation, realistic robotics integration, trusted telemetry, measured operational constraints and controlled hardware testing. Rather than relying on impressive demonstrations or a single benchmark score, users should be able to inspect the evidence supporting an agent's claimed capabilities, identify unresolved risks and make informed deployment decisions. The central objective is to replace unsupported confidence with measurable, reproducible and appropriately qualified evidence.

---

## Primary Audience & Platform Classification

### Primary Audience
The primary decision-maker is the **robotics validation or safety-assurance engineer** responsible for determining whether an autonomous system satisfies defined operational acceptance criteria.

This professional must understand how an agent behaved, which requirements it satisfied, what failures occurred, whether those failures were recovered and whether the evidence can support a deployment decision.

Secondary users include embodied-AI researchers, robotics manufacturers, benchmark developers, independent evaluators and enterprise autonomy teams.

VEAB must earn their trust through transparent experimental methods, reproducible results, accurate failure reporting and clear distinctions between demonstrated capabilities and unvalidated claims.

### Platform Classification
- **Current classification:** Experimental benchmarking and execution-verification platform.
- **Longer-term classification:** Autonomous-system evaluation and evidence-assurance infrastructure.
- **Explicit exclusions:** VEAB is not presently a certified safety controller, a physical-robot assurance system, or an accredited conformity-assessment service. Benchmark success cannot replace the safety case and regulatory requirements of a particular deployment.

---

## Technical Scope & Engineering Focus Areas

The VEAB project focuses exclusively on **autonomous and embodied AI engineering**, structured across seven technical pillars:

1. **Simulation:** NVIDIA Isaac Lab, Isaac Sim, MuJoCo, Gazebo and Unreal Engine–quality 3D environments.
2. **Robotics:** ROS 2, robot control, navigation, manipulation and hardware-in-the-loop (HIL) testing.
3. **3D engineering:** CAD, OpenUSD, URDF, MJCF, SDF, digital twins and physically realistic environments.
4. **Agent intelligence:** Vision-Language-Action (VLA) and Vision-Language-Model (VLM) systems, world models, multi-agent orchestration and adaptive planning.
5. **Safety and verification:** Independent verification, runtime assurance, fault injection and reproducible evidence.
6. **SOTA benchmarking:** Cross-simulator evaluation, sim-to-real transfer, safety, reliability, latency and resource efficiency.
7. **Enterprise infrastructure:** Cloud deployment, experiment orchestration, observability, security and evidence provenance.

---

## Proposed Research Acceptance Gates

*These are proposed acceptance gates from the research programme, not completed milestones:*

| Research gate | Proposed measurable acceptance criterion | Status |
|---|---|---|
| **Verifier hardening** | At least 30 preregistered adversarial fixtures; 100% detection of the defined integrity-tampering cases | Delivered (37 fixtures in `tests/test_adversarial_fixtures.py`) |
| **Reproducibility** | Identical trace digests across repeated deterministic executions with the same pinned environment | Verified across all 60 trials in v0.1.0 |
| **Incremental diagnostic value** | Quantify additional true failures detected versus outcome-only evaluation, with false-positive rates | Active milestone deliverable |
| **Isaac Lab integration** | At least 20 replayable scenarios across two task families | Active milestone deliverable (contract) |
| **Baseline comparisons** | At least two external agents evaluated under matched observations and compute budgets | Open research gate |
| **Physical evidence** | At least 30 supervised trajectories with independently checked provenance, latency and safety observations | Open research gate |

