# Applying the upstream Agentic Benchmark Checklist (ABC) to VEAP R1.1

**Source:** Zhu et al., NeurIPS D&B 2025. Frozen upstream `uiuc-kang-lab/agentic-benchmarks@ae1124758098876db04336e1d8c6e419a139c6e3`, `ABC.md`. This is VEAP's **self-assessment**, *not* a reproduction of the paper's ten benchmarks or flaw studies.

| ABC aspect | VEAP R1.1 evidence | Status |
|---|---|---|
| I. Outcome validity — accurate grading | Author-labelled synthetic trace cases, independent rule monitor, constructive ambiguity witness | Software demonstration; **not independently adjudicated** |
| I.d / I.e. Unit, end-to-end and adversarial testing | 63 local regression tests, rehashed altered certificates and invalid world paths | Demonstrated for specified code invariants |
| I.f. Deterministic execution | Exact same input canonical digests and sequential study runner | Demonstrated on local deterministic runtime only |
| I.g. State matching and nontrivial challenge | Continuous exclusion region, terminal goal, partially observed intermediate states | Partial; no general solver or broad task coverage |
| II. Tool versions and access | Standard-library Python R1.1; upstream code SHA pins | Partial; OS/container lock and third-party reproducibility pending |
| II. Environment reset and leakage | Evaluator input directory separate from reference-only truth; no physical instrumentation | Partial; no independent dataset audit |
| II. Reference/oracle validity | Six author-defined conditions and 16 rigid translations | **External ground truth and scene independence missing** |
| II. Benchmark exploitation resistance | Tampered certificate/hash and false-success controls | Narrow synthetic attack coverage |
| III. Source/harness transparency | R1.1 source/tests/scripts and machine-readable evidence artifacts | Provided in local source package |
| III. Contamination/holdout | Six author-defined cases only, no hidden independently authored test set | **NOT SATISFIED** |
| III. Statistical significance | Correlated stress cases; descriptive counts only | **Not claimed** |
| III. Non-AI and human baselines | Goal-only, sampled-safety and gap-aware scripts; separate reachability monitor | Human review **NOT RUN** |
| III. Flaw reporting | Known source-authenticity, assumption-validity and non-independence limitations | Explicitly reported |

## Upstream replication (required; not executed)

The EAI repository specifies VirtualHome and BEHAVIOR environments with goal interpretation, subgoal decomposition, action sequencing and transition modelling (eight cells). Reproducing these requires the original Python 3.8 environment and datasets, evaluation commands and preserved baseline results; none were executed in R1.1.

ABC publishes ten source-assessment YAML files and distinct flaw-reproduction workflows. Reproduce original analyses **before** adding VEAP's layer; no such runs were performed in R1.1. Retain failure logs, dependency hashes, original reference metrics and all deviations. See `docs/REPRODUCIBILITY_MATRIX.md` and `artifacts/upstream_protocol.json`.
