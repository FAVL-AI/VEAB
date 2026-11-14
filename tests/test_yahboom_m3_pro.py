"""Test Stage 5: Physical deployment safety gates for ROSMASTER Yahboom M3 Pro."""
import pytest
from veap.hardware.yahboom import (
    YahboomM3ProSpecs,
    SafetyGateParameters,
    YahboomSafetySupervisor,
    verify_yahboom_pre_deployment,
)

def test_yahboom_pre_deployment_acceptance_gate():
    specs = YahboomM3ProSpecs()
    limits = SafetyGateParameters(
        max_linear_velocity_mps=0.40,
        max_angular_velocity_radps=1.00,
        estop_max_latency_ms=30.0,
        human_override_priority=True,
    )

    checklist = verify_yahboom_pre_deployment(specs, limits, battery_v=12.4)
    assert checklist.ready_for_autonomous_trial is True
    assert checklist.human_override_tested is True
    assert checklist.emergency_stop_latched is True
    assert checklist.geofence_configured is True
    assert checklist.velocity_limits_locked is True
    assert checklist.recovery_procedure_registered is True
    assert checklist.battery_level_pct > 80.0

def test_yahboom_pre_deployment_fails_on_unsafe_limits():
    specs = YahboomM3ProSpecs()
    unsafe_limits = SafetyGateParameters(
        max_linear_velocity_mps=1.50,  # Exceeds safe indoor envelope
        estop_max_latency_ms=120.0,    # Unacceptably slow e-stop
        human_override_priority=False  # Refuses human override!
    )
    checklist = verify_yahboom_pre_deployment(specs, unsafe_limits, battery_v=11.0)
    assert checklist.ready_for_autonomous_trial is False
    assert len(checklist.notes) >= 3

def test_yahboom_safety_supervisor_enforces_all_invariants():
    specs = YahboomM3ProSpecs()
    limits = SafetyGateParameters(
        max_linear_velocity_mps=0.40,
        max_angular_velocity_radps=1.0,
        geofence_x_min=0.0,
        geofence_x_max=10.0,
        geofence_y_min=0.0,
        geofence_y_max=10.0,
    )
    sup = YahboomSafetySupervisor(specs, limits)

    # 1. Normal command clamped to max velocity
    vx, vy, wz, status = sup.filter_command(cmd_vx=0.80, cmd_vy=0.0, cmd_wz=0.0, current_x=5.0, current_y=5.0)
    assert status == "APPROVED"
    assert vx == 0.40  # Clamped to 0.40 m/s

    # 2. Geofence boundary brake
    vx, vy, wz, status = sup.filter_command(cmd_vx=0.30, cmd_vy=0.0, cmd_wz=0.0, current_x=9.9, current_y=5.0)
    assert status == "GEOFENCE_BOUNDARY_BRAKE"
    assert vx == 0.0 and vy == 0.0

    # 3. Human override preemption
    vx, vy, wz, status = sup.filter_command(
        cmd_vx=0.30, cmd_vy=0.0, cmd_wz=0.0,
        current_x=5.0, current_y=5.0,
        manual_inputs=(-0.25, 0.0, 0.5)  # Human pulls back on joystick
    )
    assert status == "HUMAN_OVERRIDE_PASSTHROUGH"
    assert vx == -0.25
    assert wz == 0.5

    # 4. Emergency Stop blocks everything
    sup.trigger_emergency_stop(reason="Obstacle collision sensor triggered")
    assert sup.estop_active is True
    vx, vy, wz, status = sup.filter_command(cmd_vx=0.2, cmd_vy=0.0, cmd_wz=0.0, current_x=5.0, current_y=5.0)
    assert status == "ESTOP_BLOCK"
    assert vx == 0.0 and vy == 0.0 and wz == 0.0

    # Reset with proper key
    assert sup.reset_emergency_stop("OPERATOR_CONFIRMED_CLEAR") is True
    assert sup.estop_active is False

    # 5. Fault recovery action
    rx, ry, rw, r_status = sup.execute_fault_recovery("actuator_stall")
    assert r_status == "RECOVERY_BACKOFF_PULSE"
    assert rx == -0.15

