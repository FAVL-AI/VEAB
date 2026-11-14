# VEAP R1.1 → R1.2 prospective confirmatory design (not registered)

**Proposed hypothesis H1:** For independently authored embodied-navigation scenarios with partial and noisy recording conditions, adding checkable evidence-sufficiency certificates to an abstaining evaluation method reduces independently adjudicated unjustified compliance/violation claims and/or human review effort relative to an established uncertainty-aware runtime monitor **at a matched abstention rate**.

**H0:** No improvement versus the strongest valid reference monitor or reproducible task-specific script.

## Experimental design and controls

1. **Sampling unit:** independent scene/task family and recording configuration. Seeds and rigid translations are repeated measures, never independent scenes. Size determined by a prespecified power study using pilot variance (initial operational target: ≥30 independent scene families, subject to design review).
2. **Reference evidence:** a separate, time-synchronised measurement source with calibration and limitations; cannot be obtained only from the same simulator internals as the monitored agent. Preserve full reference recordings, subject to access controls, and do not reveal them to the evaluator.
3. **Evidence interventions:** randomly allocated, prespecified critical occlusions, irrelevant camera dropout, clock shifts, topic omissions, action/pose contradictions, and fault-recovery intervals; hide full trace from all graders.
4. **Fair comparators:** goal-only as a sanity baseline; strong safety-aware terminal and gap-aware scripts; independently implemented uncertainty-aware temporal/reachability monitor; task-specific scripts; blinded manual-review workflow with synchronized multimodal replay. Use same evidence, contracts, permitted sensor metadata and budgets.
5. **Verdict vocabulary:** requirement-scoped `COMPLIANT`, `VIOLATING`, `INCONCLUSIVE`. Source truth and what is knowable from the available observations are different labelled axes.
6. **Assumption checks:** estimated upper bounds on speed and position error, TF validity, clock drift and sensor capture integrity. If an assumption is contradicted, do not claim positive physical compliance from its certificate.
7. **Checker:** separately written implementation with hashed contract/trace references. A separate physical reference or accredited external auditor is required before calling the experimental outcome independently validated.
8. **Training/held-out governance:** public development trials, frozen preregistered comparator configuration, independently authored blinded test scenes, versioned software and sealed scoring code. Never tune thresholds on held-out labels.

## Primary endpoints

- Unjustified `COMPLIANT` decisions per 100 epistemically indeterminate/violating trials.
- Unjustified `VIOLATING` decisions per 100 epistemically compliant/indeterminate trials.
- Correct `INCONCLUSIVE` versus unnecessary abstention, with coverage/abstention curves.
- Valid certificate fraction and checker false-acceptance under tampering.
- Median and tail human review time, with blinded repeated review and accuracy constraints.
- Evaluable trial fraction and cost per correctly justified verdict.

## Statistical analysis

Use paired, scene-clustered analysis with confidence intervals; report denominators separately. Predeclare effect-size threshold, acceptable false-decisive rate and review-time non-inferiority threshold after external pilot data. Do not pool many frames or seeds as independent trials. Report whether certificate generation/checking increases latency and operational cost. Apply correction or hierarchical modelling when testing several primary endpoints.

## Negative controls and failure policy

- An observed overlap must remain `VIOLATING` despite unrelated missing evidence.
- Missing evidence irrelevant to the rule must not force `INCONCLUSIVE`.
- A missing critical interval with both safe and violating admissible completions must not be called `COMPLIANT`.
- Rehashed forged evidence lacking trusted capture must not be declared authentic.
- A reported speed bound contradicted by observations invalidates conditional proof.
- Missing mandatory events must appear in the evidence completeness report.

If the reference implementation matches or beats VEAP on verdict accuracy and explainability, report the tie/loss. No production, SOTA, hardware safety certification, or unrestricted safety claim may be inferred.

## Integration order

First, use synthetic controlled partial traces with external checkers. Second, ingest real MCAP/ROS 2 recordings **from a qualified evidence collector**. Third, calibrated Isaac Lab ↔ MuJoCo cross-engine tests. Fourth, independent supervised physical trials. Do not collect new on-device Yahboom recordings until the known Jetson EXT4 integrity fault has been remediated and the evidence recorder qualified.
