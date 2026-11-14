"""Read-only ROS 2 Odometry subscriber. Never publishes motion commands.

Capturing ROS messages does not authenticate a sensor or verify physical truth.
ROS 2 nav_msgs/Odometry twist is expressed in the child frame, so planar
linear velocity is rotated to ENU world coordinates before recording.
"""
from __future__ import annotations
import math
import time
from ..spec import Scenario
from .scene import compile_scene
from .telemetry import PhysicsRecorder, make_sample


def capture_odometry(s:Scenario,topic:str="/odom",duration_s:float=10.,max_samples:int=1500)->dict:
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
        from nav_msgs.msg import Odometry
    except ImportError as e:
        raise RuntimeError("Requires a sourced ROS 2 environment with rclpy and nav_msgs") from e
    if not topic.startswith("/") or len(topic)>128 or not all(c.isalnum() or c in "_/-" for c in topic):
        raise ValueError("unsafe topic")
    if not 0<duration_s<=120 or not 2<=max_samples<=5000:
        raise ValueError("capture bounds exceeded")
    scene=compile_scene(s)
    recorder=PhysicsRecorder(s,"ros2",str(getattr(rclpy,"__version__","unknown")),
                            scene["content_sha256"],provenance="ros2_external_unattested")
    rclpy.init()
    node=Node("veab_read_only_odometry_capture")
    first_stamp=[None]
    last_stamp=[-1]
    frames=[]

    def received(msg):
        if len(recorder.samples)>=max_samples:
            return
        stamp=int(msg.header.stamp.sec)*1_000_000_000+int(msg.header.stamp.nanosec)
        if stamp<=last_stamp[0]:
            return  # duplicates, invalid stamps or backwards simulated clock
        last_stamp[0]=stamp
        if first_stamp[0] is None:first_stamp[0]=stamp
        t=(stamp-first_stamp[0])*1e-9
        pose=msg.pose.pose
        q=pose.orientation
        norm=q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w
        if norm<.9 or norm>1.1:
            return
        yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        twist=msg.twist.twist
        wx=math.cos(yaw)*twist.linear.x-math.sin(yaw)*twist.linear.y
        wy=math.sin(yaw)*twist.linear.x+math.cos(yaw)*twist.linear.y
        try:
            recorder.append(make_sample(len(recorder.samples),t,
                [pose.position.x,pose.position.y,pose.position.z],
                [wx,wy,twist.linear.z],[q.x,q.y,q.z,q.w],twist.angular.z,
                source_stamp_ns=stamp,sensor_integrity="unattested"))
            frames.append({"header_frame_id":msg.header.frame_id,
                           "child_frame_id":msg.child_frame_id,
                           "pose_covariance":list(msg.pose.covariance),
                           "twist_covariance":list(msg.twist.covariance)})
        except ValueError:
            pass

    try:
        qos=QoSProfile(depth=20,reliability=ReliabilityPolicy.BEST_EFFORT,
                       durability=DurabilityPolicy.VOLATILE)
        subscriber=node.create_subscription(Odometry,topic,received,qos)
        stop=time.monotonic()+duration_s
        while rclpy.ok() and time.monotonic()<stop and len(recorder.samples)<max_samples:
            rclpy.spin_once(node,timeout_sec=min(.2,max(0.,stop-time.monotonic())))
    finally:
        node.destroy_node()
        rclpy.shutdown()
    if not recorder.samples:
        raise RuntimeError("No valid Odometry messages received")
    return {"trace":recorder.finish(),"raw_ros_metadata":frames,
            "warning":"Capture is ROS 2 transport evidence, not independent hardware attestation"}
