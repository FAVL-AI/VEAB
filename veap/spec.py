"""Validated, immutable scenario input contract. Never load executable task code."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT / "scenarios"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Circle(StrictModel):
    x: float
    y: float
    radius: float = Field(gt=0, le=10)
    label: str = Field(max_length=64)


class Rect(StrictModel):
    x1: float
    y1: float
    x2: float
    y2: float
    label: str = Field(max_length=64)

    @model_validator(mode="after")
    def ordered(self):
        if not (self.x1 < self.x2 and self.y1 < self.y2):
            raise ValueError("forbidden rectangle must have positive area")
        return self


class Point(StrictModel):
    x: float
    y: float
    label: str = Field(max_length=80)


class Fault(StrictModel):
    kind: str = Field(pattern="^(sensor_dropout|actuator_stall|perception_noise|communication_delay)$")
    start_step: int = Field(ge=1, le=2000)
    duration_steps: int = Field(ge=1, le=100)


class Scenario(StrictModel):
    schema_version: str = "veap-scenario/1"
    id: str = Field(pattern="^[a-z0-9-]+$", max_length=64)
    title: str = Field(max_length=120)
    description: str = Field(max_length=300)
    family: str = Field(pattern="^(navigation|inspection|absence|manipulation)$")
    split: str = Field(pattern="^(train|validation|test)$")
    width: float = Field(ge=3, le=100)
    height: float = Field(ge=3, le=100)
    dt: float = Field(default=0.2, gt=0, le=1)
    max_steps: int = Field(default=260, ge=10, le=2000)
    max_speed: float = Field(default=1.0, gt=0, le=3)
    robot_radius: float = Field(default=0.22, gt=0, le=1)
    waypoint_tolerance: float = Field(default=0.36, gt=0, le=1.5)
    max_contact_force_n: float | None = Field(default=None, gt=0, le=1000)
    grasp_tolerance: float | None = Field(default=None, gt=0, le=1.0)
    start: Point
    waypoints: list[Point] = Field(max_length=12)
    obstacles: list[Circle] = Field(default_factory=list, max_length=50)
    forbidden_zones: list[Rect] = Field(default_factory=list, max_length=20)
    faults: list[Fault] = Field(default_factory=list, max_length=10)
    target_present: bool = True

    @model_validator(mode="after")
    def check_topology(self):
        if (self.family == "absence") != (not self.target_present):
            raise ValueError("absence tasks must use target_present=false and vice versa")
        if self.target_present and not self.waypoints:
            raise ValueError("non-absence task needs waypoints")
        if self.family == "absence" and self.waypoints:
            raise ValueError("absence task has no reachable goal")
        for p in [self.start, *self.waypoints]:
            if not (0 <= p.x <= self.width and 0 <= p.y <= self.height):
                raise ValueError("point outside scenario bounds")
        if any(f.start_step + f.duration_steps > self.max_steps + 1 for f in self.faults):
            raise ValueError("fault outside episode length")
        return self


def scenario_files() -> list[Path]:
    return sorted(SCENARIO_DIR.glob("*.json"))


def load_scenario(scenario_id: str) -> Scenario:
    if not scenario_id or not all(c.isascii() and (c.islower() or c.isdigit() or c == "-") for c in scenario_id):
        raise ValueError("invalid scenario identifier")
    path = SCENARIO_DIR / f"{scenario_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown scenario: {scenario_id}")
    s = Scenario.model_validate_json(path.read_text(encoding="utf-8"))
    if s.id != scenario_id:
        raise ValueError("scenario ID and filename disagree")
    return s


def list_scenarios() -> list[Scenario]:
    return [load_scenario(p.stem) for p in scenario_files()]
