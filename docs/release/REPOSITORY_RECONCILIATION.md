# GitHub repository reconciliation before VEAB v0.6 release

**Observation, 12 Nov 2026:** The connected `FAVL-AI/VEAB` GitHub repo defaults to `main`, exposes `veab/adapters/{isaac_lab,mujoco}.py`, `backend/{cpp_engine,go_orchestrator,rust_verifier}`, and has a v0.1.0 `pyproject.toml` / README heading. It does not contain the v0.4 assurance or v0.5 Studio paths in the main-branch tree inspected here.

**Current GitHub connector permission:** read/pull true; push false. No branch/PR/issue/commit was created by this delivery.

**Source of the patch:** the available standalone v0.5 Studio snapshot bundled in this conversation. This snapshot is not a substitute for comparing the current local 105-test tree with GitHub `main`.

## Non-destructive integration sequence (user workstation)

```bash
cd /path/to/local/VEAB
# first: protect your existing local edits
git status --short
git rev-parse HEAD
git switch -c feat/locked-native-replay-v06

# Extract VEAB_v06_Additive_Patch.zip into a separate directory.
# Review file paths before copying. The patch contains only NEW files.
python /path/to/extracted/v06_additive_patch/scripts/check_v06_base.py --root .
# STOP if nonzero: public main lacks prerequisites; merge v0.5 first.
rsync -avn /path/to/extracted/v06_additive_patch/ ./
rsync -av /path/to/extracted/v06_additive_patch/ ./

python -m pytest -q tests/test_locked_replay_v06.py tests/test_claims_v06.py
python scripts/check_claims.py
git diff --check
git status --short
# Run the local full suite and native builds before any release PR.
```

The optional full-source archive is a self-contained reference snapshot and **must not be copied over** your native repository, as it may overwrite newer source or local credentials. Review any filename collision and stop for manual reconciliation. The package includes no Git history.

Before a release tag, reconcile version strings, licenses, branch protections, secrets, SBOM, product-specific risk scope, CI evidence and reviewer sign-off. Do not publish a tag from a tested ZIP alone.

**Operational decision:** published main lacks prerequisite Studio and simulation source; do not apply v0.6 without first reconciling newer local worktree and confirming preflight.
