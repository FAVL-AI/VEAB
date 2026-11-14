#!/usr/bin/env bash
# First-party VEAP Studio local Ubuntu service; never touches robot controls.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -e .venv/bin/python ]] || { echo 'Create Python 3.11 venv: python3.11 -m venv .venv';exit 2; }
export VEAP_STUDIO_DATA="${VEAP_STUDIO_DATA:-$HOME/veap-studio-data}"
export VEAP_MUJOCO_PYTHON="${VEAP_MUJOCO_PYTHON:-$HOME/veap-envs/mujoco/bin/python}"
export VEAP_ISAAC_PYTHON="${VEAP_ISAAC_PYTHON:-$HOME/miniforge3/envs/isaac/bin/python}"
export VEAP_LEROBOT_PYTHON="${VEAP_LEROBOT_PYTHON:-$HOME/veap-envs/lerobot/bin/python}"
export VEAP_USD_PYTHON="${VEAP_USD_PYTHON:-$PWD/.venv/bin/python}"
export VEAP_ROS_PYTHON="${VEAP_ROS_PYTHON:-/usr/bin/python3}"
exec .venv/bin/python -m uvicorn veap_studio.api:app --host 127.0.0.1 --port 8765
