#!/usr/bin/env python3
"""Build a small, LABELLED SYNTHETIC replay control set; not an empirical dataset."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
CONTRACT=HERE/'contracts'/'m3_nav_v1.template.json'
OUT=HERE/'examples'/'m3'
TYPE={
 '/odom':'nav_msgs/msg/Odometry',
 '/cmd_vel':'geometry_msgs/msg/Twist',
 '/scan':'sensor_msgs/msg/LaserScan',
 '/tf':'tf2_msgs/msg/TFMessage',
 '/imu/data_raw':'sensor_msgs/msg/Imu',
}

def records():
    items=[]
    for step in range(5):
        for topic in ('/odom','/cmd_vel','/scan','/tf','/imu/data_raw'):
            items.append({'schema_version':'veab.m3.record/1','topic':topic,'ros_type':TYPE[topic],
                          'log_time_ns':1_000_000_000+step*100_000_000})
    return items


def export():
    OUT.mkdir(parents=True,exist_ok=True)
    base=records()
    variants={
        'clean': (base,True,'Clean topic/time/type metadata'),
        'no_odom':([r for r in base if r['topic']!='/odom'],False,'Missing required odometry'),
        'no_cmd':([r for r in base if r['topic']!='/cmd_vel'],False,'Missing required commands'),
        'no_scan':([r for r in base if r['topic']!='/scan'],False,'Missing required lidar'),
    }
    def patch(name, edit, valid=False, comment='Synthetic negative control'):
        v=copy.deepcopy(base)
        edit(v)
        variants[name]=(v,valid,comment)
    patch('wrong_type',lambda v:v[0].update(ros_type='std_msgs/msg/String'))
    patch('backwards_timestamp',lambda v:v[20].update(log_time_ns=1_000_000_000-1))
    patch('large_gap',lambda v:[r.update(log_time_ns=r['log_time_ns']+2_000_000_000) for r in v if r['topic']=='/odom' and r['log_time_ns']>=1_300_000_000])
    patch('missing_header',lambda v:None,True,'Header clocks not required in example contract')
    patch('unknown_extra_topic',lambda v:v.append({'schema_version':'veab.m3.record/1','topic':'/diagnostics','ros_type':'diagnostic_msgs/msg/DiagnosticArray','log_time_ns':1_100_000_000}),True,'Extraneous channel is allowed')
    patch('type_flip_lidar',lambda v:next(r.update(ros_type='sensor_msgs/msg/PointCloud2') for r in v if r['topic']=='/scan'))
    patch('truncated_one_sample',lambda v:v.__setitem__(slice(None),[r for r in v if r['log_time_ns'] <1_200_000_000]),True,'Bounded window is inferred from recorded data; truncation is not independently observable without an expected window')
    manifest=[]
    for name,(rows,valid,reason) in variants.items():
        path=OUT/(name+'.jsonl')
        raw=''.join(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n' for r in rows)
        path.write_text(raw,encoding='utf-8')
        manifest.append({'id':name,'expected_topic_audit_pass':valid,'purpose':reason,
                         'sha256':hashlib.sha256(raw.encode()).hexdigest()})
    (OUT/'FIXTURE_LABELS.json').write_text(json.dumps({'source':'synthetic',
        'scientific_ground_truth':False,'labels':manifest},indent=2)+'\n')
    return manifest

if __name__=='__main__':
    for item in export(): print(f"{item['id']}: {'PASS' if item['expected_topic_audit_pass'] else 'FAIL'}")
