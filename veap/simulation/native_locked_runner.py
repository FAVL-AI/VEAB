"""Native MuJoCo, lockstep command-tape replay.

Physically simulates a constrained planar research surrogate. This is NOT a
calibrated mobile robot nor an Isaac-Lab execution substitute. The caller must
install MuJoCo; unavailable native physics never triggers a toy fallback.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from ..spec import Scenario
from .scene import compile_scene
from .export import export_scene
from .locked_replay import validate_tape, validate_execution
from .telemetry import PhysicsRecorder, make_sample


def run_mujoco_tape(scenario: Scenario, tape: dict, folder: str | Path) -> dict[str, Any]:
    validate_tape(scenario, tape)
    try:
        import mujoco
    except ImportError as error:
        raise RuntimeError("Native MuJoCo is required; install its wheel in a separately qualified environment") from error

    directory = Path(folder)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = export_scene(compile_scene(scenario), directory)
    model_path = directory / manifest["files"]["mjcf"]["name"]
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    robot_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "veab_scout")
    if robot_id < 0:
        raise RuntimeError("MJCF missing expected surrogate robot body")
    dof_addresses = []
    for name in ("planar_x", "planar_y", "planar_yaw"):
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            raise RuntimeError("MJCF missing planar joint " + name)
        dof_addresses.append(int(model.jnt_dofadr[joint_id]))
    yaw_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "planar_yaw")
    yaw_qpos = int(model.jnt_qposadr[yaw_id])
    dt = float(model.opt.timestep)
    ratio = float(tape["dt_s"]) / dt
    substeps = int(round(ratio))
    if substeps < 1 or abs(ratio - substeps) > 1e-7:
        raise RuntimeError("MuJoCo timestep must divide the frozen command step exactly")
    if model.nu < 3:
        raise RuntimeError("MJCF lacks three planar actuation channels")
    recorder = PhysicsRecorder(scenario, "mujoco", getattr(mujoco, "__version__", "unknown"),
                               tape["scene_sha256"], seed=tape["seed"])

    def snapshot(tick: int, command: list[float]):
        p = data.xpos[robot_id]
        yaw = float(data.qpos[yaw_qpos])
        linear = [float(data.qvel[dof_addresses[0]]), float(data.qvel[dof_addresses[1]]), 0.0]
        return make_sample(tick, float(data.time),
                           [float(p[0]), float(p[1]), float(p[2])],
                           linear, [0., 0., math.sin(yaw/2), math.cos(yaw/2)],
                           float(data.qvel[dof_addresses[2]]),
                           command, contacts=int(data.ncon))

    recorder.append(snapshot(0, [0., 0., 0.]))
    for step, command in enumerate(tape["commands_vx_vy_yaw"], start=1):
        for _ in range(substeps):
            gains = (22., 22., 4.)
            maximum = (50., 50., 8.)
            for axis in range(3):
                error = command[axis] - float(data.qvel[dof_addresses[axis]])
                data.ctrl[axis] = max(-maximum[axis], min(maximum[axis], gains[axis] * error))
            mujoco.mj_step(model, data)
        recorder.append(snapshot(step, command))
    trace = recorder.finish("unknown")
    contract_result = validate_execution(scenario, tape, trace)
    return {
        "schema_version": "veab-native-replay-result/1",
        "execution": "native_mujoco",
        "tape_sha256": tape["tape_sha256"],
        "model_xml_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "model_path": str(model_path),
        "surrogate_calibrated": False,
        "native_execution_reported_unattested": True,
        "control_contract": contract_result,
        "trace": trace,
        "scope": "Uncalibrated planar surrogate; native engine execution is not independent ground truth",
    }
