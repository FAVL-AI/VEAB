# VEAP R1.3 Comparator Register

**Scope:** Registered evaluators executed by `r13/blinded_runner.py` under identical blinded inputs (`veap.r13.evaluator_bundle/1`).

---

## 1. Registered Evaluators

| Evaluator ID | Implementation | Uncertainty / Missing-Data Semantics | Certificate Emitted |
|---|---|---|---|
| `veap` | `veap_evidence.verdict.evaluate` | Continuous bounded-speed reachability envelope over `[mission_start_s, mission_end_s]` + deadline epistemic ball | **Yes** (`veap.evidence.sufficiency/1` with witness refs & uncovered windows) |
| `separate_reachability_monitor` | `external_monitor.monitor.independent_verdict` | Independently coded endpoint-scan reachability monitor under identical declared motion assumptions | No standalone certificate (acts as independent verifier via `monitor.inspect`) |
| `gap_aware` | `veap_evidence.baselines.grade(..., "gap_aware")` | Abstains (`INCONCLUSIVE`) whenever any inter-sample interval exceeds nominal `max_gap_s`, regardless of clearance | No |
| `sampled_safety` | `veap_evidence.baselines.grade(..., "sampled_safety")` | Checks keepout distance only at discrete retained samples; ignores unobserved inter-sample intervals | No |
| `terminal_safety` | `veap_evidence.baselines.grade(..., "terminal_safety")` | Checks goal reachability and keepout clearance only at the final sample | No |
| `goal_only` | `veap_evidence.baselines.grade(..., "goal_only")` | Checks only terminal goal reachability at deadline | No |

---

## 2. Empirical Separation Across the Four R1.3 Conditions (30-Scene Pilot)

| Evaluator | Cond A (Complete) | Cond B (Intrusion) | Cond C (Critical Omission) | Cond D (Irrelevant Omission) | Overall Accuracy | False Decisive Rate | Unnecessary Abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| `veap` | 100.0% | 100.0% | 100.0% | 100.0% | **100.0%** | **0.0%** | **0.0%** |
| `separate_reachability_monitor` | 100.0% | 100.0% | 100.0% | 100.0% | **100.0%** | **0.0%** | **0.0%** |
| `gap_aware` | 100.0% | 100.0% | 100.0% | 0.0% | 75.0% | 0.0% | 33.3% |
| `sampled_safety` | 100.0% | 100.0% | 0.0% | 100.0% | 75.0% | 25.0% | 0.0% |
| `terminal_safety` | 100.0% | 0.0% | 0.0% | 100.0% | 50.0% | 50.0% | 0.0% |
| `goal_only` | 100.0% | 0.0% | 0.0% | 100.0% | 50.0% | 50.0% | 0.0% |

### Scientific Interpretation
1. **`veap` vs `separate_reachability_monitor`:** Preserves the exact tie (`120/120`) on three-valued verdicts. Both implement sound bounded-speed reachability semantics under shared assumptions. VEAP's distinct contribution is the **independently checkable certificate** (`100%` verified by `r13/certificate_audit.py`, localizing review to `57.2%` of trace samples on average).
2. **`veap` vs `sampled_safety`:** `sampled_safety` commits `30/120` (`25.0%`) false-compliant verdicts on Condition C because it fails to account for possible keepout intrusion during unobserved intervals near the boundary.
3. **`veap` vs `gap_aware`:** `gap_aware` commits `30/90` (`33.3%`) unnecessary abstentions on Condition D because it flags every recording gap $> \text{max\_gap\_s}$ as `INCONCLUSIVE`, even when the robot is far enough from the keepout zone that intrusion is physically impossible under `max_speed_mps`.
