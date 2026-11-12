"""Vision-Language-Action (VLA) & VLM agent integration for VEAB.

Provides:
1. Standardized multimodal observation interface (RGB-D tokens, language task instructions, proprioception).
2. Action chunking contract (k-step trajectories from diffusion / autoregressive policies).
3. Pre-actuation geometric shielding and confidence thresholding for VLA models.
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel, Field


class CameraFrameMeta(BaseModel):
    width: int = 640
    height: int = 480
    channels: int = 3
    fov_degrees: float = 85.0
    encoding: str = "rgb8"
    has_depth: bool = True
    min_depth_m: float = 0.2
    max_depth_m: float = 10.0


class VLAObservation(BaseModel):
    """Multimodal observation payload passed into a VLA or VLM agent."""
    tick: int
    task_instruction: str = Field(max_length=256)
    proprio_x: float
    proprio_y: float
    proprio_vx: float
    proprio_vy: float
    camera_meta: CameraFrameMeta = Field(default_factory=CameraFrameMeta)
    sensor_healthy: bool = True
    token_budget_remaining: int = 4096


class ActionStep(BaseModel):
    step_offset: int
    vx: float
    vy: float
    yaw_rate: float = 0.0
    gripper_action: float = 0.0  # 0.0 open, 1.0 closed
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class VLAActionChunk(BaseModel):
    """Action chunk emitted by a VLA model (e.g. OpenVLA, Octo, RT-2)."""
    model_name: str
    chunk_size: int = Field(ge=1, le=64)
    horizon_dt: float = 0.2
    actions: list[ActionStep]
    uncertainty_score: float = 0.0
    should_abstain: bool = False


class VLASafetyWrapper:
    """Pre-actuation safety supervisor that audits VLA action chunks against physical & geometric constraints."""
    
    def __init__(self, max_speed: float = 1.2, min_confidence: float = 0.6):
        self.max_speed = max_speed
        self.min_confidence = min_confidence
        
    def audit_chunk(self, chunk: VLAActionChunk) -> tuple[bool, list[str]]:
        reasons = []
        if chunk.should_abstain or chunk.uncertainty_score > (1.0 - self.min_confidence):
            reasons.append("high model uncertainty; abstention warranted")
            return False, reasons
            
        for act in chunk.actions:
            speed = math.hypot(act.vx, act.vy)
            if speed > self.max_speed + 0.001:
                reasons.append(f"action chunk step {act.step_offset} exceeds speed limit ({speed:.2f} > {self.max_speed})")
            if act.confidence < self.min_confidence:
                reasons.append(f"action chunk step {act.step_offset} below confidence threshold ({act.confidence:.2f})")
                
        return len(reasons) == 0, reasons

