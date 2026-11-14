"""Framework-safe observer for collecting Isaac Lab root-state trajectories.

Attach to a REAL Isaac Lab environment loop after env.step(), not in the
VEAB toy simulator. This instrument does not launch or fabricate Isaac physics.
"""
from __future__ import annotations
from .telemetry import PhysicsRecorder, make_sample


def tensor_row(vector,env_index=0):
    """Convert one non-grad batch row from Isaac Lab/PyTorch to a Python list."""
    value=vector[env_index]
    if hasattr(value,"detach"):
        value=value.detach().cpu()
    if hasattr(value,"tolist"):
        return value.tolist()
    return list(value)


class IsaacLabRootRecorder:
    """Capture real Isaac Lab ArticulationData.root_pos_w, root_quat_w, root_lin_vel_w.

    Input quaternions must be normalized to XYZW by the caller. Older Isaac Lab
    versions use WXYZ. Do not silently exchange the component order.
    """
    def __init__(self,scenario,scene_sha256,isaaclab_version,seed=None):
        self.recorder=PhysicsRecorder(scenario,"isaaclab",isaaclab_version,scene_sha256,seed)

    def append(self,time_s,pos_xyz,quat_xyzw,linvel_xyz,angvel_z=0.,command=(0,0,0)):
        self.recorder.append(make_sample(len(self.recorder.samples),time_s,
              pos_xyz,linvel_xyz,quat_xyzw,angvel_z,command))

    def finish(self,claim="unknown"):
        return self.recorder.finish(claim)
