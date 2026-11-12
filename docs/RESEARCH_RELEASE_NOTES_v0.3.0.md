# VEAB v0.3.0 — research validity increment (11 Nov 2026)

## Implemented

1. **Paper-to-feature traceability:** verified source status and canonical references in `LITERATURE_TO_ENGINEERING_MATRIX.md`.
2. **Experimental audit:** source-row types, duplicate-trial detection, scenario-hash agreement across matched arms, and explicit scene/seed counting.
3. **Process-versus-outcome analysis:** task success, verified task success, unsafe task-complete traces, reported violations per 1,000 simulation steps, kinematic energy proxy and fault-recovery proxy. Distinguishes scene units from nominal trial-row count.
4. **Exploratory scenario-cluster analysis:** deterministic bootstrap by unique scenes and two-sided sign-flip diagnostic. Not confirmatory inference.
5. **Evidence attack regression:** four unkeyed post-hoc edits rejected; separately demonstrates that fully rehashed spoofed observations can still appear verified if capture custody is untrusted.
6. **Optional fail-closed HMAC:** `veab verify --require-attestation` refuses unsigned/unverifiable bundles even when ordinary development mode would permit them.
7. **Prospective protocol:** a frozen-study template for blinded independent scene families, ground-truth adjudication and native simulator/robot acceptance gates.

## Executable commands

```bash
python -m pytest -q
python -m veab research-analyse examples/60-trial-summary.json --out artifacts/research/process-analysis.json
python -m veab research-run --seeds 0 1 2 --split all --out artifacts/research/reexecuted-factorial.json
python -m veab tamper-audit --out artifacts/research/tamper-audit.json
# Require an externally held VEAB_ATTESTATION_KEY before accepting a signed bundle:
VEAB_ATTESTATION_KEY='key-from-secure-environment' python -m veab verify --require-attestation artifacts/signed.json
```

## Interpreting the development data

In the 60-row fixed demonstration dataset (five public scenes × three seeds × four arms), the gated and ungated greedy arms each report 12/15 task completions. The ungated arm has 3/15 verifier-accepted completions and 147 recorded geometric violations across trial rows; the gated arm has 12/15 verifier-accepted completions and no recorded geometric violations. **The 15 trials are not 15 independent scenes.** These are five environments repeated under three seeds that may produce identical paths. The scene-level sign-flip diagnostic is **p=0.25** (exploratory); no generalized or statistically substantiated SOTA claim follows.

The tamper regression identifies the crucial difference between **tamper evidence** and **original-source authenticity**. Recomputing all unkeyed hashes after spoofing an observation can preserve a valid-looking verification report. Trusted capture and external key custody remain research/deployment requirements.

## Not implemented / not established

Native Isaac Lab, MuJoCo, Gazebo and Unreal execution have **not** been run or validated in this build environment. v0.2 interchange assets, CAD STEP/STL surrogate parts and simulator hooks remain included. No real robot, contact safety proof, trained VLA baseline, independent ground-truth sensor, human label validation or enterprise production security is claimed. No physical energy in Joules has been measured.
