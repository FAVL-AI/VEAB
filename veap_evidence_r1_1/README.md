# VEAP R1 — Evidence-Sufficient Embodied Evaluation

A **standalone experimental VEAP research module**, designed to be integrated additively with VEAP after its local native worktree is reviewed. It does not modify robot controllers or actuators. It does not depend on Foxglove or the space-native AI chapter.

The implemented R1 proof-of-mechanism evaluates a specified continuous exclusion-zone requirement and a terminal goal requirement. It returns `COMPLIANT`, `VIOLATING`, or `INCONCLUSIVE`, with contract/trace hashes, evidence IDs and unresolved time intervals. A separate-process, separately implemented checker re-evaluates the contract and checks certificate linkage.

The core scientific contribution is **proposed**, not established: requirement-specific evidence-sufficiency certificates for recorded, potentially incomplete embodied-robot traces.

## Run (Python standard library only)

```bash
cd VEAP_Evidence_R1
python3 -m unittest discover -s tests -v
python3 -m veap_evidence demo --out artifacts/synthetic_comparison.json
python3 -m scripts.create_blinded_study
python3 -m scripts.evaluate_blinded_study
python3 -m scripts.score_blinded_study
```

To check user-supplied experiment input:

```bash
python3 -m veap_evidence check artifacts/r1_blinded_synthetic/evaluator_inputs/compliant/contract.json artifacts/r1_blinded_synthetic/evaluator_inputs/compliant/trace.json --out /tmp/veap-r1-cert.json
python3 -m veap_evidence verify-certificate artifacts/r1_blinded_synthetic/evaluator_inputs/compliant/contract.json artifacts/r1_blinded_synthetic/evaluator_inputs/compliant/trace.json /tmp/veap-r1-cert.json
```

`check` and `verify-certificate` receive ONLY the contract and available trace, never the separate reference-only high-rate truth. Physical sensor data cannot be authenticated by this prototype.

## Scientific provenance and reproduction

- EAI pinned source: `embodied-agent-interface/embodied-agent-interface@531c62f8df2cb392bdf1907923c76da41cad4fe6`
- ABC pinned source: `uiuc-kang-lab/agentic-benchmarks@ae1124758098876db04336e1d8c6e419a139c6e3`
- EAI eight cells (VirtualHome + BEHAVIOR × four ability modules): **NOT RUN**
- ABC ten source assessments + experiment reproductions: **NOT RUN**
- Real ROS 2/MCAP ingestion and external ground truth: **NOT RUN**
- VEAP synthetic mechanism checks: run locally; actual test counts and outputs are included in `artifacts/`.

See `docs/REPRODUCIBILITY_MATRIX.md`, `docs/SCIENTIFIC_SPECIFICATION.md`, `docs/PROSPECTIVE_R1_PROTOCOL.md`.

### Primary literature

- Li, M., et al. (2024). *Embodied Agent Interface*. NeurIPS D&B. DOI: `10.52202/079017-3188`.
- Zhu, Y., et al. (2025). *Establishing Best Practices in Building Rigorous Agentic Benchmarks*. NeurIPS D&B. DOI: `10.52202/085713-5547`.
- Bauer, A., Leucker, M., Schallhart, C. (2011). *Runtime Verification for LTL and TLTL*. ACM TOSEM. DOI: `10.1145/2000799.2000800`.
- Perez, I., et al. (2022). *Monitoring ROS2: from Requirements to Autonomous Robots*. EPTCS 371. DOI: `10.4204/EPTCS.371.15`.
- Taleb, R., Hallé, S., Khoury, R. (2023). *Uncertainty in runtime verification: A survey*. Computer Science Review 50, 100594. DOI: `10.1016/j.cosrev.2023.100594`.
- *Symbolic runtime verification for monitoring under uncertainties and assumptions* (2026). Information and Software Technology 191, 108004. DOI: `10.1016/j.infsof.2025.108004`.

No SOTA, novel-first, true sensor provenance, general safety or production qualification is claimed.

## R1.1 extension — Constructive identifiability and comparison

R1.1 adds two explicitly constructed *possible-world* trajectories that share the same observed pose samples and stated speed bound, but have different exclusion-zone compliance. A separate, stdlib-only checker validates exact interpolation at retained observations, every segment's velocity bound, continuous line/rectangle collision geometry and the goal-at-deadline. It rejects malformed or rehashed fabricated proof claims.

The extended deterministic study comprises 6 conditions × 16 *rigid coordinate translations* = **96 correlated synthetic software stress cases**. The author-defined epistemic reference labels and scores are recorded in `artifacts/r1_identifiability/stress_report.json`. A strong separate reachability monitor **ties** VEAP on all 96 cases, so the pilot does **not** demonstrate a new verdict algorithm or statistical superiority.

```bash
python3 -m unittest discover -s tests -v
PYTHONPATH=. python3 -m scripts.run_r1_identifiability --transforms 16
PYTHONPATH=. python3 -m scripts.build_r11_viewer
```

Open `VEAP_R1_1_Offline_Identifiability_Lab.html` for an original first-party visual explanation. It is a self-contained synthetic research explorer, **not** an enterprise telemetry dashboard or a live physical robot view.

Read `docs/R11_RESEARCH_RESULTS.md`, `docs/R11_CONFIRMATORY_PROTOCOL.md`, and `docs/ABC_APPLIED_TO_VEAP_R11.md`. EAI and ABC third-party replications remain **NOT RUN** and are explicit release blockers before claiming full parity or superiority.
