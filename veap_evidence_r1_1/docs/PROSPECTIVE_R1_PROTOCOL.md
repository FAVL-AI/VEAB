# VEAP R1 — Prospective research protocol (not preregistered)

**Scientific target:** Correctness, sufficiency and cost of evaluating robot-recorded executions against defined requirements—not improvement of robot navigation or physical safety.

**Primary question:** Compared with a competent, abstaining, task-specific evaluator, can VEAP reduce erroneous compliance/violation decisions at a predeclared inconclusive-verdict rate, and provide reproducible explanations that a separate checker can validate?

**Why:** A conclusive label that is not justified by available data is worse than a transparent uncertain decision. The research must test whether such transparent uncertainty is materially useful.

**When/Where:** Initially offline, on RTX 4080 SUPER Ubuntu 22.04 with synthetic reference trajectories; then independently authored Isaac Lab/MuJoCo scenes; then controlled, stationary or supervised ROSMASTER M3 Pro recordings after NVMe filesystem integrity and sensor readiness are qualified. No autonomous hardware actuation in the initial evaluation.

## Hypotheses

- H1: Compared with a *credible* gap-aware or uncertainty-aware comparator, VEAP reduces the false-compliant rate for masked critical evidence at no more than 5% false-violation rate on valid, adequately observed runs.
- H2: VEAP reduces *unnecessary* inconclusive verdicts by demonstrating clearance with calibrated speed/uncertainty envelopes where gaps are semantically irrelevant.
- H3: A separately implemented checker confirms >=99% of certificate-to-evidence relationships under independently authored input fixtures, while identifying deliberate tampering and invalid source references.
- H4: Median review time for human engineers decreases by at least 30% compared with a baseline workflow, without reducing adjudicated decision accuracy. This is a target, not an observed outcome.

These are *candidate thresholds* to be finalised using pilot estimates before confirmatory enrollment. Do not use synthetic fixtures to select thresholds and then claim they were held out.

## Unit of generalisation and experimental factors

- Primary unit: **independently authored scene/mission**, not random seed or duplicated trace row.
- Preliminary author-generated fixtures: compliant, observed violation, missing critical pose, irrelevant camera gap, provably irrelevant pose gap, violation plus gap.
- Confirmatory design: independently authored held-out task/scene families with predeclared required zones, mission times and calibration; scene-clustered paired comparisons; sample-size determined by simulation/power analysis using pilot scene-level variance, not an arbitrary number of seeds.
- Controlled evidence ablations: drop pose near known critical event, drop irrelevant topic, truncate final recording, alter frame, reorder timestamps, increase positional uncertainty, violate declared speed model, forge a coherent observation.
- Blinded external adjudication: at least two competent reviewers for a prespecified subset, reference measurements separate from evaluator logs, inter-rater agreement reported (e.g. Cohen's kappa).

## Comparator set

1. Deliberately limited goal-only grader (sanity check, not primary baseline).
2. Strong sampled-safety checker.
3. Competent time-gap-aware checker with abstention.
4. Established runtime-monitoring approach (ROSMonitoring or a reproduced symbolic RV implementation), if feasible under matched contract semantics.
5. Human log review using any available observability software, including Foxglove if relevant (as a baseline only; VEAP has its own UI).
6. VEAP certificate-producing evaluator and its separate checker.

Do not claim a named third-party comparator has been tested unless its actual unmodified/reproduced implementation was run.

## Required outcome measures (report separately)

- **False compliance:** compliant verdict when reference has a proven requirement violation.
- **False violation:** violation verdict on independently compliant reference traces.
- **Correct inconclusive:** insufficient evidence when compatible full traces can differ in requirement satisfaction.
- **Unnecessary inconclusive:** evaluator abstains despite sufficient evidence or a conclusive bound under the common contract.
- **Certificate soundness:** correct references, hashes, requirement and interval justification; how often independent checker disagrees.
- **Latency and review cost:** per-trace evaluation time, memory, reviewer time; include abstention trade-off curves.

If an evaluator abstains on a truly violating run because the critical evidence was hidden, that is an **appropriate inconclusive** under the epistemic evaluation, not automatically a false negative. Reference truth (what actually occurred) and sufficiency oracle (what can be inferred from observation) must be kept distinct.

## Statistical plan and falsifiers

Report scene-clustered paired bootstrap confidence intervals or suitable paired tests. Compare false-compliant rates at a matched false-violation bound and report coverage. If the strong monitor ties or outperforms VEAP, report it. If independent checking identifies incorrect VEAP certificate claims, the relevant certificate mechanism fails acceptance. Avoid statements of statistical significance on the six authored demonstration cases.

## Failure and refinement log

- Initial toy-world method rejected every nominal recording gap: too conservative and not requirement-specific.
- Initial checker could reject obvious violations but could not independently check a positive verdict.
- Refined method uses bounded-motion continuous-coverage certificates and a separate implementation for positive and negative checks.
- Remaining challenge: declared speed and error bounds are not yet metrologically established in real robot data, nor are observations attested.

## Release gates

R1-G0: deterministic fixtures, input validation, tests and source-pinned upstream reproducibility plan.
R1-G1: six synthetic-case demonstration; no scientific novelty claim.
R1-G2: independently authored and labelled held-out scenes; strong external comparators; calibrated sensing; blinded reviews.
R1-G3: reproducible evidence of incremental decision value over a credible alternative with statistical uncertainty.
R1-G4: peer-reviewed publication and external independent reproduction (future goal).
