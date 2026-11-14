"""Native engine availability, not simulated/pretend success flags."""
from __future__ import annotations
import importlib.util
import shutil
import sys


def engine_status() ->dict:
    candidates={
        "mujoco":{"available":importlib.util.find_spec("mujoco") is not None,"interface":"Python MjModel / mj_step","execution":"native adapter"},
        "gazebo":{"available":shutil.which("gz") is not None,"interface":"Gazebo SDF and ros_gz","execution":"external process"},
        "ros2":{"available":shutil.which("ros2") is not None and importlib.util.find_spec("rclpy") is not None,"interface":"read-only rclpy Odometry capture","execution":"external ROS graph"},
        "isaaclab":{"available":importlib.util.find_spec("isaaclab") is not None,"interface":"OpenUSD and root-state recorder","execution":"requires native Isaac Lab runtime"},
        "isaacsim":{"available":importlib.util.find_spec("isaacsim") is not None,"interface":"OpenUSD import and physics authoring","execution":"requires Isaac Sim Kit"},
        "unreal":{"available":False,"interface":"USD Stage import and optional Pixel Streaming","execution":"requires independent Unreal Editor install"},
    }
    return {"platform_python":sys.version.split()[0],"engines":candidates,
            "warning":"Export availability is not engine integration validation."}
