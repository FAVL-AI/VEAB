# Reproducible example evidence

`warehouse-verified.json`: one complete deterministic toy-world trial: route planner, seed 17, safety gate ON; contains scenario, event hashes, trajectory, and locally verified report. Check using `python -m veab verify examples/warehouse-verified.json`.

`60-trial-summary.json`: a 5-scenario × 3-seed × 2-policy × 2-gate-factor demonstration generated with `python -m veab suite --seeds 0 1 2 --split all`. This dataset illustrates method plumbing, not held-out, statistically established, hardware-realistic or SOTA performance. The seeds cover only synthetic perturbations of known tasks; no contamination control is in place.
