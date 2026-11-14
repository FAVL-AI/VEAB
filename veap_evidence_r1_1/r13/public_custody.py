"""VEAP R1.3 optional public-key custody protocol.

Complements (does not replace) r13.custody's development HMAC receipts.
Ed25519 attests pinned input bytes and post-submission receipts; neither
attestation nor hashing proves physical truth, independent authorship, trusted
time, reference quality, or separation if both roles share the same OS account.

Envelope protocol 1 is intentionally self-contained and independently usable by
external custodians. Cross-language canonicalisation requires reproducing the
specified Python json.dumps profile; it is not RFC 8785 JSON canonicalisation.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

VERSION = "veap.r13.public-custody/1"
SUBMISSION_SCHEMA = "veap.r13.submission/1"
PUBLIC_METHODS = (
    "veap", "separate_reachability_monitor", "gap_aware",
    "sampled_safety", "terminal_safety", "goal_only",
)
MAX_JSON_BYTES = 20_000_000


class CustodyError(ValueError):
    """An input, trust-anchor, or signed-binding validation failed."""


def _canonical(value: Any) -> bytes:
    # This matches VEAP's existing canonical_hash implementation.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs_no_dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise CustodyError(f"Duplicate JSON key: {key}")
        out[key] = value
    return out


def _read_bytes(path: Path) -> bytes:
    """Read only a bounded, stable, regular file without following final symlinks."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags)
    with os.fdopen(fd, "rb") as f:
        st0 = os.fstat(f.fileno())
        if not stat.S_ISREG(st0.st_mode) or st0.st_size > MAX_JSON_BYTES:
            raise CustodyError("Refusing non-regular or oversized custody input")
        raw = f.read(MAX_JSON_BYTES + 1)
        st1 = os.fstat(f.fileno())
        if (len(raw) > MAX_JSON_BYTES or st0.st_dev != st1.st_dev or
            st0.st_ino != st1.st_ino or st0.st_mtime_ns != st1.st_mtime_ns or
            st0.st_size != st1.st_size):
            raise CustodyError("Custody input changed while reading or exceeded 20 MB")
        return raw


def read_json(path: Path) -> dict[str, Any]:
    path = Path(path)
    raw = _read_bytes(path)
    try:
        obj = json.loads(raw, object_pairs_hook=_pairs_no_dupes,
                         parse_constant=lambda x: (_ for _ in ()).throw(CustodyError(f"Non-finite token: {x}")))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise CustodyError(f"Invalid JSON in {path.name}: {e}") from e
    if not isinstance(obj, dict):
        raise CustodyError("Expected JSON object")
    return obj


def _exclusive_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    """No overwrites or symlink following, including after re-running a study."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        raise


def save_json(path: Path, record: dict[str, Any], mode: int = 0o600) -> None:
    _exclusive_write(path, json.dumps(record, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n", mode)


def _key_and_public(private_path: Path) -> tuple[Ed25519PrivateKey, bytes]:
    path = Path(private_path)
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or (s.st_mode & 0o077):
        raise CustodyError("Private key must be a non-symlink regular file with permissions 0600")
    if hasattr(os, "geteuid") and s.st_uid != os.geteuid():
        raise CustodyError("Private key must be owned by the signing process")
    key = serialization.load_pem_private_key(_read_bytes(path), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise CustodyError("Expected Ed25519 private key")
    pub_raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, pub_raw


def generate_key_pair(private_path: Path, public_path: Path) -> str:
    """Generate one random custodian key pair; never put the private key in Git."""
    if Path(private_path).resolve() == Path(public_path).resolve():
        raise CustodyError("Public/private paths must differ")
    if Path(private_path).exists() or Path(private_path).is_symlink() or Path(public_path).exists() or Path(public_path).is_symlink():
        raise CustodyError("Refusing to overwrite an existing custodian key file")
    key = Ed25519PrivateKey.generate()
    priv_bytes = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption())
    pub = key.public_key()
    pub_bytes = pub.public_bytes(serialization.Encoding.PEM,
                                  serialization.PublicFormat.SubjectPublicKeyInfo)
    _exclusive_write(Path(private_path), priv_bytes, 0o600)
    _exclusive_write(Path(public_path), pub_bytes, 0o644)
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return _sha(raw)


def _load_public(public_path: Path) -> tuple[Ed25519PublicKey, str]:
    key = serialization.load_pem_public_key(_read_bytes(Path(public_path)))
    if not isinstance(key, Ed25519PublicKey):
        raise CustodyError("Expected Ed25519 public key")
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, _sha(raw)


def _domain(kind: str) -> bytes:
    if kind not in ("precommit", "submission_receipt", "score"):
        raise CustodyError(f"Unsupported envelope kind: {kind}")
    return ("VEAP-R13-PUBLIC-CUSTODY/1/" + kind + "\0").encode("ascii")


def sign(kind: str, body: dict[str, Any], private_key_path: Path) -> dict[str, Any]:
    key, raw_pub = _key_and_public(private_key_path)
    signable = {"schema": VERSION, "kind": kind, "body": body, "public_key_sha256": _sha(raw_pub)}
    signature = key.sign(_domain(kind) + _canonical(signable))
    return {**signable, "signature_base64": base64.b64encode(signature).decode("ascii")}


def verify(envelope: dict[str, Any], expected_kind: str, trusted_public_key_path: Path) -> dict[str, Any]:
    """Public verifier MUST pin its trust anchor outside the submitted envelope."""
    if not isinstance(envelope, dict) or set(envelope) != {
        "schema", "kind", "body", "public_key_sha256", "signature_base64"
    }:
        raise CustodyError("Invalid or unexpected signed envelope fields")
    if envelope["schema"] != VERSION or envelope["kind"] != expected_kind:
        raise CustodyError("Wrong signed envelope protocol/kind")
    key, key_sha = _load_public(trusted_public_key_path)
    if envelope["public_key_sha256"] != key_sha:
        raise CustodyError("Signer does not match pinned public key")
    to_check = {k: envelope[k] for k in ("schema", "kind", "body", "public_key_sha256")}
    try:
        signature = base64.b64decode(envelope["signature_base64"], validate=True)
        key.verify(signature, _domain(expected_kind) + _canonical(to_check))
    except (InvalidSignature, ValueError, TypeError) as e:
        raise CustodyError("Ed25519 signature invalid") from e
    if not isinstance(envelope["body"], dict):
        raise CustodyError("Signed body is malformed")
    return envelope["body"]


def _utc_note() -> str:
    # Informational only. Wall clock is not a trusted timestamp authority.
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _outside_vault(public_bundle_path: Path, private_paths: tuple[Path, ...]) -> None:
    base = Path(public_bundle_path).resolve().parent
    for path in private_paths:
        p = Path(path).resolve()
        if p == base or base in p.parents or p in base.parents:
            raise CustodyError("Custodian private inputs must be outside the evaluator workspace")


_FORBIDDEN_REFERENCE_KEYS = frozenset({
    "ground_truth", "expected_verdict", "reference_verdict", "reference_label",
    "true_verdict", "hidden_trajectory", "reference_trajectory", "oracle",
    "condition_code", "condition", "author_secret", "is_compliant_truth",
})


def _check_no_reference_fields(value: Any) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if k in _FORBIDDEN_REFERENCE_KEYS:
                raise CustodyError(f"Reference label leaked into evaluator input: {k}")
            _check_no_reference_fields(v)
    elif isinstance(value, list):
        for v in value:
            _check_no_reference_fields(v)


def _bundle_shape(bundle: dict[str, Any]) -> tuple[str, set[str]]:
    _check_no_reference_fields(bundle)
    cases = bundle.get("cases")
    study_id = bundle.get("study_id")
    if not isinstance(study_id, str) or not study_id or not isinstance(cases, list) or not cases:
        raise CustodyError("Evaluator bundle missing study_id or cases")
    ids = [item.get("case_id") for item in cases if isinstance(item, dict)]
    if len(ids) != len(cases) or not all(isinstance(c, str) and c for c in ids):
        raise CustodyError("Evaluator bundle case IDs invalid")
    if len(set(ids)) != len(ids):
        raise CustodyError("Evaluator bundle has duplicate case IDs")
    for cid in ids:
        if any(tok in cid.lower() for tok in (
            "complete", "intrusion", "violat", "compliant", "inconclusive", "omission", "cond_"
        )):
            raise CustodyError("Evaluator case_id discloses a condition label")
    return study_id, set(ids)


def _submission_shape(submission: dict[str, Any], bundle: dict[str, Any],
                      required_methods: list[str]) -> None:
    if submission.get("schema") != SUBMISSION_SCHEMA:
        raise CustodyError("Wrong submission schema")
    study_id, ids = _bundle_shape(bundle)
    if submission.get("study_id") != study_id:
        raise CustodyError("Submission study_id differs")
    if submission.get("evaluator_bundle_sha256") != _sha(_canonical(bundle)):
        raise CustodyError("Submission does not match canonical evaluator bundle")
    if submission.get("n_cases") != len(ids):
        raise CustodyError("Submission case count differs")
    copy = dict(submission)
    claimed_sha = copy.pop("submission_sha256", None)
    if claimed_sha != _sha(_canonical(copy)):
        raise CustodyError("Submission self-digest does not match")
    methods = submission.get("methods")
    if not isinstance(methods, list) or len(methods) != len(set(methods)) or sorted(methods) != sorted(required_methods):
        raise CustodyError("Submission method inventory differs from preregistration")
    predictions = submission.get("predictions_by_method")
    certs = submission.get("veap_certificates")
    if not isinstance(predictions, dict) or not isinstance(certs, dict) or set(certs) != ids:
        raise CustodyError("Certificate case inventory differs")
    if set(predictions) != set(required_methods):
        raise CustodyError("Prediction method inventory differs")
    if any(not isinstance(p, dict) or set(p) != ids for p in predictions.values()):
        raise CustodyError("Prediction case inventory differs")
    if any(v not in ("COMPLIANT", "VIOLATING", "INCONCLUSIVE") for p in predictions.values() for v in p.values()):
        raise CustodyError("Unexpected verdict vocabulary")


def make_precommit(bundle_path: Path, reference_path: Path, private_key_path: Path,
                   nonce_out_path: Path, method_ids: tuple[str, ...] = PUBLIC_METHODS) -> dict[str, Any]:
    """Bind all data and methods BEFORE the custodian issues any submission receipt."""
    _outside_vault(bundle_path, (reference_path, private_key_path, nonce_out_path))
    bundle = read_json(bundle_path)
    ref = read_json(reference_path)
    study_id, cases = _bundle_shape(bundle)
    if ref.get("study_id") != study_id:
        raise CustodyError("Sealed reference study_id differs")
    if ref.get("evaluator_bundle_sha256") != _sha(_canonical(bundle)):
        raise CustodyError("Sealed reference bundle digest differs")
    if not isinstance(ref.get("cases"), dict) or set(ref["cases"]) != cases:
        raise CustodyError("Reference case inventory differs")
    methods = list(method_ids)
    if not methods or len(methods) != len(set(methods)):
        raise CustodyError("Invalid preregistered methods")
    nonce = secrets.token_bytes(32)
    _exclusive_write(Path(nonce_out_path), nonce, 0o600)
    body = {
        "study_id": study_id,
        "experiment_id": secrets.token_hex(16),
        "evaluator_bundle_file_sha256": _sha(_read_bytes(bundle_path)),
        "evaluator_bundle_canonical_sha256": _sha(_canonical(bundle)),
        "reference_hmac_commitment_sha256": hmac.new(nonce, _read_bytes(reference_path), hashlib.sha256).hexdigest(),
        "nonce_sha256": _sha(nonce),
        "case_inventory_sha256": _sha(_canonical(sorted(cases))),
        "n_cases": len(cases),
        "method_ids": methods,
        "issued_at_utc_untrusted_wall_clock": _utc_note(),
        "study_claims": "NO_EXTERNAL_INDEPENDENCE_OR_PHYSICAL_AUTHENTICITY_INFERRED",
    }
    return sign("precommit", body, private_key_path)


def _verify_bundle_precommit(precommit_body: dict[str, Any], bundle_path: Path) -> dict[str, Any]:
    bundle = read_json(bundle_path)
    study_id, cases = _bundle_shape(bundle)
    if (precommit_body.get("study_id") != study_id or
        precommit_body.get("evaluator_bundle_file_sha256") != _sha(_read_bytes(bundle_path)) or
        precommit_body.get("evaluator_bundle_canonical_sha256") != _sha(_canonical(bundle)) or
        precommit_body.get("case_inventory_sha256") != _sha(_canonical(sorted(cases))) or
        precommit_body.get("n_cases") != len(cases)):
        raise CustodyError("Evaluator bundle differs from signed preregistration")
    return bundle


def make_receipt(precommit: dict[str, Any], bundle_path: Path, submission_path: Path,
                 private_key_path: Path, trusted_public_key_path: Path) -> dict[str, Any]:
    body = verify(precommit, "precommit", trusted_public_key_path)
    bundle = _verify_bundle_precommit(body, bundle_path)
    submission = read_json(submission_path)
    _submission_shape(submission, bundle, body["method_ids"])
    receipt = {
        "study_id": body["study_id"],
        "experiment_id": body["experiment_id"],
        "precommit_sha256": _sha(_canonical(precommit)),
        "submission_file_sha256": _sha(_read_bytes(submission_path)),
        "submission_canonical_sha256": _sha(_canonical(submission)),
        "submission_self_digest_sha256": submission["submission_sha256"],
        "n_cases": body["n_cases"],
        "method_ids": body["method_ids"],
        "issued_at_utc_untrusted_wall_clock": _utc_note(),
    }
    return sign("submission_receipt", receipt, private_key_path)


def verify_locked_run(precommit: dict[str, Any], receipt: dict[str, Any],
                      bundle_path: Path, submission_path: Path, public_key_path: Path) -> dict[str, Any]:
    pre = verify(precommit, "precommit", public_key_path)
    rec = verify(receipt, "submission_receipt", public_key_path)
    bundle = _verify_bundle_precommit(pre, bundle_path)
    submission = read_json(submission_path)
    _submission_shape(submission, bundle, pre["method_ids"])
    if (rec.get("precommit_sha256") != _sha(_canonical(precommit)) or
        rec.get("study_id") != pre["study_id"] or
        rec.get("experiment_id") != pre["experiment_id"] or
        rec.get("submission_file_sha256") != _sha(_read_bytes(submission_path)) or
        rec.get("submission_canonical_sha256") != _sha(_canonical(submission)) or
        rec.get("submission_self_digest_sha256") != submission["submission_sha256"] or
        rec.get("method_ids") != pre["method_ids"] or
        rec.get("n_cases") != pre["n_cases"]):
        raise CustodyError("Submission receipt not bound to supplied preregistration and exact submission")
    return {
        "status": "PUBLIC_SIGNATURES_AND_CONTENT_BINDINGS_VALID",
        "study_id": pre["study_id"],
        "experiment_id": pre["experiment_id"],
        "public_key_sha256": precommit["public_key_sha256"],
        "submission_sha256": rec["submission_file_sha256"],
        "n_cases": pre["n_cases"],
        "external_independence_established": False,
        "physical_truth_established": False,
        "trusted_timestamp_established": False,
    }


def verify_reference_reveal(precommit: dict[str, Any], reference_path: Path,
                            nonce_path: Path, public_key_path: Path) -> None:
    pre = verify(precommit, "precommit", public_key_path)
    nonce = _read_bytes(nonce_path)
    if len(nonce) != 32 or _sha(nonce) != pre.get("nonce_sha256"):
        raise CustodyError("Invalid or modified private nonce")
    if not hmac.compare_digest(
        hmac.new(nonce, _read_bytes(reference_path), hashlib.sha256).hexdigest(),
        str(pre.get("reference_hmac_commitment_sha256", ""))
    ):
        raise CustodyError("Reference evidence changed after preregistration")
    ref = read_json(reference_path)
    if ref.get("study_id") != pre.get("study_id"):
        raise CustodyError("Reference study ID changed")


def score_locked_run(precommit: dict[str, Any], receipt: dict[str, Any],
                     bundle_path: Path, submission_path: Path, reference_path: Path,
                     nonce_path: Path, public_key_path: Path, private_key_path: Path,
                     scorer=None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Custodian-only step: verify all bindings, independently recheck, score, attest.

    The existing `r13.reference_scorer.score_submission` performs independent
    certificate obligation checks against its monitor. `scorer` is an optional
    injectable function for protocol unit tests, not a trusted external oracle.
    """
    _outside_vault(bundle_path, (reference_path, nonce_path, private_key_path))
    binding = verify_locked_run(precommit, receipt, bundle_path, submission_path, public_key_path)
    verify_reference_reveal(precommit, reference_path, nonce_path, public_key_path)
    ref = read_json(reference_path)
    bundle = read_json(bundle_path)
    submission = read_json(submission_path)
    if scorer is None:
        from r13.reference_scorer import score_submission
        scorer = score_submission
    report = scorer(bundle, submission, ref)
    if not isinstance(report, dict):
        raise CustodyError("Scorer did not return a report mapping")
    if report.get("study_id") != binding["study_id"]:
        raise CustodyError("Score report study ID differs from signed commitment")
    # The existing HMAC status is independent of this Ed25519 protocol.
    report["public_custody_attestation"] = {
        "status": "PUBLIC_SIGNATURES_AND_REFERENCE_REVEAL_VERIFIED",
        "experiment_id": binding["experiment_id"],
        "precommit_sha256": _sha(_canonical(precommit)),
        "receipt_sha256": _sha(_canonical(receipt)),
        "public_key_sha256": binding["public_key_sha256"],
        "independent_external_custodian": False,
        "trusted_timestamp": False,
    }
    body = {
        "study_id": binding["study_id"],
        "experiment_id": binding["experiment_id"],
        "precommit_sha256": _sha(_canonical(precommit)),
        "receipt_sha256": _sha(_canonical(receipt)),
        "report_canonical_sha256": _sha(_canonical(report)),
        "issued_at_utc_untrusted_wall_clock": _utc_note(),
    }
    score_envelope = sign("score", body, private_key_path)
    # Refuse a private key not matching the pinned public verification key.
    verify(score_envelope, "score", public_key_path)
    return report, score_envelope


def verify_score_attestation(report: dict[str, Any], attestation: dict[str, Any],
                             precommit: dict[str, Any], receipt: dict[str, Any],
                             public_key_path: Path) -> None:
    body = verify(attestation, "score", public_key_path)
    if (body.get("report_canonical_sha256") != _sha(_canonical(report)) or
        body.get("precommit_sha256") != _sha(_canonical(precommit)) or
        body.get("receipt_sha256") != _sha(_canonical(receipt)) or
        body.get("study_id") != precommit["body"].get("study_id") or
        body.get("experiment_id") != precommit["body"].get("experiment_id")):
        raise CustodyError("Score attestation does not bind the provided report and receipts")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VEAP R1.3 Ed25519 public custody gate (not a certification)")
    cmd = parser.add_subparsers(dest="action", required=True)
    keygen = cmd.add_parser("keygen", help="Generate an external custodian signing key pair")
    keygen.add_argument("--private", type=Path, required=True)
    keygen.add_argument("--public", type=Path, required=True)
    pre = cmd.add_parser("precommit", help="Custodian: commit reference before evaluation")
    for arg in ("bundle", "reference", "private", "nonce_out", "out"):
        pre.add_argument("--" + arg.replace("_", "-"), type=Path, required=True)
    lock = cmd.add_parser("receipt", help="Custodian: freeze a submitted prediction file")
    for arg in ("precommit", "bundle", "submission", "private", "public", "out"):
        lock.add_argument("--" + arg, type=Path, required=True)
    check = cmd.add_parser("verify", help="External reviewer: validate with public key only")
    for arg in ("precommit", "receipt", "bundle", "submission", "public"):
        check.add_argument("--" + arg, type=Path, required=True)
    reveal = cmd.add_parser("reveal", help="Custodian: verify sealed reference against precommit")
    for arg in ("precommit", "reference", "nonce", "public"):
        reveal.add_argument("--" + arg, type=Path, required=True)
    score = cmd.add_parser("score", help="Custodian: recheck and score a frozen submission")
    for arg in ("precommit", "receipt", "bundle", "submission", "reference", "nonce", "private", "public", "out", "attestation_out"):
        score.add_argument("--" + arg.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "keygen":
            print(json.dumps({"status": "KEY_GENERATED", "public_key_sha256": generate_key_pair(args.private, args.public)}))
        elif args.action == "precommit":
            save_json(args.out, make_precommit(args.bundle, args.reference, args.private, args.nonce_out), 0o644)
            print(json.dumps({"status": "PRECOMMIT_SIGNED", "file": str(args.out)}))
        elif args.action == "receipt":
            save_json(args.out, make_receipt(read_json(args.precommit), args.bundle, args.submission,
                                             args.private, args.public), 0o644)
            print(json.dumps({"status": "RECEIPT_SIGNED", "file": str(args.out)}))
        elif args.action == "verify":
            print(json.dumps(verify_locked_run(read_json(args.precommit), read_json(args.receipt),
                                               args.bundle, args.submission, args.public), sort_keys=True))
        elif args.action == "reveal":
            verify_reference_reveal(read_json(args.precommit), args.reference, args.nonce, args.public)
            print(json.dumps({"status": "SEALED_REFERENCE_COMMITMENT_MATCHED"}))
        elif args.action == "score":
            report, attestation = score_locked_run(
                read_json(args.precommit), read_json(args.receipt), args.bundle,
                args.submission, args.reference, args.nonce, args.public, args.private)
            # Refuse pre-existing report/attestation paths before writing either.
            if args.out.exists() or args.out.is_symlink() or args.attestation_out.exists() or args.attestation_out.is_symlink():
                raise CustodyError("Score outputs already exist: refusing overwrite")
            save_json(args.out, report, 0o600)
            save_json(args.attestation_out, attestation, 0o644)
            print(json.dumps({"status": "SIGNED_SCORE_RECORDED", "out": str(args.out)}))
    except (CustodyError, OSError, ValueError) as err:
        parser.exit(2, f"VEAP custody gate FAILED: {err}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
