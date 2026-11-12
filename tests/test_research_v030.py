"""Tests for VEAB v0.3.0 regenerated research files and CLI tools."""
import hashlib
import json
from pathlib import Path
from veab.research.analyse import run_process_analysis
from veab.research.attacks import run_tamper_audit
from veab.cli import main

ROOT = Path(__file__).resolve().parent.parent

EXPECTED_HASHES = {
    "LITERATURE_TO_ENGINEERING_MATRIX.md": "bcfc5223c61c534edfae95da03f43f727a98f5b06edd4707ed102c3fcbaaaf5e",
    "PREREG_VEAB_NAV_PROTOCOL.md": "f274ab290ba9d4cdf759eca393889ab762a70d5ab6e03151c797edf98ba89c92",
    "process-analysis.json": "ca623e39383e66775e0fbf973b29df630baaee2af8de1711d23a288f4ecef128",
    "RESEARCH_RELEASE_NOTES_v0.3.0.md": "61e6c9be20c4f1a3bcc0fbce58f97e88a7f1bf88d65866bac32a2f1353eb2c11",
}


def test_research_v030_exact_checksums():
    for filename, expected_sha in EXPECTED_HASHES.items():
        doc_path = ROOT / "docs" / "research" / filename
        assert doc_path.exists(), f"Missing research file: {doc_path}"
        actual_sha = hashlib.sha256(doc_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha, f"Checksum mismatch for {filename}: {actual_sha} != {expected_sha}"


def test_research_process_analysis_cli(tmp_path):
    out_file = tmp_path / "proc-analysis.json"
    summary_path = ROOT / "examples" / "60-trial-summary.json"
    
    code = main(["research-analyse", str(summary_path), "--out", str(out_file)])
    assert code == 0
    assert out_file.exists()
    
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "veab-research-analysis/1"
    assert data["data_audit"]["n_trial_rows"] == 60
    assert "greedy_gate_effect" in data["comparisons"]
    assert "route_gate_effect" in data["comparisons"]
    assert "policy_effect_without_gate" in data["comparisons"]


def test_tamper_audit_suite(tmp_path):
    out_file = tmp_path / "tamper-audit.json"
    res = run_tamper_audit(out_path=out_file)
    
    assert res["tamper_regression"]["all_unkeyed_tampering_caught"] is True
    assert res["tamper_regression"]["unkeyed_edits_rejected_count"] == 4
    assert res["rehashed_spoof_vulnerability_demonstrated"]["recomputed_chain_appears_valid_without_hmac"] is True

