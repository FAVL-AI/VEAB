# VEAP R1.3 Evidence Register

**Date:** 14 November 2026  
**Module:** `veap_evidence_r1_1/r13/`

---

## 1. Implemented R1.3 Artifacts & Verification Controls

| Component | Path | Purpose | Status |
|---|---|---|---|
| Study Schema & Pilot Split | `veap_evidence_r1_1/r13/study_schema.py` | Separates `veap.r13.evaluator_bundle/1` from `veap.r13.sealed_reference/1`; generates 30 non-translated scenes $\times$ 4 conditions | Implemented & tested |
| Split Integrity Auditor | `veap_evidence_r1_1/r13/split_integrity.py` | Rejects duplicate traces and rigid-translation-equivalent scenes across `scene_id` clusters | Implemented & tested |
| Blinded Evaluator Runner | `veap_evidence_r1_1/r13/blinded_runner.py` | Enforces workspace/env reference isolation and emits hash-sealed `veap.r13.submission/1` | Implemented & tested |
| Certificate Auditor | `veap_evidence_r1_1/r13/certificate_audit.py` | Verifies 100% of conclusive certificates, witness citations, and localization fractions via `external_monitor` | Implemented & tested |
| Post-Submission Scorer | `veap_evidence_r1_1/r13/reference_scorer.py` | Verifies frozen submission digest, scores scene-cluster metrics, and checks R1.3 KPI gate | Implemented & tested |
| Scene-Cluster Statistics | `veap_evidence_r1_1/r13/statistics.py` | Wilson 95% CIs, paired scene-cluster bootstrap, exact sign test, and confirmatory power calculation ($N = 57$ scenes) | Implemented & tested |
| Pilot Execution Script | `veap_evidence_r1_1/scripts/run_r13_pilot.py` | Runs the 30-scene (120-case) blinded evaluation in an isolated workspace and writes `artifacts/r13_pilot_report.json` | Implemented & tested |

---

## 2. Explicit Validity Boundaries

- **Development Pilot Scope:** The 30-scene (`120`-case) dataset produced by `generate_r13_pilot_split` is a **synthetic development pilot** (`independent_external_authorship: false`, `physical_sensor_ground_truth: false`) designed to validate the sealed evaluation harness, split-integrity detector, reference-isolation guards, and certificate audit pipeline.
- **External Held-Out Requirement:** Claiming empirical confirmation of R1.3 requires replacing the development pilot inputs with externally authored, access-controlled navigation traces ($N \ge 57$ independent scenes per power analysis) where reference trajectories are held outside the repository.
- **Upstream Benchmarks:** EAI (`531c62f8df2cb392bdf1907923c76da41cad4fe6`) and ABC (`ae1124758098876db04336e1d8c6e419a139c6e3`) full upstream benchmark reproductions remain `NOT_RUN`.
