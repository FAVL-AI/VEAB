# VEAB v0.3 · Literature-to-engineering traceability matrix

**Reviewed 11 November 2026.** This matrix establishes the provenance of engineering requirements. **Citing a paper does not constitute reproducing its results**; implementation status and experiment outcomes are deliberately separated.

## Supplied agent-evaluation reference corpus

| Source | Publication status and permanent identifier | Transferable method | VEAB implementation / next gate |
|---|---|---|---|
| Xie et al. (2024), **OSWorld** | NeurIPS 2024 D&B; DOI [10.52202/079017-1650](https://doi.org/10.52202/079017-1650); [proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/5d413e48f84dc61244b6be550f1cd8f5-Abstract-Datasets_and_Benchmarks_Track.html) | Executable evaluator and deterministic task setup | **Current:** scenario contracts and agent-independent postconditions. **Required:** cross-application (robot-harness) evaluator lifecycle checks |
| Zhou et al. (2024), **WebArena** | ICLR 2024; [official](https://proceedings.iclr.cc/paper_files/paper/2024/hash/4410c0711e9154a7a2d26f9b3816d1ef-Abstract-Conference.html) | Functional, realistic, interactive tasks | **Current:** benchmark scenarios; **required:** hidden physical-environment task families and realistic dynamic agents |
| Wang et al. (2025), **OpenHands** | ICLR 2025; [official](https://proceedings.iclr.cc/paper_files/paper/2025/hash/a4b6ad6b48850c0c331d1259fc66a69c-Abstract-Conference.html) | Distinguish model, tools, harness and environment | **Required:** frozen model/harness/tool identity, sandboxed action-runner plugins |
| Chen et al. (2025), **ScienceAgentBench** | ICLR 2025; [official](https://proceedings.iclr.cc/paper_files/paper/2025/hash/f12b4df26344f3be803c06b555252efe-Abstract-Conference.html) | Expert-validated tasks, executable results, cost and contamination checks | **Required:** blinded domain expert rubric, contamination audit, independent safety annotation |
| Zhu et al. (2025), **Establishing Best Practices in Building Rigorous Agentic Benchmarks** | NeurIPS 2025 D&B; DOI [10.52202/085713-5547](https://doi.org/10.52202/085713-5547) | Agentic Benchmark Checklist; task / reward / reporting validity | **Current:** duplicate and scene-digest rejection, source/sample-size disclosures; **required:** independent rubric validity study |
| Mohammadi et al. (2025), **Evaluation and Benchmarking of LLM Agents: A Survey** | ACM KDD 2025 **tutorial**; DOI [10.1145/3711896.3736570](https://doi.org/10.1145/3711896.3736570) | Evaluation objective/process taxonomy and enterprise concerns | **Required:** benchmark taxonomy and access control; not a novel embodied safety method |
| Guo et al. (2026), **From Question Answering to Task Completion: A Survey on Agent System and Harness Design** | [arXiv:2606.20683](https://arxiv.org/abs/2606.20683); peer-reviewed venue **not established** | Observe/context/control/act/state/verify; test scaffold effects | **Required:** independent configuration switches for model, memory, planner, tool middleware, safety gate |
| Cao & Yu, **Survey of Emerging Trends in LLM Agent Benchmarking** | DOI [10.1145/3784013.3784018](https://doi.org/10.1145/3784013.3784018), **2025 symposium metadata**, original publisher page not directly accessible in this audit | Background on coverage, metrics, costs and alignment | **Reference only** pending a primary bibliographic check; do not call it an A* full paper |
| Hong et al. (2026), **AgentActionBench** | [arXiv:2609.11117](https://arxiv.org/abs/2609.11117); NLPCC 2026 shared-task article; proceedings status **not independently confirmed** | Tool-level action recorder and paper-specific rubrics | **Current:** event ledger; **required:** instrumented control/observation/tool execution events and third-party rubric audit |
| Li et al. (2026), **AgencyBench** | **ACL 2026 main**; DOI [10.18653/v1/2026.acl-long.337](https://doi.org/10.18653/v1/2026.acl-long.337) | Long-horizon user-simulation, costs and judge rubrics | **Required:** duration, intervention, completion, token/tool cost; no 1M-token/90-call reproduction claimed |

## Essential embodied benchmarking comparators (must not be omitted)

| Source | Publication status | Required VEAB comparative study |
|---|---|---|
| Li et al. (2024), **Embodied Agent Interface: Benchmarking LLMs for Embodied Decision Making** | NeurIPS 2024 D&B; DOI [10.52202/079017-3188](https://doi.org/10.52202/079017-3188) | Validate error attribution beyond terminal success; compare EAI-style fine-grained error categories against VEAB |
| Li et al. (2025), **IndustryEQA** | NeurIPS 2025 D&B; DOI [10.52202/085713-3423](https://doi.org/10.52202/085713-3423) | Assess industrial hazard recognition and whether model perception errors propagate to unsafe action; note question-answer scoring is not closed-loop control validation |
| Mu et al. (2025), **RoboTwin: Dual-Arm Robot Benchmark with Generative Digital Twins** | CVPR 2025; [official](https://openaccess.thecvf.com/content/CVPR2025/html/Mu_RoboTwin_Dual-Arm_Robot_Benchmark_with_Generative_Digital_Twins_CVPR_2025_paper.html) | Model geometry and domain variation, independent manipulation validation and real-data comparison |
| Shukla, Tao & Su (2025), **ManiSkill-HAB** | ICLR 2025; [indexed proceedings](https://mlanthology.org/iclr/2025/shukla2025iclr-maniskillhab/) | Compare long-horizon task and safety-oriented demonstration filters under changing contact and object dynamics |
| Zhan et al. (2026), **SENTINEL** | Authors report NeurIPS 2026 acceptance; [authors' project](https://nu-ideas-lab.github.io/SENTINEL/) | Formal temporal-logic contract controls across semantic, plan and trajectory stages; **do not claim priority for multi-level formal verification** |

## Method-to-module mapping

1. **Executable benchmark validity (OSWorld/WebArena/ABC)** → `veab/spec.py`, `veab/verifier.py`, `veab/research/protocol.py`. Next evidence: independent scene-family holdouts and grading false-positive rates.
2. **Model–harness attribution (OpenHands/Guo)** → `veab/agents.py`, `veab/sim.py`, factorial experiment; next: model providers, memory/action budget and controller factorization.
3. **Process evidence (ScienceAgentBench/AgentActionBench)** → `veab/ledger.py`, `veab/research/attacks.py`; next: external action collector and witnessed telemetry.
4. **Safety and formal contracts (Embodied Agent Interface/SENTINEL)** → current geometric constraints in `veab/verifier.py`; next: bounded-time fault-response and formal temporal monitors verified independently.
5. **Physical validity (RoboTwin/IndustryEQA/ManiSkill-HAB)** → v0.2 multi-engine asset exporters, native adapter hooks; next: measured dynamics calibration, real ROS 2 / MCAP traces, sensor calibration and witnessed physical trials.
6. **Benchmark efficiency (AgencyBench/Mohammadi)** → timing and dimensioned kinematic energy proxy in current suite; next: hardware-counter Joules, wall-clock latency, token and communication budgets.

## Unsupported claims to avoid

- The present 2D physics surrogate **is not** Isaac Lab, MuJoCo, Gazebo or Unreal physics equivalence.
- `SHA-256` event chaining protects an internally coherent history against unsophisticated post-hoc edits, **not** against a source able to rewrite and rehash the full stream.
- "Independent" today means **agent-independent verification**; external custody, ground truth and independent implementation must be demonstrated separately.
- Peer-reviewed digital-agent evaluations are **methodological analogies**, not evidence that VEAB is state-of-the-art on robot safety.
