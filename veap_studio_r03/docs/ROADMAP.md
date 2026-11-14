# VEAP Research and Product Release Programme

**R0.3 — First-party native workbench (implemented software)**
- Own original GUI, local recording vault, trace/event replay, original assurance panels and counterfactual faults.
- Runtime capability probes and bounded native-engine experiment jobs.
- Source lineage: MCAP source -> derived odometry/recorded action trace -> optional LeRobotDataset.
- OpenUSD/MJCF/SDF source interchange. No external visualization service.

**R0.4 — Native evidence validation**
- Execute and record independent Isaac Lab 2.3.2 and MuJoCo 4.0.1 physics on RTX workstation.
- PhysX contacts and external reference comparison, cross-engine model calibration, repeated trials.
- Real ROS2 MCAP smoke on a qualified workstation and true message type handling.

**R0.5 — Reconstruction and Learning**
- Calibrated LiDAR/RGBD registration with clock/TF audits, volumetric reconstruction and CAD fidelity report.
- Stable LeRobotDataset v3 conversion, training run IDs, ACT/SmolVLA baselines with matched harnesses.

**R0.6 — Engineering trials**
- Gazebo native SDF execution, simulator-parity harness, physically realistic M3 and G1 digital twins.
- Independent monitors with blinded adjudication, fault recovery metrics and null-result publication.

**R0.7+ — Customer pilot and enterprise qualification**
- OIDC/RBAC/ABAC, protected object storage, PostgreSQL, isolated workers, retention and restore tests.
- Industrial recorded/shadow-mode pilots; external security assessment; documented customer acceptance.

No stage is labelled production validated unless its own acceptance criteria are independently met.
