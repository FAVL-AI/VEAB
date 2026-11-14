"""Negative controls for VEAP's documented software release gate."""
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/veap_integrated_gate.py"
spec = importlib.util.spec_from_file_location("integrated_gate", ROOT_SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_fixture(tmp_path):
    for p in module.REQUIRED_PATHS:
        dest = tmp_path / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("fake fixture\n")
    (tmp_path / "README.md").write_text("# VEAP — Verifiable Embodied Agent Platform\n")
    report_path = tmp_path / "veap_evidence_r1_1/artifacts/r1_identifiability/stress_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "n_cases": 96,
        "no_independent_scenes": True,
        "no_experimental_p_value_or_sota_claim": True,
        "upstream_EAI_reproduction": "NOT_RUN",
        "upstream_ABC_reproduction": "NOT_RUN",
        "summary": {"correct_by_method": {"veap": 96, "separate_monitor": 96}},
    }))
    fresh = tmp_path / "r12.json"
    fresh.write_text(json.dumps({
        "study_type": "AUTHOR_CONSTRUCTED_CORRELATED_SOFTWARE_STRESS",
        "independent_heldout_environments": False,
        "physical_sensor_ground_truth": False,
        "summary": {"n_cases": 180, "n_fixtures": 15,
                    "independent_monitor_disagreements": 0,
                    "certificate_checker_failures": 0,
                    "assumption_monotonicity_failures": 0},
    }))
    return report_path, fresh


def test_release_gate_accepts_scoped_regression(tmp_path):
    _, r12 = make_fixture(tmp_path)
    result = module.audit(tmp_path, r12)
    assert result["status"] == "PASS_SOFTWARE_ONLY"
    assert result["native_engine_production_acceptance"] == "NOT_ESTABLISHED"


def test_gate_fails_on_missing_source_file(tmp_path):
    _, r12 = make_fixture(tmp_path)
    (tmp_path / module.REQUIRED_PATHS[1]).unlink()
    assert module.audit(tmp_path, r12)["status"] == "BLOCKED"


def test_gate_rejects_misleading_readme(tmp_path):
    _, r12 = make_fixture(tmp_path)
    (tmp_path / "README.md").write_text("# VEAP — Verifiable Embodied Agent Benchmark\n")
    assert module.audit(tmp_path, r12)["status"] == "BLOCKED"


def test_gate_refuses_sota_from_correlated_cases(tmp_path):
    _, r12 = make_fixture(tmp_path)
    data = json.loads(r12.read_text())
    data["independent_heldout_environments"] = True
    r12.write_text(json.dumps(data))
    assert module.audit(tmp_path, r12)["status"] == "BLOCKED"


def test_gate_preserves_strong_comparator_tie(tmp_path):
    r11, r12 = make_fixture(tmp_path)
    data = json.loads(r11.read_text())
    data["summary"]["correct_by_method"]["separate_monitor"] = 87
    r11.write_text(json.dumps(data))
    assert module.audit(tmp_path, r12)["status"] == "BLOCKED"


def test_gate_requires_fresh_reproduced_r12(tmp_path):
    make_fixture(tmp_path)
    assert module.audit(tmp_path, None)["status"] == "BLOCKED"


def test_gate_rejects_r12_monitor_mismatch(tmp_path):
    _, r12 = make_fixture(tmp_path)
    data = json.loads(r12.read_text())
    data["summary"]["independent_monitor_disagreements"] = 1
    r12.write_text(json.dumps(data))
    assert module.audit(tmp_path, r12)["status"] == "BLOCKED"
