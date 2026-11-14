# First-party Integration Decisions

VEAP provides its **own** timeline, topic browser, synchronized trajectory playback, annotations, geometry viewport, model registry, fault analysis and assurance report panels. No separately licensed visualization application or extension is part of the architecture.

We retain format compatibility with the open MCAP ecosystem and LeRobotDataset for data science only. The UI, evidence registry, state model, API, experiment workbench and provenance reporting are first-party implementations.

| External engine or interchange | VEAP implementation | Limitations |
|---|---|---|
| OpenUSD | Original reference scene author and asset vault | USD parser validation and complex CAD fidelity pending |
| MuJoCo | Controlled native rigid-body worker | Calibrated robot model pending |
| Isaac Sim / Isaac Lab | Controlled headless PhysX rigid-body worker | Requires installed RTX Python 3.11; not executed in package tests |
| Gazebo | Native-compatible reference SDF export | Runtime execution pending |
| ROS 2 / MCAP | Read-only capture script, local source vault, ROS2 decoder | Real recording pending |
| LeRobotDataset | Strict recorded-state/action dataset worker | Complete datasets and training tests pending |
| Unreal-quality photorealism | Original VEAP real-time scene viewport | No Unreal engine, RTX ray tracing or photorealistic capture claim |
