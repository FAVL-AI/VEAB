"""Read-only ROS2 MCAP decoder; source evidence preserved unchanged.

No publisher, actuator command, live DDS client, or source trust assertion.
"""
from __future__ import annotations
import json, math, statistics
from collections import Counter
from pathlib import Path

MAX_MESSAGES=500_000
MAX_TRAJECTORY=150_000

def yaw_from_quat(q):
    x,y,z,w=float(q.x),float(q.y),float(q.z),float(q.w)
    return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))

def decode_mcap(path, out):
    try:
        from mcap_ros2.reader import read_ros2_messages
    except ImportError as exc:
        raise RuntimeError('Install mcap and mcap-ros2-support in the VEAP Studio Python environment') from exc
    path=Path(path);out=Path(out)
    counts=Counter();types={};frame_ids=Counter();raw_times=[];poses=[];cmds=[];decode_errors=[]
    for i,m in enumerate(read_ros2_messages(path, log_time_order=True)):
        if i>=MAX_MESSAGES:
            raise ValueError(f'MCAP read limited to {MAX_MESSAGES} messages')
        topic=m.channel.topic;counts[topic]+=1;types[topic]=m.schema.name
        raw_times.append(int(m.log_time_ns))
        o=m.ros_msg
        header=getattr(o,'header',None)
        if header is not None and getattr(header,'frame_id',None):frame_ids[str(header.frame_id)]+=1
        if topic in ('/odom','/odom_raw','/odometry/filtered') and len(poses)<MAX_TRAJECTORY:
            try:
                pose=o.pose.pose
                twist=o.twist.twist
                poses.append((int(m.log_time_ns),float(pose.position.x),float(pose.position.y),
                              yaw_from_quat(pose.orientation),float(twist.linear.x),float(twist.linear.y),
                              topic))
            except (AttributeError,TypeError,ValueError) as e:
                decode_errors.append({'topic':topic,'error':str(e)[:100]})
        if topic=='/cmd_vel' and len(cmds)<MAX_TRAJECTORY:
            try:
                twist=o.twist if hasattr(o,'twist') else o
                cmds.append((int(m.log_time_ns),float(twist.linear.x),float(twist.linear.y),float(twist.angular.z)))
            except (AttributeError,TypeError,ValueError) as e:
                decode_errors.append({'topic':topic,'error':str(e)[:100]})
    if not poses:raise ValueError('No decoded odometry in MCAP; cannot construct trajectory')
    # Single odometry source is selected deterministically to avoid duplicate timestamps.
    selected='/odom' if '/odom' in counts else ('/odom_raw' if '/odom_raw' in counts else '/odometry/filtered')
    poses=[p for p in poses if p[-1]==selected]
    poses.sort(key=lambda x:x[0]);cmds.sort(key=lambda x:x[0])
    out.parent.mkdir(parents=True,exist_ok=True)
    pos_n=0;accepted_cmds=0;stale_cmds=0;last_stamp=-1;ci=0
    with out.open('w',encoding='utf-8') as f:
        for t,x,y,yaw,vx,vy,src in poses:
            if t<=last_stamp:
                continue
            last_stamp=t;pos_n+=1
            while ci+1<len(cmds) and cmds[ci+1][0]<=t:ci+=1
            cmd=None
            if cmds and cmds[ci][0]<=t and (t-cmds[ci][0])<=100_000_000:
                cmd=[round(z,6) for z in cmds[ci][1:]];accepted_cmds+=1
            else:stale_cmds+=1
            row={'t_ns':t,'x_m':x,'y_m':y,'yaw_rad':yaw,
                 'speed_m_s':math.hypot(vx,vy),'sensor_ok':True,'event':'',
                 'cmd_vel':cmd,'cmd_sync_status':'ALIGNED_WITHIN_100_MS' if cmd else 'UNAVAILABLE',
                 'source_topic':src,'source_type':'ROS2_MCAP_DECODED',
                 'clock_alignment':'LOG_TIME_ONLY_UNATTESTED'}
            f.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n')
    intervals=[b[0]-a[0] for a,b in zip(poses,poses[1:]) if b[0]>a[0]]
    return {'status':'ROS2_MCAP_DECODED','topics':dict(counts),'schemas':types,
            'frame_ids':dict(frame_ids),'selected_odometry':selected,'odometry_samples':pos_n,
            'command_samples_aligned':accepted_cmds,'command_samples_missing_or_stale':stale_cmds,
            'estimated_odom_rate_hz':round(1e9/statistics.median(intervals),3) if intervals else None,
            'decode_errors':decode_errors[:25], 'provenance':'UNATTESTED',
            'sensor_truth':'NOT_ESTABLISHED','clock_source':'RECORDER_LOG_TIME',
            'max_command_lag_ms':100,'source_record_preserved':True}
