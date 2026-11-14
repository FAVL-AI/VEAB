"""Simulator-independent, strictly bounded physical scene description.

ENU world: x east, y north, z up, metres, seconds, radians. Blender/Unreal
coordinate conversion is an explicit engine import task; do not silently flip.
"""
from __future__ import annotations
import math
import re
from typing import Any
from ..spec import Scenario, digest

SCHEMA = "veab-scene/2"
_IDENT = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def canonical_scenario_payload(s: Scenario) -> dict[str, Any]:
    """Return the canonical v0.6 scenario payload preserving on-disk tape digest compatibility."""
    payload = s.model_dump(mode="json", exclude_none=True)
    payload["schema_version"] = "veab-scenario/1"
    return payload


def _name(value: str, taken: set[str]) -> str:
    s = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-_")[:50]
    if not s or not s[0].isalpha():
        s = "object-" + s
    candidate = s
    index = 1
    while candidate in taken:
        candidate = f"{s[:40]}-{index}"
        index += 1
    taken.add(candidate)
    return candidate


def compile_scene(s: Scenario) -> dict[str, Any]:
    """Create a 3-D world, with *surrogate* navigation geometry, from a VEAP task.

    Physical robot properties are deliberately assumptions, NOT calibrations of
    any vendor's machine. Dynamic mass/inertia values need hardware measurement.
    """
    used: set[str] = set()
    objects: list[dict] = []

    def add(label, kind, xyz, size, rgba, role, collision=True, mass=None):
        object_id = _name(label, used)
        record = {"id": object_id, "label": label, "shape": kind,
                  "position_m": [round(float(v), 5) for v in xyz],
                  "size_m": [round(float(v), 5) for v in size],
                  "rgba": rgba, "role": role, "collision": collision}
        if mass is not None:
            record["mass_kg"] = float(mass)
        objects.append(record)
        return object_id

    # Floor slab: top surface precisely z=0; collision solids are above.
    add("Factory floor", "box", [s.width/2, s.height/2, -0.075],
        [s.width, s.height, 0.15], [0.16,0.21,0.27,1], "floor")
    # Walls should remain outside the toy navigation boundaries; do not block
    # admissible centre points near the walls.
    for label, pos, size in [
        ("West boundary", [-0.08,s.height/2,0.65], [.16,s.height,1.3]),
        ("East boundary", [s.width+.08,s.height/2,.65], [.16,s.height,1.3]),
        ("South boundary", [s.width/2,-.08,.65], [s.width,.16,1.3]),
        ("North boundary", [s.width/2,s.height+.08,.65], [s.width,.16,1.3]),
    ]:
        add(label,"box",pos,size,[.30,.36,.46,0.68],"boundary")
    for o in s.obstacles:
        add(o.label,"cylinder",[o.x,o.y,.8],[o.radius,1.6],
            [.9,.52,.2,1],"obstacle")
    for z in s.forbidden_zones:
        add(z.label,"box",[(z.x1+z.x2)/2,(z.y1+z.y2)/2,.025],
            [z.x2-z.x1,z.y2-z.y1,.05],[.9,.18,.32,.25],
            "forbidden",False)
    for i, p in enumerate(s.waypoints):
        add(f"Checkpoint {i+1} {p.label}","cylinder",[p.x,p.y,.035],
            [.16,.07],[.16,.83,.71,.8],"waypoint",False)

    scene: dict[str, Any] = {
        "schema_version":SCHEMA,
        "scene_id":s.id,
        "source_scenario_sha256":digest(canonical_scenario_payload(s)),
        "coordinate_frame":"ENU_z_up_m",
        "meters_per_unit":1,
        "dt_seconds":s.dt,
        "bounds_m":[s.width,s.height,3.0],
        "source_split":s.split,
        "objects":objects,
        "robot":{
            "id":"veab-scout-surrogate",
            "display_name":"VEAB Scout (research surrogate; not vendor-calibrated)",
            "initial_pose_xyz_m":[s.start.x,s.start.y,.16],
            "yaw_rad":0.0,
            "footprint_radius_m":s.robot_radius,
            "height_m":.27,
            "mass_kg":8.0,
            "max_speed_m_s":s.max_speed,
            "control_mode":"planar_velocity_reference",
        },
        "waypoints_xyz_m":[[p.x,p.y,.16] for p in s.waypoints],
        "disclosure":"Geometric surrogate scene; masses/friction/sensors are not measured hardware properties.",
    }
    validate_scene(scene)
    scene["content_sha256"] = digest(scene)
    return scene


def validate_scene(scene: dict) -> None:
    if scene.get("schema_version") != SCHEMA or scene.get("coordinate_frame") != "ENU_z_up_m":
        raise ValueError("unsupported scene schema / frame")
    seen = set()
    if not 0 < len(scene.get("objects",[])) <= 120:
        raise ValueError("invalid scene object count")
    for obj in scene["objects"]:
        if not _IDENT.fullmatch(obj["id"]) or obj["id"] in seen:
            raise ValueError("duplicate or invalid scene object ID")
        seen.add(obj["id"])
        if obj["shape"] not in ("box", "cylinder"):
            raise ValueError("unsupported solid")
        vals = obj["position_m"] + obj["size_m"] + obj["rgba"]
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals):
            raise ValueError("nonfinite scene geometry")
        if any(v <= 0 for v in obj["size_m"]):
            raise ValueError("nonpositive solid dimension")
        if any(not 0 <= v <= 1 for v in obj["rgba"]):
            raise ValueError("invalid RGBA")
        if len(obj["size_m"]) != (3 if obj["shape"] == "box" else 2):
            raise ValueError("invalid solid dimension count")
        if not isinstance(obj["collision"],bool):
            raise ValueError("collision field not boolean")
    if scene.get("content_sha256"):
        expected = digest({k:v for k,v in scene.items() if k != "content_sha256"})
        if expected != scene["content_sha256"]:
            raise ValueError("scene checksum mismatch")
