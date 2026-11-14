"""VEAP R1.3 independent certificate-obligation and witness-citation auditor."""
from __future__ import annotations

from typing import Any

from external_monitor.monitor import inspect as monitor_inspect


class CertificateAuditError(ValueError):
    """Raised when a certificate fails independent evidence-citation or proof checks."""


def _cited_refs_exist(trace: dict[str, Any], cert: dict[str, Any]) -> list[str]:
    """Verify every evidence_ref / evidence_refs cited in the certificate exists in trace."""
    known_ids = {
        row.get("event_id", f"sample:{idx}")
        for idx, row in enumerate(trace.get("samples", []))
        if isinstance(row, dict)
    }
    missing: list[str] = []
    for section in ("confirmed_violations", "evidence_witnesses"):
        for item in cert.get(section, []):
            if not isinstance(item, dict):
                missing.append(f"malformed_{section}_entry")
                continue
            if "evidence_ref" in item and item["evidence_ref"] not in known_ids:
                missing.append(f"{section}:{item['evidence_ref']}")
            if "evidence_refs" in item:
                refs = item["evidence_refs"]
                if not isinstance(refs, list) or not refs:
                    missing.append(f"{section}:empty_evidence_refs")
                else:
                    for r in refs:
                        if r not in known_ids:
                            missing.append(f"{section}:{r}")
    return missing


def _compute_review_localization(contract: dict[str, Any], trace: dict[str, Any], cert: dict[str, Any]) -> dict[str, float]:
    """Quantify the fraction of trace samples or mission window isolated by the certificate."""
    n_samples = max(1, len(trace.get("samples", [])))
    duration = max(1e-9, float(contract["mission_end_s"]) - float(contract["mission_start_s"]))
    verdict = cert.get("verdict")

    if verdict == "VIOLATING":
        cited = {
            w.get("evidence_ref")
            for w in cert.get("confirmed_violations", [])
            if isinstance(w, dict) and w.get("evidence_ref")
        }
        sample_fraction = len(cited) / n_samples
        return {"localized_sample_fraction": round(sample_fraction, 4), "localized_window_fraction": round(sample_fraction, 4)}

    if verdict == "INCONCLUSIVE":
        unresolved = cert.get("unresolved_coverage", [])
        total_gap = 0.0
        for item in unresolved:
            iv = item.get("interval_s", [0.0, 0.0]) if isinstance(item, dict) else [0.0, 0.0]
            if isinstance(iv, list) and len(iv) == 2:
                total_gap += max(0.0, float(iv[1]) - float(iv[0]))
        win_frac = min(1.0, total_gap / duration)
        return {"localized_sample_fraction": round(win_frac, 4), "localized_window_fraction": round(win_frac, 4)}

    # COMPLIANT
    cov_refs: set[str] = set()
    for w in cert.get("evidence_witnesses", []):
        if isinstance(w, dict):
            if "evidence_ref" in w and isinstance(w["evidence_ref"], str):
                cov_refs.add(w["evidence_ref"])
            for r in w.get("evidence_refs", []):
                if isinstance(r, str):
                    cov_refs.add(r)
    sample_fraction = min(1.0, len(cov_refs) / n_samples)
    return {"localized_sample_fraction": round(sample_fraction, 4), "localized_window_fraction": 1.0}


def audit_single_certificate(contract: dict[str, Any], trace: dict[str, Any], cert: dict[str, Any]) -> dict[str, Any]:
    """Independently check a single certificate against its contract and trace."""
    if not isinstance(cert, dict):
        raise CertificateAuditError("Certificate must be a JSON object")

    inspected = monitor_inspect(contract, trace, cert)
    errors = list(inspected.get("errors", []))
    dangling = _cited_refs_exist(trace, cert)
    if dangling:
        errors.append(f"cited evidence references missing from trace: {dangling}")

    verdict = cert.get("verdict")
    if verdict == "VIOLATING" and not cert.get("confirmed_violations"):
        errors.append("VIOLATING certificate must cite at least one confirmed violation witness")
    if verdict == "INCONCLUSIVE" and not cert.get("unresolved_coverage") and not cert.get("missing_evidence_diagnostics"):
        errors.append("INCONCLUSIVE certificate must cite unresolved intervals or diagnostics")

    localization = _compute_review_localization(contract, trace, cert)
    return {
        "certificate_check": "PASS" if not errors else "FAIL",
        "verdict": verdict,
        "reference_verdict": inspected.get("reference_verdict"),
        "errors": errors,
        "localization": localization,
    }


def audit_submission_certificates(
    evaluator_bundle: dict[str, Any],
    submission: dict[str, Any],
    fail_closed: bool = True,
) -> dict[str, Any]:
    """Audit all VEAP certificates in a frozen submission."""
    certs = submission.get("veap_certificates", {})
    cases = evaluator_bundle.get("cases", [])

    total = 0
    passed = 0
    conclusive_total = 0
    conclusive_passed = 0
    failures: list[dict[str, Any]] = []
    sample_fractions: list[float] = []

    for item in cases:
        cid = item["case_id"]
        total += 1
        cert = certs.get(cid)
        if cert is None:
            failures.append({"case_id": cid, "errors": ["missing certificate"]})
            continue
        res = audit_single_certificate(item["contract"], item["trace"], cert)
        is_conclusive = cert.get("verdict") in ("COMPLIANT", "VIOLATING")
        if is_conclusive:
            conclusive_total += 1
        if res["certificate_check"] == "PASS":
            passed += 1
            if is_conclusive:
                conclusive_passed += 1
            sample_fractions.append(res["localization"]["localized_sample_fraction"])
        else:
            failures.append({"case_id": cid, "errors": res["errors"]})

    all_rate = passed / max(1, total)
    conclusive_rate = conclusive_passed / max(1, conclusive_total)
    mean_loc = sum(sample_fractions) / max(1, len(sample_fractions))

    summary = {
        "status": "PASS" if not failures else "FAIL",
        "total_certificates": total,
        "passed_certificates": passed,
        "conclusive_certificates": conclusive_total,
        "conclusive_passed": conclusive_passed,
        "all_certificate_check_rate": round(all_rate, 6),
        "conclusive_certificate_check_rate": round(conclusive_rate, 6),
        "mean_localized_sample_fraction": round(mean_loc, 4),
        "failures": failures,
    }
    if fail_closed and failures:
        raise CertificateAuditError(f"Certificate audit failed on {len(failures)} cases: {failures[:3]}")
    return summary
