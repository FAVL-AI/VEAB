# ROS 2 / Isaac Lab data adapter contract (next engineering milestone)

**Current status:** design and read-only JSONL importer exist. There is **no** native `rclpy`, MCAP/rosbag2, Isaac Lab or Unitree command integration in v0.1.

## Capture first, control later

Create a separate read-only ROS 2 node that subscribes to ground-truth pose, odometry, collision sensors, commanded and executed twist, obstacle observations, driver status, energy monitoring and e-stop, using synchronised timestamps. Record raw original MCAP and a provenance manifest **before** converting for VEAB. Never infer real-world forces or Joules from the toy simulator's velocity proxy.

Recommended future raw source topics (examples only; validate actual robot topics):

- `/odom` or ground-truth pose with reference frame and covariance
- `/tf`, `/tf_static` with transform-tree version
- `/scan` and `/camera/depth/image_raw` with sensor calibration
- read-only driver status, estop state and executed velocity
- power/current telemetry calibrated with time synchronisation

## Minimal JSONL interchange supported today

One JSON object per line:

```json
{"tick":0,"x":1.0,"y":1.0,"vx":0.0,"vy":0.0}
{"tick":1,"x":1.1,"y":1.0,"vx":0.5,"vy":0.0}
```

The exact continuous tick count is required and each step uses the scenario's `dt`. It converts telemetry to `state` and geometric `milestone` events with the original input file hash. Such milestones are **geometric observations**, not authenticated source evidence. The independent verifier marks provenance unknown and refuses verified status.

## Required upgrade for ROS2/MCAP production candidate

- Signed capture manifests containing source topics, sensor serial/calibration, software build, immutable bag hash, PTP/NTP sync quality, robot ID, map coordinate reference, latency provenance and data-governance controls.
- A trusted external tool/robot runtime that enforces endpoint-level read-only access and an independent emergency-stop chain.
- Reconstruct action/observation causality from authoritative clocks; reject missing spans, reordering, late packets and inconsistent coordinate frames.
- Calibrated replay in Isaac Lab or simulator and cross-checks against measured hardware trace. Sensor noise distribution and contact semantics must be empirically validated.
- Match test policy and actual controller execution; all delays and emergency-stops must be recorded, not inferred from eventual goal completion.
- Separate verifiable process outcomes from any claim that actions are physically safe under unobserved conditions.

Current primary docs: https://github.com/ros2/rosbag2 and https://isaac-sim.github.io/IsaacLab/develop/source/tutorials/03_envs/create_direct_rl_env.html
