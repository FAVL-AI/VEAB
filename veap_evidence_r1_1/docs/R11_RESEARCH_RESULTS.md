# VEAP R1.1 — Constructive Evidence Ambiguity: Results and Limits

**Status:** Software mechanism demonstration, 14 November 2026. **Not a registered, externally validated or peer-reviewed benchmark.**

## Claim and falsifier

VEAP's R1.1 hypothesis is not that three-valued logic is new. It asks whether requirement-specific *evidence certificates* and witness-based ambiguity explanations are sound, repeatable and useful for recorded embodied-agent executions when observations are incomplete. A strong reachability-based monitor may match its decisions; this must be treated as a meaningful null result.

**Falsifier:** A separate checker finds a positive or negative claim that is unsupported under the stated bounded-speed and error assumptions, or a strong independent baseline generates equivalent explanations at lower evaluation/review cost.

## Design (who, what, when, where, why, how)

- **Who:** author-coded VEAP evaluator, a separate standard-library monitor, three simple author-implemented comparators. No external reviewers, hardware experiments or third-party algorithms were executed.
- **What:** finite-horizon navigation contract requiring exclusion-zone avoidance and terminal goal attainment, with three verdicts (`COMPLIANT`, `VIOLATING`, `INCONCLUSIVE`).
- **When:** frozen synthetic test run created on 14 November 2026. No earlier published benchmark results are reproduced.
- **Where:** local Python interpreter; no Isaac Sim, MuJoCo, Jetson or ROS 2 runtime invoked by this study.
- **Why:** distinguish a proven requirement failure from truly unresolved observations and unnecessary abstention.
- **How:** six author-defined conditions under 16 rigid scene translations (96 **correlated** test cases); independent checker re-evaluates every certificate. Six of the conditions involve different evidence interventions.

## Results (counts; do not infer significance)

| Method | Matches author-specified epistemic reference labels (n=96) |
|---|---:|
| VEAP certificate-producing evaluator | **96/96** |
| Separate, reachability-aware monitor | **96/96** |
| Goal-only (deliberately weak) | 48/96 |
| Sampled-safety heuristic | 80/96 |
| Gap-aware abstaining heuristic | 80/96 |

96/96 certificates passed the separate checker, and 16/16 constructive ambiguity pairs passed the independent path checker. **The two strong evaluators tie.** This experiment does not show a generalizable accuracy advantage or statistical improvement over established runtime verification.

### Constructive identification failure

For the available four pose samples `t={0,0.5,1.5,2.0}` seconds, the `0.5–1.5 s` interval contains no observed pose. Two piecewise-linear completions agree exactly at every retained observation and reach the goal at 2.0 s:

- **World A (safe):** travels along y=1.5 and never overlaps the exclusion zone.
- **World B (violating):** crosses `(1.0,0.0)` at t=1.0 s, violating the exclusion-zone requirement while respecting the synthetic 4 m/s speed bound.

Both are consistent with the available evidence; therefore neither `COMPLIANT` nor `VIOLATING` is justified from that partial record, absent extra evidence or stronger valid assumptions. The checker verifies path geometry, continuous segment-to-rectangle clearance, speed and observed pose consistency without importing the generator. This is **implementation-independent verification of the stated model**, not actual sensor authentication.

### Failed and adverse findings retained

1. A heuristic gap-aware monitor incorrectly abstains on a distant harmless pose gap: its extra abstention is not essential when motion bounds prove clearance. This does not establish superiority over a sound reachability monitor, which makes the same decision as VEAP.
2. A trajectory whose recorded claims are internally coherent may still be factually false. Rehashing cannot prove original telemetry truthful.
3. If the maximum-speed bound, positional uncertainty, clock alignment or frame transformation is wrong, a positive compliance certificate may be unsound for the physical world.
4. A generated scenario's translational copies are correlated. The 96 cases are not 96 independent task families and justify **no p-value, confidence interval or SOTA claim**.
5. Verification does not establish that the underlying data were captured by a trusted recorder or reviewed by an independent organisation.

## Scientific conclusion

R1.1 supports a narrower mechanism claim: under the stated assumptions, VEAP can produce checkable, source-linked justifications including constructive witnesses showing why a missing interval prevents deciding a specified robot execution requirement. The next research work is a powered comparison against *already capable* temporal/reachability monitors, source-linked manual-review workflows and blinded adjudication. A null result is admissible.

## Reproduction

```bash
python3 -m unittest discover -s tests -v
PYTHONPATH=. python3 -m scripts.run_r1_identifiability --transforms 16 --out artifacts/r1_identifiability/stress_report.json
PYTHONPATH=. python3 -m scripts.build_r11_viewer
# Open VEAP_R1_1_Offline_Identifiability_Lab.html in your browser.
```

Reproducible script inputs are in `veap_evidence/fixtures.py`, `veap_evidence/possible_worlds.py` and `scripts/run_r1_identifiability.py`; the monitor and pair validator have no imports from VEAP's evaluator module.
