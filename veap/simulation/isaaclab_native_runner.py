"""Native Isaac Lab / PhysX lockstep command-tape replay.

Physically simulates the same uncalibrated planar research surrogate defined in
``veap.simulation.scene.compile_scene`` using Isaac Lab's PhysX backend and
records root state and native contact observations via ``IsaacLabTapeCollector``.
Unavailable Isaac Lab runtimes never trigger a toy fallback.
"""
from __future__ import annotations

import hashlib
from importlib.metadata import version
from pathlib import Path
from typing import Any

from ..spec import Scenario
from .export import export_scene
from .isaaclab_locked_collector import IsaacLabTapeCollector
from .locked_replay import validate_tape
from .scene import compile_scene


def _require_isaaclab():
    try:
        import torch
        import isaaclab.sim as sim_utils
        from isaaclab.assets import RigidObject, RigidObjectCfg
        from isaaclab.sensors import ContactSensor, ContactSensorCfg
        from isaaclab.sim import SimulationContext
    except ImportError as error:
        raise RuntimeError(
            "Native Isaac Lab is required; run in a qualified Isaac Lab environment"
        ) from error
    return torch, sim_utils, RigidObject, RigidObjectCfg, ContactSensor, ContactSensorCfg, SimulationContext


def _isaac_version_string() -> str:
    try:
        return f"isaacsim-{version('isaacsim')}/isaaclab-{version('isaaclab')}"
    except Exception:
        return "isaaclab-unknown"


def run_isaaclab_tape(
    scenario: Scenario,
    tape: dict,
    folder: str | Path,
    *,
    device: str = "cuda:0",
    enable_contact_sensor: bool = True,
    physics_dt: float = 0.01,
    contact_force_threshold_n: float = 1e-4,
) -> dict[str, Any]:
    """Execute one frozen command tape in an active Isaac Lab simulation context.

    The caller must have already initialized ``isaaclab.app.AppLauncher`` in the
    process before calling this function.
    """
    validate_tape(scenario, tape)
    torch, sim_utils, RigidObject, RigidObjectCfg, ContactSensor, ContactSensorCfg, SimulationContext = (
        _require_isaaclab()
    )

    ratio = float(tape["dt_s"]) / float(physics_dt)
    substeps = int(round(ratio))
    if substeps < 1 or abs(ratio - substeps) > 1e-7:
        raise RuntimeError("Isaac Lab physics_dt must divide the frozen command step exactly")

    directory = Path(folder)
    directory.mkdir(parents=True, exist_ok=True)
    scene = compile_scene(scenario)
    manifest = export_scene(scene, directory)
    usda_path = directory / manifest["files"]["usda"]["name"]

    sim = SimulationContext(sim_utils.SimulationCfg(dt=float(physics_dt), device=device))
    ground_cfg = sim_utils.GroundPlaneCfg()
    ground_cfg.func("/World/ground", ground_cfg)

    for obj in scene["objects"]:
        if not obj["collision"] or obj["role"] == "floor":
            continue
        pos = tuple(float(v) for v in obj["position_m"])
        if obj["shape"] == "box":
            cfg_obj = sim_utils.CuboidCfg(
                size=tuple(float(v) for v in obj["size_m"]),
                rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True, disable_gravity=True),
                collision_props=sim_utils.CollisionPropertiesCfg(),
            )
        else:
            cfg_obj = sim_utils.CylinderCfg(
                radius=float(obj["size_m"][0]),
                height=float(obj["size_m"][1]),
                axis="Z",
                rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True, disable_gravity=True),
                collision_props=sim_utils.CollisionPropertiesCfg(),
            )
        prim_name = obj["id"].replace("-", "_")
        cfg_obj.func(f"/World/Scene/{prim_name}", cfg_obj, translation=pos)

    robot = scene["robot"]
    mass = float(robot["mass_kg"])
    radius = float(robot["footprint_radius_m"])
    height = float(robot["height_m"])
    inertia_z = 0.5 * mass * (radius ** 2)
    linear_damping_s_inv = 2.0 / mass
    angular_damping_s_inv = 0.3 / inertia_z

    robot_cfg = RigidObjectCfg(
        prim_path="/World/VEAPScout",
        spawn=sim_utils.CylinderCfg(
            radius=radius,
            height=height,
            axis="Z",
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                disable_gravity=True,
                linear_damping=linear_damping_s_inv,
                angular_damping=angular_damping_s_inv,
            ),
            mass_props=sim_utils.MassPropertiesCfg(mass=mass),
            collision_props=sim_utils.CollisionPropertiesCfg(),
            activate_contact_sensors=enable_contact_sensor,
        ),
        init_state=RigidObjectCfg.InitialStateCfg(
            pos=tuple(float(v) for v in robot["initial_pose_xyz_m"]),
        ),
    )
    body = RigidObject(cfg=robot_cfg)

    contact_sensor = None
    if enable_contact_sensor:
        contact_sensor = ContactSensor(
            ContactSensorCfg(
                prim_path="/World/VEAPScout",
                update_period=0.0,
                track_air_time=False,
                force_threshold=float(contact_force_threshold_n),
            )
        )

    sim.reset()
    body.reset()
    if contact_sensor is not None:
        contact_sensor.reset()

    isaac_ver = _isaac_version_string()
    collector = IsaacLabTapeCollector(
        scenario,
        tape,
        engine_version=isaac_ver,
        provenance_note="externally_supplied_isaaclab_state_unattested",
    )

    def read_contacts() -> int | None:
        if contact_sensor is None:
            return None
        forces = contact_sensor.data.net_forces_w[0]
        mag = float(torch.linalg.norm(forces).item())
        return 1 if mag > contact_force_threshold_n else 0

    def record_tick(t_sec: float) -> None:
        pos = [float(x) for x in body.data.root_pos_w[0].cpu().tolist()]
        quat_wxyz = [float(x) for x in body.data.root_quat_w[0].cpu().tolist()]
        quat_xyzw = [quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]]
        lin_vel = [float(x) for x in body.data.root_lin_vel_w[0].cpu().tolist()]
        ang_vel = [float(x) for x in body.data.root_ang_vel_w[0].cpu().tolist()]
        collector.append_state(
            time_s=t_sec,
            position_xyz_m=pos,
            quaternion_xyzw=quat_xyzw,
            velocity_xyz_m_s=lin_vel,
            angular_z_rad_s=ang_vel[2],
            contacts=read_contacts(),
        )

    record_tick(0.0)
    gains = (22.0, 22.0, 4.0)
    maximum = (50.0, 50.0, 8.0)

    for step_idx, cmd in enumerate(tape["commands_vx_vy_yaw"], start=1):
        for _ in range(substeps):
            lin_v = body.data.root_lin_vel_w[0].cpu().tolist()
            ang_v = body.data.root_ang_vel_w[0].cpu().tolist()
            fx = max(-maximum[0], min(maximum[0], gains[0] * (cmd[0] - float(lin_v[0]))))
            fy = max(-maximum[1], min(maximum[1], gains[1] * (cmd[1] - float(lin_v[1]))))
            tz = max(-maximum[2], min(maximum[2], gains[2] * (cmd[2] - float(ang_v[2]))))
            forces = torch.tensor([[[fx, fy, 0.0]]], dtype=torch.float32, device=device)
            torques = torch.tensor([[[0.0, 0.0, tz]]], dtype=torch.float32, device=device)
            body.set_external_force_and_torque(forces, torques, is_global=True)
            body.write_data_to_sim()
            sim.step()
            body.update(float(physics_dt))
            if contact_sensor is not None:
                contact_sensor.update(float(physics_dt))
        record_tick(round(step_idx * float(tape["dt_s"]), 8))

    result = collector.finish()
    result["execution"] = "native_isaaclab"
    result["tape_sha256"] = tape["tape_sha256"]
    result["scene_sha256"] = scene["content_sha256"]
    result["usda_sha256"] = hashlib.sha256(usda_path.read_bytes()).hexdigest()
    result["asset_manifest_files"] = manifest["files"]
    result["surrogate_calibrated"] = False
    result["contact_sensor_enabled"] = enable_contact_sensor
    result["parameter_alignment"] = {
        "coordinate_frame": "ENU_z_up_m",
        "quaternion_input_order": "WXYZ",
        "quaternion_output_order": "XYZW",
        "physics_dt_s": float(physics_dt),
        "control_dt_s": float(tape["dt_s"]),
        "substeps": substeps,
        "mass_kg": mass,
        "inertia_z_kg_m2": round(inertia_z, 8),
        "linear_damping_n_s_m_equivalent": 2.0,
        "linear_damping_physx_s_inv": linear_damping_s_inv,
        "angular_damping_n_m_s_rad_equivalent": 0.3,
        "angular_damping_physx_s_inv": round(angular_damping_s_inv, 8),
        "gravity_mode": "disabled_planar_surrogate_at_z_0.16m",
        "controller_id": tape["controller_id"],
        "gains_kp": list(gains),
        "effort_limits": list(maximum),
    }
    return result

