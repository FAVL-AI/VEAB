# VEAP-M3 Replay — Prospective research protocol (NOT preregistered)

**Date:** 2026-11-12
**Claim status:** Implementation candidate. Confirmation and independent validation pending.

## Hypothesis and 5W1H

- **Who:** VEAP evaluation team, blinded reference reviewers, external robotics/assurance partner (to be appointed).
- **What:** Does contract-conditioned replay reveal additional independently adjudicated safety- or evidence-relevant failures beyond terminal-only and safety-aware grading?
- **Where:** Identically controlled simulated indoor robot trajectories; subsequently ROSMASTER M3 Pro read-only recorded trials in a supervised test area.
- **When:** Following device topic audit, ethics/privacy review where applicable, frozen protocol and pilot calibration.
- **Why:** Goal success alone does not characterise trace completeness or safe recovery; however strong safety-aware evaluators may already capture physical violations.
- **How:** Compare matched evaluations against a reference monitor with separate capture and blinded independent adjudication.

## Hypotheses

**H1 (primary):** At matched false-positive rate, the process verifier identifies a higher proportion of independently labelled **evidence/recovery faults** than the strongest safety-aware terminal baseline under held-out conditions.

**H2 (secondary):** For independently labelled unsafe task-complete episodes, VEAP detects additional episodes not caught by a terminal-state-only grader. A strong safety-aware terminal grader is mandatory; the added-value claim may be null.

**H3 (secondary):** Diagnostic attribution is better than guessing failure causes from final success alone, using blinded causal labels and a separately measured confusion matrix. Candidate cause suggestions alone do not satisfy this hypothesis.

## Study design and controls

- Freeze task and robot configuration, scene-family boundaries, seed schedules, policy/harness versions, sensor calibration, recorder configuration and source digests.
- Use a scene/task family (not a repeated seed) as the generalisation unit. Calculate sample size from pilot scene-level variance and the preregistered minimum detectable effect; **30 scenes is an initial recruitment target, not an automatic power guarantee**.
- Use matched no-fault, sensor dropout and command delay conditions; add odometry drift only when a calibrated, independent position source exists.
- Compare (A) goal-only, (B) safety-aware terminal, (C) VEAP process contract, (D) separated monitor, and (E) blinded human reference. Report disagreements explicitly.
- Judge raw traces without revealing policy identity. Dual raters for a stratified sample; report Cohen's kappa or another predeclared inter-rater coefficient and resolve disagreements by an independent adjudicator.
- Record all null results and invalidated scenarios; do not replace failed scenes after seeing results.

## Primary and operational KPIs (targets, NOT achieved)

1. **Incremental sensitivity** over the best safety-aware comparator at fixed false-positive rate: target and minimum detectable effect fixed from pilot data before confirmatory collection.
2. **False rejection** on independently accepted valid episodes: initial design ceiling 5%, with 95% confidence interval.
3. **Evidence completeness:** report channel presence and timestamp continuity with unknown or inconsistent header clocks flagged, not silently accepted.
4. **Fault recovery classification:** sensitivity/specificity for bounded-time safe stop against an external timestamped position/velocity source.
5. **Cross-simulator reproducibility:** per-scene trajectory, contact and timestamp discrepancy with predeclared tolerances after calibration; deterministic CPU traces and GPU nondeterminism reported separately.
6. **Review efficiency:** paired median analysis time compared with analysts reviewing raw bags under matched case mix (product pilot only; not primary scientific endpoint).

## Threats to validity and limitations

- No agent-specific success claim can substitute for independent physical observation.
- A hash of a bag verifies bytes after capture, not authenticity of sensor data or the capture time.
- Rosbag receive timestamp, ROS header timestamps and external timebase are different quantities and may not be synchronised.
- MCAP metadata completeness does not prove semantic validity or true hazard avoidance.
- The independent implementation may share a faulty contract or compromised recording; independent implementation is not organisational independence.
- Coherent forged traces and faulty shared sensor calibration remain open attack classes.

## Falsification and publication policy

If process verification provides no improvement over the strongest baseline at the chosen false-rejection threshold, report a null result with CIs and examine which checks add overhead or false alarms. Publish independent test code, protocol, model/harness version manifests and non-sensitive, rights-cleared traces. Avoid raw patient or third-party identifying sensor images.
