"""Tests for VEAP v0.3.0 regenerated research files and CLI tools."""
import hashlib
import json
from pathlib import Path
from veap.research.analyse import run_process_analysis
from veap.research.attacks import run_tamper_audit
from veap.cli import main

ROOT = Path(__file__).resolve().parent.parent

EXPECTED_HASHES = {
    "LITERATURE_TO_ENGINEERING_MATRIX.md": "2cf56c614da5db4813256f09658256f86c6acf345af928e28f7e1b678ff00f26",
    "PREREG_VEAP_NAV_PROTOCOL.md": "024c4d26a948b526012e8f564a8243cb2f04a27913fdf237074b568a8c75f342",
    "process-analysis.json": "cea31fcce868137ed18c8c6d2dd5b215f7170b7fd09bb436bc3186e814f41962",
    "RESEARCH_RELEASE_NOTES_v0.3.0.md": "6c9a9540b9d1535dc1ccb6d6d2ac62529eb24c799eb59bf01e6174d2e5e38d3a",
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
    assert data["schema_version"] == "veap-research-analysis/1"
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

