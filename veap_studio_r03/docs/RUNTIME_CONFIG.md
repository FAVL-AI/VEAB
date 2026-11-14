# Ubuntu integration and engine bring-up

Runtime probes assess the local API server host, not remote devices.

```bash
# Existing M3/RTX workstation environments from previous diagnostics:
export VEAP_MUJOCO_PYTHON="$HOME/veap-envs/mujoco/bin/python"
export VEAP_ISAAC_PYTHON="$HOME/miniforge3/envs/isaac/bin/python"
# Optional separately managed tools:
# export VEAP_LEROBOT_PYTHON="$HOME/veap-envs/lerobot/bin/python"
# export VEAP_USD_PYTHON="$HOME/miniforge3/envs/isaac/bin/python"
export VEAP_STUDIO_DATA="$HOME/veap-studio-data"
# For large original recordings received through rsync:
export VEAP_INBOX="$VEAP_STUDIO_DATA/inbox"
export VEAP_STUDIO_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m uvicorn veap_studio.api:app --host 127.0.0.1 --port 8765
```

Connect to `http://127.0.0.1:8765`, open Runtime Workbench and click **Probe local runtimes**. A detected Python module only establishes importability, not successful GPU initialization or calibrated physics.

## Native acceptance

Invoke MuJoCo and Isaac from the UI. Each produces a job record and `trajectory.jsonl` plus `run.json` in the local data directory. Only successfully completed jobs receive an indexed trajectory record. Contact recording is currently only in the MuJoCo worker; Isaac's contact count remains `null`, preventing false agreement statements.

MuJoCo and Isaac should first be assessed using the exact same `dt=0.005`, `steps=400` and sphere/ground geometry. Solver contact parameters, material coefficients, mass and physical invariants still require further calibration before a valid equivalence claim.

## ROS 2

ROS 2 Humble on the workstation is available at `/opt/ros/humble`; stage large source data with rsync to `$VEAP_INBOX`. Use `scripts/veap_record_ros2.sh --check` to inspect whether topics and MCAP plugin exist. Do not record on the Yahboom until its EXT4/storage and sensor health gates have passed.

## LeRobot

LeRobot is optional and runs as a separate native Python environment. The existing demo traces do not include real `/cmd_vel` actions and therefore **must not** produce LeRobot training data. Run `mcap_decode` on a real ROS2 MCAP containing odometry and command velocities, then request local dataset conversion. Training and model evaluation are future opt-in jobs.
