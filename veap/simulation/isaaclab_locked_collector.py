"""VEAP Isaac Lab read-only bridge to a REAL stepping loop.

The user must supply observations from an already launched Isaac Lab environment.
This module does not create a fake Isaac environment, assume robot DOF layout,
issue commands or authenticate the simulator's raw source.
"""
from __future__ import annotations

from ..spec import Scenario
from .locked_replay import validate_tape, validate_execution
from .telemetry import PhysicsRecorder, make_sample


class IsaacLabTapeCollector:
    def __init__(self, scenario: Scenario, tape: dict, *, engine_version: str,
                 provenance_note: str = "externally_supplied_isaaclab_state_unattested"):
        validate_tape(scenario, tape)
        if not engine_version or len(engine_version) > 100:
            raise ValueError("Isaac Lab version required")
        self.scenario = scenario
        self.tape = tape
        self.recorder = PhysicsRecorder(scenario, "isaaclab", engine_version,
                                        tape["scene_sha256"], seed=tape["seed"])
        self.provenance_note = provenance_note

    def append_state(self, *, time_s: float, position_xyz_m, quaternion_xyzw,
                     velocity_xyz_m_s, angular_z_rad_s: float = 0.,
                     contacts: int | None = None):
        """Read actual root state AFTER each native physics step (tick 0 is initial).

        Quaternion is XYZW. Isaac versions may provide WXYZ; convert explicitly
        at the native collection call site, never infer quaternion ordering.
        """
        tick = len(self.recorder.samples)
        if tick > len(self.tape["commands_vx_vy_yaw"]):
            raise ValueError("more observations than frozen command tape")
        command = [0., 0., 0.] if tick == 0 else self.tape["commands_vx_vy_yaw"][tick-1]
        self.recorder.append(make_sample(tick, time_s, position_xyz_m,
                          velocity_xyz_m_s, quaternion_xyzw,
                          angular_z_rad_s, command, contacts=contacts))

    def finish(self) -> dict:
        trace = self.recorder.finish("unknown")
        report = validate_execution(self.scenario, self.tape, trace)
        return {"schema_version": "veab-isaaclab-observation-bridge/1",
                "trace": trace, "control_contract": report,
                "source_status": self.provenance_note,
                "native_execution_asserted_by_veab": False,
                "scope": "Observer of externally stepped Isaac Lab environment; no physics, sensing or provenance certification"}
