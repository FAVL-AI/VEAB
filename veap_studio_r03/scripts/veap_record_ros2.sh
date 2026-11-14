#!/usr/bin/env bash
# VEAP workstation-only READ-ONLY ROS 2 MCAP recording. Never publishes motion.
set -Eeuo pipefail
MODE="${1:---check}"
: "${ROS_DOMAIN_ID:=30}"
TOPICS=(/scan0 /scan1 /odom_raw /imu/data_raw /cmd_vel /tf)
if ! command -v ros2 >/dev/null; then
  if [[ -f /opt/ros/humble/setup.bash ]]; then source /opt/ros/humble/setup.bash; fi
fi
command -v ros2 >/dev/null || { echo 'ROS 2 not found'; exit 2; }
export ROS_DOMAIN_ID
[[ "$MODE" == --check || "$MODE" == --record ]] || { echo 'Use --check or --record'; exit 2; }
echo "HOST: $(hostname) / ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo 'Recording is read-only; no robot motion commands are issued.'
if [[ $(df --output=avail -B1 "$HOME" | tail -1) -lt 10737418240 ]]; then
 echo 'HOLD: less than 10 GiB available; do not start recording.';exit 3
fi
ros2 bag list storage | grep -qx 'mcap' || { echo 'HOLD: ROS 2 MCAP storage plugin unavailable'; exit 4; }
ACTIVE="$(timeout 12s ros2 topic list -t)" || { echo 'HOLD: cannot discover ROS 2 topics';exit 5; }
for topic in "${TOPICS[@]}"; do
 grep -qF "$topic [" <<< "$ACTIVE" || { echo "HOLD: required topic missing: $topic"; exit 6; }
done
if [[ "$MODE" == --check ]];then
 echo 'PREFLIGHT PASS: ROS 2 topics and MCAP available. Physical safety not assessed.';exit 0
fi
if [[ $(hostname) == yahboom ]]; then
 echo 'HOLD: Jetson device storage recovery is unresolved; record on the qualified workstation.';exit 7
fi
DIR="$HOME/veap-recordings"
mkdir -p "$DIR"
OUT="$DIR/m3_$(date -u +%Y%m%dT%H%M%SZ)"
echo "RECORDING: $OUT (bounded 30s, SIGINT termination)"
set +e
timeout --signal=INT --kill-after=8s 30s ros2 bag record -s mcap -o "$OUT" "${TOPICS[@]}"
STATUS=$?
set -e
ros2 bag info "$OUT" || { echo 'REVIEW: recording failed to close or index';exit 8; }
echo "Recording exit code: $STATUS (timeout 124 is expected for bounded capture)"
echo 'SOURCE UNATTESTED; preserve raw bag and verify timestamps before use.'
