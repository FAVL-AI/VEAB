"""Native-only physics smoke. Runs ONLY when the MuJoCo wheel is present."""
import pytest
mujoco = pytest.importorskip("mujoco", reason="native MuJoCo runtime is not available; never simulate a pass")
from veap.spec import load_scenario
from veap.simulation.locked_replay import standard_tape, validate_execution
from veap.simulation.native_locked_runner import run_mujoco_tape


def test_real_mujoco_steps_frozen_commands(tmp_path):
    s = load_scenario("warehouse-transfer")
    tape = standard_tape(s, steps=8, seed=5)
    output = run_mujoco_tape(s, tape, tmp_path)
    assert output["execution"] == "native_mujoco"
    assert len(output["trace"]["samples"]) == 9
    assert validate_execution(s, tape, output["trace"])["tape_matches"]
    assert output["surrogate_calibrated"] is False
    assert output["control_contract"]["physical_source_authenticity"] == "not_established"
    assert output["model_xml_sha256"]
