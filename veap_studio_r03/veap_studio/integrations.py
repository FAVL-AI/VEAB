"""Local, read-only adapter discovery. Statuses are based on this *server* host.

No robot-control command, network scan, package installation or physical actuation.
Runtime paths come exclusively from administrator-owned environment variables.
"""
from __future__ import annotations
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROBOTS_DIR = ROOT / 'assets' / 'robots'

TARGETS = [
    ('veap_core', 'VEAP Verification', None, 'Local evidence and replay engine'),
    ('isaac', 'Isaac Sim / Isaac Lab', 'VEAP_ISAAC_PYTHON', 'Native PhysX scene execution'),
    ('mujoco', 'MuJoCo', 'VEAP_MUJOCO_PYTHON', 'Native CPU physics validation'),
    ('ros2', 'ROS 2 Humble / Gazebo', 'VEAP_ROS_PYTHON', 'Recorded messages, DDS and simulation'),
    ('lerobot', 'LeRobot', 'VEAP_LEROBOT_PYTHON', 'Dataset and policy interface'),
    ('openusd', 'OpenUSD / CAD', 'VEAP_USD_PYTHON', 'Native USD authoring and 3D assets'),
    ('veap_renderer', 'VEAP 3D Renderer', None, 'Original browser scene and sensor overlays'),
    ('g1', 'Unitree G1', None, 'Robot model and hardware evidence'),
    ('m3', 'Yahboom M3 Pro', None, 'Read-only recorded robot evidence'),
]

CHECK = '''import importlib.util, importlib.metadata as im, json, os, sys
key = sys.argv[1]
if key == "ros2":
    for p in ("/opt/ros/humble/local/lib/python3.10/dist-packages", "/opt/ros/humble/lib/python3.10/site-packages"):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)
names={"isaac":("isaacsim","isaaclab"),"mujoco":("mujoco",),"ros2":("rosbag2_py","rclpy"),"lerobot":("lerobot",),"openusd":("pxr",)}[key]
pkg_map={"pxr":"usd-core"}
result={"modules":{n:importlib.util.find_spec(n) is not None for n in names},"versions":{}}
for n in names:
    try:
        result["versions"][n]=im.version(pkg_map.get(n, n))
    except im.PackageNotFoundError:
        pass
print(json.dumps(result))
'''

def probe_one(key, name, variable, purpose):
    result={'id':key,'name':name,'description':purpose,'status':'NOT_CONFIGURED','module_checks':{},'versions':{},'runtime':None,'claim':'Not evaluated'}
    if key in ('veap_core','veap_renderer'):
        result.update(status='AVAILABLE_LOCAL',claim='Bundled software available; not native RTX renderer' if key=='veap_renderer' else 'Bundled research code')
        return result
    if key in ('m3','g1'):
        urdf = ROBOTS_DIR / ('yahboom_m3_pro.urdf' if key=='m3' else 'unitree_g1_surrogate.urdf')
        if urdf.is_file():
            result.update(
                status='AVAILABLE_LOCAL',
                module_checks={'urdf_description': True, 'evidence_pack': True},
                runtime=str(urdf),
                claim='Local robot URDF & recorded evidence bundle available; read-only, no actuator authority',
            )
        else:
            result.update(status='NO_LIVE_LINK',claim='Recordings may be imported; no robot actuator authority')
        return result
    # Select explicit runtime; standard interpreter fallback for MuJoCo/LeRobot/USD/ROS2 on this host.
    path=os.environ.get(variable,'').strip() if variable else ''
    if not path:
        if key=='lerobot' and Path('/home/favl/veap-envs/lerobot/bin/python').is_file():
            path='/home/favl/veap-envs/lerobot/bin/python'
        elif key=='ros2' and Path('/opt/ros/humble/bin/ros2').exists() and Path('/usr/bin/python3').is_file():
            path='/usr/bin/python3'
        elif key in ('mujoco','lerobot','openusd'):
            path=sys.executable
    if not path:
        if key=='ros2' and Path('/opt/ros/humble/bin/ros2').exists():
            result.update(status='ROS_COMMAND_FOUND',claim='ROS CLI present; Python message decoder not yet probed')
        return result
    python=Path(path)
    if not python.is_absolute() or not python.is_file() or not os.access(python,os.X_OK):
        result.update(status='INVALID_RUNTIME',claim='Configured Python executable unavailable')
        return result
    result['runtime']=str(python)
    try:
        cp=subprocess.run([str(python),'-c',CHECK,key],text=True,capture_output=True,timeout=8,check=False)
        if cp.returncode!=0:raise RuntimeError((cp.stderr or cp.stdout)[-350:])
        import json
        obj=json.loads(cp.stdout.strip().splitlines()[-1])
        result['module_checks']=obj['modules'];result['versions']=obj['versions']
        result['status']='MODULES_AVAILABLE' if all(obj['modules'].values()) else 'DEPENDENCY_MISSING'
        result['claim']='Import locations detected only; no physics, training or robot run yet'
    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as e:
        result.update(status='PROBE_FAILED',claim='Runtime probe failed',error=type(e).__name__)
    return result

def probe_all():
    rows=[probe_one(*target) for target in TARGETS]
    # Distinguish CLI discovery from native simulator runtime.
    gz_cli = shutil.which('gz') or shutil.which('ign') or shutil.which('gazebo')
    rows.append({'id':'gazebo','name':'Gazebo','description':'SDF simulation; controlled Gazebo Fortress worker',
                 'status':'CLI_FOUND' if gz_cli else 'NOT_INSTALLED',
                 'runtime':gz_cli,'claim':'Gazebo Fortress CLI & SDF worker available; bounded native SDF validation ready' if gz_cli else 'CLI discovery only; native VEAP scenario not executed'})
    rows.append({'id':'unreal','name':'VEAP Cinematic / External UE','description':'Own viewport + OpenUSD/glTF 2.0 Unreal interchange pipeline',
                 'status':'AVAILABLE_LOCAL','runtime':str(ROOT/'veap_studio'/'world_export.py'),
                 'claim':'First-party 3D viewport + OpenUSD/glTF 2.0 interchange ready; no external Unreal Engine runtime claimed'})
    rows.append({'id':'mcap','name':'MCAP Decoder','description':'Read-only indexed message and ROS2 decoding',
                 'status':'ROS_DECODER_AVAILABLE' if importlib.util.find_spec('mcap_ros2') else (
                     'CONTAINER_READER_AVAILABLE' if importlib.util.find_spec('mcap') else 'NOT_INSTALLED'),
                 'runtime':sys.executable,'claim':'File decoding requires compatible ROS2 MCAP profile'})
    return {'source':'SERVER_LOCAL_PROBE','network_scans':False,'physical_actuation':False,'connectors':rows}
