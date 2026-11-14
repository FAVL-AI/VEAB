# VEAP R1.3 — Publicly verifiable reference custody (additive protocol v1)

**Status:** locally tested software extension; not an independent human study, trusted timestamp, physical robot validation, or safety certification.
**Base repository reviewed:** `FAVL-AI/VEAP@7b0f17e36c3c039b30983166d4da1d5711ceddd1` (14 November 2026).
**Target:** `veap_evidence_r1_1/r13/public_custody.py`, complementary to the existing HMAC `r13/custody.py`.

## 1. Scientific motivation and precise limitation

The existing R1.3 development pilot uses HMAC-SHA256 receipts and disjoint directory checks. Those are legitimate development controls, but an independent reviewer must know the HMAC secret to verify them. A shared secret exposes signing authority to any verifier that receives it. Directory disjointness does **not** establish separate security principals, external authorship or trustworthy sensor readings.

This extension adds **Ed25519 public-key attestations** for (i) preregistration, (ii) exact submitted predictions, and (iii) the final checked score report. A reviewer verifies signatures with a pinned public key, never a private signing key. Its purpose is public verification of *which specific data bytes a keyholder signed*, not verification of a physical claim.

### Research hypothesis

*H1:* A third-party auditor given the public key, the preregistered evaluator input, the signed submission receipt and the published output can deterministically detect post-commit changes without accessing a custodian signing secret.
*H0:* The public attestation layer offers no additional role separation, auditability or review efficiency beyond a correctly managed existing mechanism. Demonstrating its functional cryptographic properties is not proof of improved human review outcomes.

## 2. Roles and information boundaries

| Role | Must have | Must not receive |
|---|---|---|
| Scene author | Scenario source and evidence; reference-generation procedure | Model submissions after hidden labels are fixed |
| Independent custodian | Reference vault, private Ed25519 key, random 32-byte nonce, published frozen input | Evaluator’s permission to change reference labels |
| Evaluator | Contract/trace `evaluator_bundle.json`, public key, signed preregistration | Reference, private key, nonce, scoring labels |
| Public reviewer | Trusted public key fingerprint, preregistration, receipt, input, prediction, signed score | Custodian signing secret |

**Real separation requires separate OS principals/hosts, access controls, a logged independent custodian, and a trusted pre-submission timestamp or externally witnessed publication.** The software's `external_independence_established` field is intentionally always `false`. Neither HMAC nor Ed25519 proves trusted capture, physical truth or that publication happened before the evaluated submission.

Do **not** put `custody.key`, `*.key.pem`, `nonce.secret`, `sealed_reference.json` or authentic robot evidence with sensitive metadata in public GitHub. Files under `/mnt/data` are disposable demonstration artifacts, not a secure evidence vault.

## 3. Attestation protocol

1. Custodian generates an Ed25519 key pair, storing the private key with mode `0600` in a vault; a reviewer pins the exported public-key SHA-256 out-of-band.
2. Before evaluation, the custodian generates a random 32-byte nonce and signs a **precommit** binding: study ID, experiment ID, exact evaluator-bundle file SHA-256, its canonical JSON SHA-256, sorted case inventory, predeclared method IDs, and `HMAC-SHA256(key=nonce, message=reference_file_bytes)`. The nonce is withheld.
3. The evaluator (which cannot read the private vault) produces `veap.r13.submission/1` against the committed bundle and named comparators.
4. After validating completeness and submission self-hash, the custodian signs a **submission receipt** binding the exact prediction file SHA-256, precommit SHA-256, study, experiment ID and method inventory.
5. An external reviewer checks both Ed25519 signatures and exact byte-level bindings with the pinned public key. No private key is required. A changed prediction—even if its self-SHA is recomputed—fails.
6. Only after the signed receipt is committed and protected may the custodian reveal/check the reference nonce, run the existing `r13.reference_scorer.score_submission` procedure, and sign the resulting score report. The original scorer performs its separate certificate audit. The public-key protocol is an **additional gate**, not a substitute for the independent checker.

Signed JSON uses domain separation per envelope kind and Python `json.dumps(sort_keys=True, separators=(',', ':'), allow_nan=False)` byte serialization, matching the repository's `canonical_hash` profile. This is **not** cross-language RFC 8785 canonical JSON: external tools must reproduce these byte rules exactly or use the Python verifier.

All writes are exclusive; the program refuses overwrites. Public inputs are size bounded and rejects duplicate keys/non-finite JSON; keys and nonces must not be supplied to the evaluator process. The vault's operating-system isolation must be enforced outside this Python code.

## 4. Running with two externally controlled roles

On the **custodian machine/account**, with independent author-controlled reference files and `cryptography` installed:

```bash
# Custodian commands: not in the evaluator's account.
mkdir -m 700 -p "$HOME/veap-r13-private"
python -m r13.public_custody keygen \
  --private "$HOME/veap-r13-private/ed25519.key.pem" \
  --public "$HOME/veap-r13-custodian-public.pem"

python -m r13.public_custody precommit \
  --bundle /path/to/public/evaluator_bundle.json \
  --reference "$HOME/veap-r13-private/sealed_reference.json" \
  --private "$HOME/veap-r13-private/ed25519.key.pem" \
  --nonce-out "$HOME/veap-r13-private/nonce.secret" \
  --out /path/to/public/precommit.json
```

Publish the precommit and public-key fingerprint **before running evaluators**, using an independently witnessed record or credible timestamping mechanism. Do not treat the local informational clock field as such a timestamp. The sealed reference must already exist, and must match the committed evaluator bundle.

The evaluator runs `r13.blinded_runner.run_blinded_evaluation` in a workspace that cannot see the reference vault, writing `submission.json`. The custodian then receives this exact file and issues a receipt:

```bash
python -m r13.public_custody receipt \
  --precommit /path/to/public/precommit.json \
  --bundle /path/to/public/evaluator_bundle.json \
  --submission /path/to/public/submission.json \
  --private "$HOME/veap-r13-private/ed25519.key.pem" \
  --public "$HOME/veap-r13-custodian-public.pem" \
  --out /path/to/public/receipt.json
```

An **external reviewer** can validate the preregistration and signed submission without any secret:

```bash
python -m r13.public_custody verify \
  --precommit /path/to/public/precommit.json \
  --receipt /path/to/public/receipt.json \
  --bundle /path/to/public/evaluator_bundle.json \
  --submission /path/to/public/submission.json \
  --public /path/to/trusted/custodian-public.pem
```

To reveal/confirm that the sealed reference did not change, only the custodian executes:

```bash
python -m r13.public_custody reveal \
  --precommit /path/to/public/precommit.json \
  --reference "$HOME/veap-r13-private/sealed_reference.json" \
  --nonce "$HOME/veap-r13-private/nonce.secret" \
  --public "$HOME/veap-r13-custodian-public.pem"
```

Finally, **the custodian only**, after receipt freeze, invokes the existing scorer plus separate certificate audit, and publishes a signed score artifact:

```bash
python -m r13.public_custody score \
  --precommit /path/to/public/precommit.json \
  --receipt /path/to/public/receipt.json \
  --bundle /path/to/public/evaluator_bundle.json \
  --submission /path/to/public/submission.json \
  --reference "$HOME/veap-r13-private/sealed_reference.json" \
  --nonce "$HOME/veap-r13-private/nonce.secret" \
  --private "$HOME/veap-r13-private/ed25519.key.pem" \
  --public "$HOME/veap-r13-custodian-public.pem" \
  --out "$HOME/veap-r13-private/scored_report.json" \
  --attestation-out /path/to/public/scored_report.attestation.json
```

The public signature only validates the report bytes as signed. Independent reviewers must still verify that the referenced scorer and scientific evidence actually justify the interpretations.

## 5. Run/test commands on the Ubuntu VEAP checkout

```bash
cd ~/Desktop/VEAP
python3.11 -m pip install -e './veap_evidence_r1_1[custody]'
cd veap_evidence_r1_1
python3.11 -m unittest discover -s tests -p test_r13_public_custody.py -v
python3.11 -m r13.public_custody --help
```

Run the complete integrated suite, not only these new tests, before merging. On GitHub, the integrated workflow must install the `[custody]` extra so Ed25519 tests actually run.

## 6. Negative controls and release gates

- Wrong signer or unpinned public key → reject.
- Modified reference labels or changed nonce → reject at reference reveal.
- Mutated or reserialized prediction file after receipt → reject.
- Missing case or undeclared comparator → reject before receipt.
- Duplicate JSON keys, NaN, path nesting, non-regular inputs or insecure private-key mode → reject.
- Overwriting a report, receipt or key file → reject.
- Agreement between VEAP and the strong reachability checker remains a **null/tie**, not evidence of SOTA accuracy.

## 7. Remaining scientific requirements

The public-key mechanism is not a complete independent study. It requires: independently authored scenes and reference truth; unbiased randomisation; genuine separated custodial infrastructure; clock/TF/calibration provenance; a strong external uncertainty-aware comparator; blinded human review; preregistered statistics; and an external replication of EAI/ABC where relevant.

The current 30-scene pilot is **author-generated**, its 120 cases are not physically grounded, and its 100% VEAP/monitor agreement remains an implementation check.

A credible next stage is a smaller external design pilot and then a correctly powered sealed confirmatory study. The earlier estimate of 57 scenes depends on assumed paired scene-level standard deviation and minimum detectable effect; it is not an experimentally established sample size.
