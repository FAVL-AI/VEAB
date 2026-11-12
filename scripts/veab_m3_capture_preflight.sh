#!/usr/bin/env bash
# Read-only ROS 2 inventory; performs no actuator or lifecycle operation.
set -euo pipefail
source /opt/ros/humble/setup.bash
printf '\n=== ROS 2 distro / domain ===\n'
echo "ROS_DISTRO=${ROS_DISTRO:-none} ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-default}"
printf '\n=== Topic names and ROS message types ===\n'
ros2 topic list -t
printf '\n=== MCAP storage plugin ===\n'
if command -v dpkg-query >/dev/null; then
  dpkg-query -W -f='${Status} ${Version}\n' ros-humble-rosbag2-storage-mcap || true
fi
printf '\n=== No messages recorded and no commands sent ===\n'
