# VEAP R1.2 — Assumption-sensitivity software experiment

**Hypothesis:** With identical available observations and a valid stated model, relaxing the assumed speed or position-error bound cannot generate new definitive compliance/violation knowledge from an inconclusive verdict. The evaluator's certificate must be independently checked under each assumption set.

## Protocol

- Source: 15 **author-authored** VEAP synthetic R1.1 fixtures.
- Intervention: four declared speed multipliers `[1, 1.25, 1.5, 2]`, three assumed bounded pose errors `[0, 0.02, 0.06]` metres.
- Design: 15 × 4 × 3 = **180 correlated software-control cases**, no independent robot scenes.
- Comparator: existing separate standard-library reachability monitor, not organisationally independent.
- Reference check: independently recompute each certificate's obligations with a separate checker.
- Error flags: VEAP/monitor disagreement, checker failure, unsupported source-authenticity claim, or new definitive verdict after relaxed assumptions on internally consistent fixtures.
- Initial results (2026-11-14): `COMPLIANT=21`, `INCONCLUSIVE=111`, `VIOLATING=48`; **0** monitor disagreements, **0** failed certificate checks, **0** assumption-monotonicity failures.

These results are exploratory *development controls*, not a confirmation of scientific novelty or accuracy on independent robot recordings. Relaxed assumptions should sometimes increase abstention; an increase in inconclusive decisions does not itself demonstrate superior grading. The study does not authenticate sensors or establish the physical truth of declared bounds.

## Reproduction

```bash
cd veap_evidence_r1_1
python -m unittest discover -s tests -q
python -m scripts.run_r12_assumption_sensitivity --out artifacts/r12_assumptions.json
```

## Failure response

Any mismatch must be investigated before accepting the release. Preserve the offending fixture, versioned contract and resulting certificate; do not discard a failed case as an outlier. New purported scientific advantages must be tested against existing strong reachability monitors on independently authored scenes and measured effort, not extrapolated from this grid.

## Confirmatory experiment — NOT RUN

1. Preregister externally authored scene families and the intended operating context.
2. Calibrate and independently verify motion, frame, clock and observation uncertainty bounds.
3. Compare VEAP certificates with a strong runtime-verifier implementation, competent task-specific scripts and blinded human reviewers.
4. Measure false-compliant, false-violating, unnecessary-inconclusive, correct-inconclusive and explanation-checking rates, plus human review time.
5. Analyse by independently authored scene as the statistical unit, not translated seeds/trace variants.
6. Publish negative, tied and adverse findings alongside positive results.
