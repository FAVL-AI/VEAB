# Upstream replication and additive contribution matrix

Checked repository snapshot references on 14 November 2026. **Source pinning has been planned, not executed locally. Upstream published scores have not been reproduced.**

| Upstream study | What must be reproduced | Source revision | Current reproduction gate | VEAP additive layer |
|---|---|---|---|---|
| EAI: Embodied Agent Interface (NeurIPS 2024) | Both `VirtualHome` and `BEHAVIOR` with each of four ability modules (`goal_interpretation`, `subgoal_decomposition`, `action_sequencing`, `transition_modeling`), published prompt/dataset splits, reference outputs, exact evaluation scripts and parameter settings | `531c62f8df2cb392bdf1907923c76da41cad4fe6` | **NOT RUN**; Python 3.8/iGibson/PDDL/model data may require environment isolation | Recover trace-level evidence and assess requirements rather than just subtask labels |
| ABC: Rigorous Agentic Benchmarks (NeurIPS 2025) | Implement the complete outcome-validity, challenge-validity, and reporting checklists; retain all ten `assessments/*.yaml`; reproduce published flaw-patch experiments for tau-bench, Kernel-Bench, SWE-Lancer, WebArena, OSWorld, and any others specified by upstream; preserve exact upstream commits and baseline scores | `ae1124758098876db04336e1d8c6e419a139c6e3` | **NOT RUN**; these are external agent benchmarks and separate studies, not VEAP tests | Apply ABC items to VEAP itself, test evaluator false-positive and false-negative rates |
| Bauer et al. (2011) | Three-valued incomplete-trace semantics and early conclusive verdicts | Paper DOI `10.1145/2000799.2000800` | Literature verified; implementation reproduction **NOT RUN** | Requirement-linked evidence certificates for robot runs |
| Perez et al. (2022) | ROS 2 requirement-to-monitor workflow, FRET/Ogma stream-monitor pipeline | DOI `10.4204/EPTCS.371.15` | Literature verified; source reproduction **NOT RUN** | Posthoc evidence sufficiency with explicit insufficiency interval |
| Taleb et al. (2023) | Partial-trace uncertainty classification and methods | DOI `10.1016/j.cosrev.2023.100594` | Survey reviewed; not a runnable benchmark | Test when missing data is irrelevant versus decisive |
| Symbolic RV under uncertainties and assumptions (2026) | Symbolic monitoring of noisy/missing observations under assumptions | DOI `10.1016/j.infsof.2025.108004` | Literature reviewed; implementation reproduction **NOT RUN** | Compare conservative motion-envelope checking versus symbolic RV |

## EAI: eight required cells

| Environment | Goal interpretation | Subgoal decomposition | Action sequencing | Transition modeling |
|---|---|---|---|---|
| VirtualHome | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| BEHAVIOR | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

The EAI repo provides the `eai-eval` CLI, a Docker image, resources for VirtualHome/BEHAVIOR, and optional PDDL/iGibson setup. Use a dedicated Python 3.8 environment; do **not** mix it with Isaac Sim Python 3.11, MuJoCo 4 Python 3.13, or ROS 2 Humble environments.

## ABC: ten benchmark assessments

`bird-bench`, `cy-bench`, `gaia`, `kernel-bench`, `mle-bench`, `osworld`, `swe-bench`, `swe-lancer`, `tau-bench`, `webarena`. Their assessment YAML files have not been inspected or scored locally in this package. Preserve per-benchmark methods and versions; the original paper also contains exploit demonstrations and patches, not simply a checklist file.

## Parity requirements before saying “reproduced”

1. Pinned upstream commit and dependency/container digest, with platform details.
2. Original paper data versions, licenses, partitions and contamination risks accounted for.
3. Native upstream command exits successfully and produces its raw outputs.
4. Published metrics regenerated with uncertainty (or exact deterministic equivalence) under predeclared tolerances.
5. Discrepancies, failures and deviations reported, not silently repaired.
6. Original method and VEAP augmentation evaluated **separately** using the same original inputs.

Run `bash scripts/bootstrap_upstream_sources.sh` only on a suitable development machine with adequate space and internet, after reviewing downloads; not on the nearly full Yahboom Jetson. `python scripts/run_upstream_reproduction.py` only checks source layout and Git identity. It does **not** execute upstream benchmarks.

## Stronger adjacent work that narrows novelty further

- Luckcuck, Farrell, Ferrando, Cardoso, Dennis, and Fisher (2026), *A compositional approach to verifying modular robotic systems*, **Robotics and Autonomous Systems 205:105648**, DOI `10.1016/j.robot.2026.105648`: already provides ROS Contract Language, assumption–guarantee reasoning, Vanda monitor synthesis and an autonomous-rover case study. Reproduction artefacts are on Zenodo DOI `10.5281/zenodo.18273311`. This is a **mandatory comparator and replication target**, not an empty gap.
- *Symbolic runtime verification for monitoring under uncertainties and assumptions* (2026), DOI `10.1016/j.infsof.2025.108004`, already handles noisy or missing observations with symbolic assumptions. VEAP's bounded-motion certificate is a narrow engineering instance of this problem class; any claimed methodological novelty must explicitly compare semantics, soundness, evidence explanation and computation with symbolic RV.

The most defensible VEAP value proposition may be **measured usability, traceability, replay reproducibility and evaluation efficiency under real heterogeneous ROS 2 evidence**, not a new fundamental three-valued semantics.
