# VEAP R1 — Evidence-Sufficient Embodied Evaluation

## Research claim hierarchy

**Question (prospective, not validated):** Can an evaluator distinguish robot execution that is compliant with *specified requirements*, demonstrably violating those requirements, or inconclusive because evidence is insufficient, while producing an independently checkable explanation?

**No novelty claim yet:** Three-valued runtime verification (Bauer et al. 2011), verification of incomplete signals (Taleb et al. 2023; symbolic RV 2026), ROS/ROS2 requirement monitoring (Perez et al. 2022; ROSMonitoring), EAI's fine-grained evaluation (Li et al. 2024), and ABC's benchmark validity analysis (Zhu et al. 2025) are existing contributions. R1 proposes to study ***requirement-specific sufficiency certificates***, measurement-aware abstention, replayability, and checking of explanations from *recorded robot runs* under these existing conceptual foundations.

## Exactly which requirements are evaluated?

1. `G (not footprint_intersects(keepout))` over an **externally declared finite mission window**. Continuous-time safety is inferred conservatively from pose samples using *assumed* bounded translational speed and positional error. A sample can prove a violation when the robot footprint must overlap the region even after applying the stated error bound.
2. `at(mission_end, within_goal_tolerance)`. A pose sample before the deadline can certify terminal compliance only if the reachable envelope at the deadline is entirely within the goal tolerance. It can certify violation only if the envelope is entirely outside the tolerance.

Only axis-aligned 2D zones and circular robot footprints are supported. No LTL parser, dynamics model, robot control, real sensor authentication or accredited safety certification is included.

## Verdict semantics

- `COMPLIANT`: supplied observations, plus **externally justified** bounds, suffice to prove both specified requirements over their stated temporal scope.
- `VIOLATING`: at least one sufficient witness proves violation of at least one requirement. This **takes precedence** over unrelated missing observations.
- `INCONCLUSIVE`: neither compliance nor violation can be proved for at least one required condition. Include the exact unresolved time interval and requested evidence.

A missing camera message does **not** matter to a pose-based keep-out requirement that does not depend on camera data. A missing pose may also be harmless when a high-clearance measurement and the stated maximum speed exclude entering the zone during the gap. Conversely, a critical pose gap near an exclusion-zone boundary must not be silently interpolated.

## Sufficiency proof

If observed robot-centre location at time `t_i` is `p_i`, the position error bound is `ε`, robot footprint radius is `r`, maximum translational speed is `v`, and signed point-to-rectangle clearance is `d_i`, then a sufficient no-overlap time radius is

`R_i = max(0, (d_i - r - ε) / v)`.

If the union of intervals `[t_i - R_i, t_i + R_i]` covers the full mission window, continuous clearance is established **conditional on the bounds and the validity of the observations**. The sample-based sufficient violation condition is `d_i + ε < r` (entire allowed centre-error set intersects the rectangle with the robot footprint). A physics-level invalid speed bound, compromised source, wrong timestamp, or incorrectly reported coordinate frame can defeat this argument. There is deliberately no claim of unconditional safety.

## Independent checker

`external_monitor/monitor.py` is a separately implemented, standard-library-only process. It receives (1) contract JSON, (2) trace JSON, and (3) VEAP certificate JSON. It checks SHA-256 digests, ensures evidence references exist, independently calculates per-requirement verdicts, and reports mismatches. This is **implementation independence**, not organisational or metrological independence; it shares motion bounds, scene geometry and input provenance assumptions.

## What has been implemented?

- Versioned two-requirement contract and bounded JSON parsing
- Three verdicts with witness precedence and requirement-specific sufficiency
- Time-interval evidence-gaps (no silent path interpolation)
- Conservative speed/uncertainty reachability reasoning
- Differentiation between irrelevant and critical missing evidence
- Goal-at-deadline requirement
- Hash-linked source/contract/certificate identities (not digital signatures)
- Separately implemented checker for positive and negative verdicts
- Goal-only, terminal-safety, sampled-safety and gap-aware baselines
- Synthetic author-defined reference trajectories withheld from evaluator inputs
- CLI, tests and machine-readable reports

## Limitations requiring explicit disclosure

- No independent physical ground truth, blinded external human adjudication or real MCAP experiments.
- Speed/error bounds in synthetic examples are specified assumptions, not measured sensor calibration.
- Six illustrative cases are *not* statistically independent scenes or a generalisable sample.
- Both evaluator and checker rely on some shared modelling assumptions.
- Source digests detect changes; they do not authenticate the original acquisition.
- The checker compares semantic decisions and hash linkage; it is **not** a full formal proof checker.
- No comparison yet with reproduced ROSMonitoring, symbolic RV, or blinded Foxglove-assisted workflows.

## Publication pathway

Submit a confirmatory paper only after a preregistered held-out experiment with separately authored scenes, external reference measurements, matched baselines, reviewer blinding, reproducibility controls, and a documented null-result policy. No SOTA, first-ever, hardware safety or production certification claim is currently supported.
