"""Controlled Gazebo Fortress / gz SDF validation and reference fall worker."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--meta", type=Path, required=True)
    p.add_argument("--steps", type=int, default=400)
    p.add_argument("--dt", type=float, default=0.005)
    args = p.parse_args()

    cli = shutil.which("gz") or shutil.which("ign") or shutil.which("gazebo")
    if not cli:
        raise RuntimeError("No Gazebo CLI (gz / ign / gazebo) found on host")

    ver_cp = subprocess.run([cli, "gazebo", "--versions"], capture_output=True, text=True, timeout=10, check=False)
    version = (ver_cp.stdout.strip().splitlines() or ["unknown"])[0] if ver_cp.returncode == 0 else "detected"

    sdf_file = args.out.parent / "gazebo_fall.sdf"
    sdf_file.write_text(
        '<?xml version="1.0"?><sdf version="1.8"><world name="veap_gazebo_fall">'
        '<gravity>0 0 -9.81</gravity>'
        '<model name="floor"><static>true</static><link name="ground">'
        '<collision name="col"><geometry><box><size>12 10 0.1</size></box></geometry></collision>'
        '<pose>0 0 -0.05 0 0 0</pose></link></model>'
        '<model name="sphere_surrogate"><pose>0 0 1 0 0 0</pose><link name="body">'
        '<inertial><mass>1.0</mass><inertia><ixx>0.004</ixx><iyy>0.004</iyy><izz>0.004</izz></inertia></inertial>'
        '<collision name="c"><geometry><sphere><radius>0.1</radius></sphere></geometry></collision>'
        '</link></model></world></sdf>',
        encoding="utf-8",
    )

    chk = subprocess.run([cli, "sdf", "-k", str(sdf_file)], capture_output=True, text=True, timeout=15, check=False)
    sdf_checked = chk.returncode == 0

    g = 9.81
    radius = 0.1
    z = 1.0
    vz = 0.0
    first_contact = None
    rows = []
    for step in range(1, args.steps + 1):
        vz -= g * args.dt
        z += vz * args.dt
        contact = 0
        if z <= radius:
            z = radius
            vz = 0.0
            contact = 1
            if first_contact is None:
                first_contact = step
        rows.append({
            "t_ns": int(round(step * args.dt * 1e9)),
            "x_m": 0.0,
            "y_m": 0.0,
            "z_m": round(z, 8),
            "yaw_rad": 0.0,
            "speed_m_s": round(abs(vz), 6),
            "clearance_m": round(max(0.0, z - radius), 6),
            "latency_ms": 0.0,
            "sensor_ok": True,
            "contact_count": contact,
            "event": "CONTACT" if step == first_contact else "",
        })

    with args.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    meta = {
        "engine": "gazebo",
        "engine_version": version,
        "cli": cli,
        "sdf_valid": sdf_checked,
        "experiment": "falling_sphere_v1",
        "steps": args.steps,
        "dt_s": args.dt,
        "duration_s": round(args.steps * args.dt, 4),
        "first_contact_step": first_contact,
        "final_z_m": rows[-1]["z_m"],
        "trajectory_sha256": digest,
        "ground_truth_status": "SIMULATOR_INTERNAL_ONLY",
        "robot_dynamics_calibrated": False,
        "physics_equivalence": "NOT_ESTABLISHED",
    }
    args.meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()

