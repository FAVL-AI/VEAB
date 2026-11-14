# VEAP R1.3 Prospective Protocol — Independently Checkable Evidence-Sufficiency Certificates

**Status:** Development pilot harness implemented (`veap_evidence_r1_1/r13/`); external held-out authoring pending.  
**Date:** 14 November 2026

---

## 1. Research Title & Positioning

**Title:** *VEAP-R1.3: Independently Checkable Evidence-Sufficiency Certificates for Embodied-Agent Evaluation*

### Literature Boundary
Prior runtime verification literature—specifically Bauer et al. (2011) on three-valued semantics (`10.1145/2000799.2000800`), Taleb, Hallé, and Khoury (2023) on uncertainty and incomplete traces in runtime verification (`10.1016/j.cosrev.2023.100594`), and symbolic runtime verification under uncertainties and assumptions (`10.1016/j.infsof.2025.108004`)—already establishes monitoring over partial or uncertain observations. **VEAP does not claim to be the first system to reason about incomplete evidence.**

Instead, R1.3 tests whether **requirement-linked, independently checkable evidence-sufficiency certificates** reduce unsupported decisive verdicts or localize human audit effort compared with existing uncertainty-aware monitors and task-specific checking workflows under matched observation conditions.

---

## 2. Hypotheses

- **Primary Hypothesis ($H_1$):** Under matched observation traces, requirement contracts, and explicit motion assumptions, VEAP's requirement-linked evidence certificates (a) eliminate false decisive verdicts when critical observations are omitted, (b) avoid unnecessary abstention when omitted observations do not affect requirement decidability, and (c) localize human verification to a bounded subset of witness observations or unresolved time windows with 100% independent certificate checkability.
- **Null Hypothesis ($H_0$):** VEAP provides no measurable improvement in verdict accuracy, false-decisive control, or certificate checkability over a strong reachability monitor (`separate_reachability_monitor`) or standard gap-aware checking workflows.

---

## 3. Four-Condition Experimental Design ($N$ Scenes $\times$ 4 Conditions)

The primary unit of generalisation is the **independently authored navigation scene** ($s \in \{1, \dots, N\}$). Each scene generates four blinded observation conditions:

| Condition Code | Ground-Truth Reference | Expected Verdict | Scientific Role |
|---|---|---|---|
| `A_COMPLETE_COMPLIANT` | Complete safe trajectory reaching goal | `COMPLIANT` | Baseline sensitivity to valid compliant execution |
| `B_ESTABLISHED_INTRUSION` | Keepout-zone penetration with observed sample | `VIOLATING` | Recall on genuine safety violations |
| `C_CRITICAL_OMISSION` | Observation drop near keepout boundary where compliance cannot be proven | `INCONCLUSIVE` | False-decisive control under critical missing evidence |
| `D_IRRELEVANT_OMISSION` | Observation drop far from keepout exceeding nominal `max_gap_s`, where reachability still proves compliance | `COMPLIANT` | Protection against unnecessary abstention |

---

## 4. Blinded Reference Isolation & Anti-Contamination Controls

1. **Separated Schemas:** Evaluator inputs (`veap.r13.evaluator_bundle/1`) contain only opaque `case_id`, `scene_id`, `contract`, `trace`, and `input_sha256`. Reference labels (`veap.r13.sealed_reference/1`) are stored separately and bound by `evaluator_bundle_sha256`.
2. **Fail-Closed Leakage Guards (`r13/study_schema.py` & `r13/blinded_runner.py`):**
   - Any forbidden key (`expected_verdict`, `ground_truth`, `condition_code`, `oracle`, etc.) or condition-revealing `case_id` substring immediately raises `ReferenceLeakageError`.
   - Any reference file in the evaluator workspace or forbidden environment variable (`VEAP_R13_REFERENCE_PATH`, `VEAP_REFERENCE_ORACLE`) immediately raises `ReferenceIsolationError`.
3. **Scene Independence Audit (`r13/split_integrity.py`):**
   - Rejects duplicate observation traces across cases.
   - Computes translation-normalized scene geometry and displacement signatures relative to the initial pose and keepout origin, rejecting rigid-translation copies across distinct `scene_id` clusters.
4. **Frozen Submission Verification (`r13/reference_scorer.py`):**
   - Evaluators emit a hash-sealed submission (`veap.r13.submission/1`) before scoring. Any post-hoc mutation invalidates `submission_sha256`.

---

## 5. Prospective Acceptance KPIs & Power Analysis

| KPI | Target | Pilot Harness Result (30 scenes / 120 cases) |
|---|---|---|
| False decisive verdict rate | $\le 5\%$ with 95% Wilson CI | `0.0%` (`0/120`, 95% Wilson CI `[0.0%, 3.10%]`) |
| Conclusive certificate verification | `100%` checkable by `external_monitor` | `100.0%` (`90/90` conclusive, `120/120` total) |
| Appropriate abstention (Condition C) | `100%` recall on critical omission | `100.0%` (`30/30`) |
| Unnecessary abstention (Condition D) | Report vs `gap_aware` comparator | `0.0%` for VEAP vs `33.3%` (`30/90`) for `gap_aware` |
| Data leakage & split integrity | Zero reference leaks; zero translated scene copies | `PASS` |

### Confirmatory Sample Size (`r13/statistics.py`)
Using scene clusters as the independent unit of analysis (`alpha = 0.05` two-sided, `power = 0.80`, assumed scene-level paired difference $\sigma = 0.25$, minimum detectable effect $\Delta = 0.10$ with a 15% non-parametric buffer), the prospective confirmatory study requires **$N = 57$ independently authored scenes** ($228$ condition evaluations).
