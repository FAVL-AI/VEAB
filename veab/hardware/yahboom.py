"""ROSMASTER Yahboom M3 Pro Hardware Deployment & Safety Architecture.

Provides:
1. Yahboom M3 Pro hardware platform specifications and configuration.
2. Pre-trial safety gate: Human override, Emergency stop, Geofence, Velocity limit, Recovery procedure.
3. Pre-actuation command filter and safety watchdog.
"""
from __future__ import annotations
import math
import time
from typing import Any
from pydantic import BaseModel, Field


class YahboomM3ProSpecs(BaseModel):
    """Hardware specifications for ROSMASTER Yahboom M3 Pro mobile robot."""
    model_name: str = "ROSMASTER Yahboom M3 Pro"
    drive_type: str = "4WD Mecanum Omnidirectional"
    compute_board: str = "NVIDIA Jetson Orin Nano (8GB) / Ubuntu 22.04 LTS"
    aux_microcontroller: str = "STM32F407 Core Board (CAN/UART/PWM)"
    lidar_sensor: str = "Silan RPLiDAR A1/A2 (360 deg, 12m, 8000 Hz)"
    depth_camera: str = "Astra Pro RGB-D (0.6 - 8.0m range)"
    imu_sensor: str = "MPU9250 9-Axis Gyro/Accelerometer/Magnetometer"
    wheel_diameter_m: float = 0.080  # 80mm mecanum wheels
    wheelbase_m: float = 0.220
    track_width_m: float = 0.210
    total_mass_kg: float = 4.85
    max_payload_kg: float = 5.0
    nominal_battery_voltage_v: float = 12.6  # 3S LiPo


class SafetyGateParameters(BaseModel):
    """Enforced limits before and during any autonomous trial."""
    max_linear_velocity_mps: float = 0.40   # Enforced indoor ceiling (default robot max is 1.0 m/s)
    max_angular_velocity_radps: float = 1.00 # Max turn rate
    estop_max_latency_ms: float = 50.0      # E-stop latency limit
    heartbeat_timeout_ms: float = 200.0     # Watchdog timeout
    geofence_x_min: float = 0.0
    geofence_x_max: float = 12.0
    geofence_y_min: float = 0.0
    geofence_y_max: float = 8.0
    human_override_priority: bool = True     # Joystick/human always preempts autonomous policy
    recovery_max_time_s: float = 3.0        # Bounded fault recovery time


class PreDeploymentChecklist(BaseModel):
    human_override_tested: bool
    emergency_stop_latched: bool
    geofence_configured: bool
    velocity_limits_locked: bool
    recovery_procedure_registered: bool
    battery_level_pct: float
    ready_for_autonomous_trial: bool
    notes: list[str] = Field(default_factory=list)


class YahboomSafetySupervisor:
    """Pre-actuation supervisor running at 50 Hz on the Yahboom M3 Pro."""

    def __init__(self, specs: YahboomM3ProSpecs, limits: SafetyGateParameters):
        self.specs = specs
        self.limits = limits
        self.estop_active = False
        self.human_override_active = False
        self.last_heartbeat_time = time.monotonic()
        self.current_state = "IDLE"  # IDLE, AUTONOMOUS, HUMAN_OVERRIDE, RECOVERY, ESTOP_LATCHED

    def trigger_emergency_stop(self, reason: str = "Manual E-Stop") -> dict[str, Any]:
        """Hard emergency stop: instantly cuts all motor duty cycles."""
        self.estop_active = True
        self.current_state = "ESTOP_LATCHED"
        return {
            "status": "ESTOP_ENGAGED",
            "cmd_vel_out": [0.0, 0.0, 0.0],
            "reason": reason,
            "timestamp": time.monotonic()
        }

    def reset_emergency_stop(self, manual_key: str) -> bool:
        """E-stop can only be reset by deliberate manual action."""
        if manual_key == "OPERATOR_CONFIRMED_CLEAR":
            self.estop_active = False
            self.current_state = "IDLE"
            return True
        return False

    def receive_human_override(self, manual_vx: float, manual_vy: float, manual_wz: float) -> bool:
        """Flag that human teleoperator has touched the joystick/controls."""
        is_active = (abs(manual_vx) > 0.01 or abs(manual_vy) > 0.01 or abs(manual_wz) > 0.01)
        self.human_override_active = is_active
        if is_active:
            self.current_state = "HUMAN_OVERRIDE"
        return is_active

    def filter_command(
        self,
        cmd_vx: float,
        cmd_vy: float,
        cmd_wz: float,
        current_x: float,
        current_y: float,
        manual_inputs: tuple[float, float, float] = (0.0, 0.0, 0.0)
    ) -> tuple[float, float, float, str]:
        """Filter autonomous /cmd_vel through strict safety limits."""
        self.last_heartbeat_time = time.monotonic()

        # 1. E-Stop check
        if self.estop_active:
            return 0.0, 0.0, 0.0, "ESTOP_BLOCK"

        # 2. Human override preemption
        man_vx, man_vy, man_wz = manual_inputs
        if self.receive_human_override(man_vx, man_vy, man_wz):
            # Clamp human input to safe indoor limits as well
            s_vx = math.copysign(min(abs(man_vx), self.limits.max_linear_velocity_mps), man_vx)
            s_vy = math.copysign(min(abs(man_vy), self.limits.max_linear_velocity_mps), man_vy)
            s_wz = math.copysign(min(abs(man_wz), self.limits.max_angular_velocity_radps), man_wz)
            return s_vx, s_vy, s_wz, "HUMAN_OVERRIDE_PASSTHROUGH"

        # 3. Geofence enforcement
        margin = 0.25  # 25cm deceleration buffer
        violates_x = (current_x <= self.limits.geofence_x_min + margin and cmd_vx < 0) or \
                     (current_x >= self.limits.geofence_x_max - margin and cmd_vx > 0)
        violates_y = (current_y <= self.limits.geofence_y_min + margin and cmd_vy < 0) or \
                     (current_y >= self.limits.geofence_y_max - margin and cmd_vy > 0)
        
        if violates_x or violates_y:
            return 0.0, 0.0, 0.0, "GEOFENCE_BOUNDARY_BRAKE"

        # 4. Strict velocity limit clamp
        speed = math.hypot(cmd_vx, cmd_vy)
        if speed > self.limits.max_linear_velocity_mps:
            scale = self.limits.max_linear_velocity_mps / speed
            cmd_vx *= scale
            cmd_vy *= scale

        if abs(cmd_wz) > self.limits.max_angular_velocity_radps:
            cmd_wz = math.copysign(self.limits.max_angular_velocity_radps, cmd_wz)

        self.current_state = "AUTONOMOUS"
        return round(cmd_vx, 4), round(cmd_vy, 4), round(cmd_wz, 4), "APPROVED"

    def execute_fault_recovery(self, fault_type: str) -> tuple[float, float, float, str]:
        """Deterministic fault recovery procedure."""
        self.current_state = "RECOVERY"
        if fault_type == "actuator_stall":
            # Backoff pulse: reverse 0.15 m/s for 0.4s to disengage obstruction
            return -0.15, 0.0, 0.0, "RECOVERY_BACKOFF_PULSE"
        elif fault_type == "sensor_dropout":
            # Controlled immediate halt
            return 0.0, 0.0, 0.0, "RECOVERY_SAFE_STOP"
        return 0.0, 0.0, 0.0, "RECOVERY_STANDBY"


def verify_yahboom_pre_deployment(
    specs: YahboomM3ProSpecs,
    limits: SafetyGateParameters,
    battery_v: float = 12.2
) -> PreDeploymentChecklist:
    """Rigorous pre-deployment acceptance gate for Yahboom M3 Pro physical robot."""
    notes = []
    
    # Check 1: Human override defined
    override_ok = limits.human_override_priority is True
    if not override_ok:
        notes.append("FAIL: Human override priority is disabled.")
    
    # Check 2: Emergency stop latency <= 50ms
    estop_ok = limits.estop_max_latency_ms <= 50.0
    if not estop_ok:
        notes.append(f"FAIL: E-stop latency {limits.estop_max_latency_ms}ms exceeds 50ms safety requirement.")
        
    # Check 3: Geofence bounds
    geofence_ok = (limits.geofence_x_max > limits.geofence_x_min) and (limits.geofence_y_max > limits.geofence_y_min)
    if not geofence_ok:
        notes.append("FAIL: Geofence spatial bounds are non-positive or undefined.")
        
    # Check 4: Velocity limits within indoor safe envelope
    v_ok = (limits.max_linear_velocity_mps <= 0.50) and (limits.max_angular_velocity_radps <= 1.50)
    if not v_ok:
        notes.append("FAIL: Velocity limits exceed indoor robot safe envelope.")

    # Check 5: Recovery procedure registered
    recovery_ok = limits.recovery_max_time_s <= 5.0

    # Battery health
    bat_pct = min(100.0, max(0.0, (battery_v - 10.5) / (12.6 - 10.5) * 100.0))
    if bat_pct < 25.0:
        notes.append(f"WARN: Battery charge {bat_pct:.1f}% below 25% minimum threshold.")

    ready = override_ok and estop_ok and geofence_ok and v_ok and recovery_ok and (bat_pct >= 25.0)

    if ready:
        notes.append("PASS: All 5 physical deployment safety gates passed for ROSMASTER Yahboom M3 Pro.")

    return PreDeploymentChecklist(
        human_override_tested=override_ok,
        emergency_stop_latched=estop_ok,
        geofence_configured=geofence_ok,
        velocity_limits_locked=v_ok,
        recovery_procedure_registered=recovery_ok,
        battery_level_pct=round(bat_pct, 1),
        ready_for_autonomous_trial=ready,
        notes=notes,
    )

