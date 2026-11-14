"""VEAP-owned cross-engine geometric interchange source.
Exports simple reference primitives; no calibrated dynamics or CAD fidelity claim.
"""
from __future__ import annotations
import hashlib, json, shutil, subprocess, xml.etree.ElementTree as ET
from pathlib import Path

SCENE={'schema':'veap.scene.v1','name':'VEAP Reference World','up_axis':'Z','units':'meters',
       'ground':[12.0,10.0], 'robot':{'kind':'sphere_surrogate','radius_m':.1,'mass_kg':1.0,'xyz':[0,0,1]},
       'obstacles':[{'xyz':[4,3,.5],'radius_m':.4,'height_m':1.0},
                    {'xyz':[7,6,.5],'radius_m':.6,'height_m':1.0}]}

def sha_obj(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def export_reference_world(outdir):
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    digest=sha_obj(SCENE)
    usd='''#usda 1.0
(
    defaultPrim = "World"
    metersPerUnit = 1
    upAxis = "Z"
)
def Xform "World"
{
    def Cube "Floor"
    {
        double size = 1
        double3 xformOp:scale = (12, 10, 0.1)
        double3 xformOp:translate = (6, 5, -0.05)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }
    def Sphere "RobotSurrogate"
    {
        double radius = 0.1
        double3 xformOp:translate = (0, 0, 1)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def Cylinder "ObstacleA"
    {
        double radius = 0.4
        double height = 1
        double3 xformOp:translate = (4, 3, 0.5)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def Cylinder "ObstacleB"
    {
        double radius = 0.6
        double height = 1
        double3 xformOp:translate = (7, 6, 0.5)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
}
'''
    usda_path = out/'veap_reference.usda'
    usda_path.write_text(usd,encoding='utf-8')
    usd_valid = False
    try:
        from pxr import Usd
        stage = Usd.Stage.Open(str(usda_path))
        usd_valid = stage is not None and bool(stage.GetPrimAtPath('/World/RobotSurrogate'))
    except Exception:
        usd_valid = False

    mjcf='''<mujoco model="veap_reference"><compiler angle="radian"/>
<option timestep="0.005" gravity="0 0 -9.81"/><worldbody>
<geom name="floor" type="plane" size="6 5 0.1" pos="6 5 0"/>
<body name="robot_surrogate" pos="0 0 1"><freejoint/><geom type="sphere" size="0.1" mass="1"/></body>
<body name="obstacle_a" pos="4 3 0.5"><geom type="cylinder" size="0.4 0.5"/></body>
<body name="obstacle_b" pos="7 6 0.5"><geom type="cylinder" size="0.6 0.5"/></body>
</worldbody></mujoco>'''
    ET.fromstring(mjcf);(out/'veap_reference.xml').write_text(mjcf,encoding='utf-8')
    sdf='''<?xml version="1.0"?><sdf version="1.8"><world name="veap_reference">
<gravity>0 0 -9.81</gravity><model name="floor"><static>true</static><link name="ground"><collision name="col"><geometry><box><size>12 10 0.1</size></box></geometry></collision><pose>6 5 -0.05 0 0 0</pose></link></model>
<model name="sphere_surrogate"><pose>0 0 1 0 0 0</pose><link name="body"><inertial><mass>1</mass><inertia><ixx>0.004</ixx><iyy>0.004</iyy><izz>0.004</izz></inertia></inertial><collision name="c"><geometry><sphere><radius>0.1</radius></sphere></geometry></collision></link></model></world></sdf>'''
    sdf_path = out/'veap_reference.sdf'
    ET.fromstring(sdf);sdf_path.write_text(sdf,encoding='utf-8')
    sdf_valid = False
    gz_cli = shutil.which('gz') or shutil.which('ign')
    if gz_cli:
        try:
            cp = subprocess.run([gz_cli, 'sdf', '-k', str(sdf_path)], capture_output=True, text=True, timeout=8, check=False)
            sdf_valid = cp.returncode == 0
        except Exception:
            sdf_valid = False

    gltf={
        'asset':{'version':'2.0','generator':'VEAP Studio R0.3 Cinematic / UE Interchange'},
        'scene':0,
        'scenes':[{'name':'VEAP_Reference_World','nodes':[0,1,2,3]}],
        'nodes':[
            {'name':'Floor','translation':[6.0,5.0,-0.05],'scale':[12.0,10.0,0.1]},
            {'name':'RobotSurrogate','translation':[0.0,0.0,1.0],'extras':{'radius_m':0.1,'mass_kg':1.0}},
            {'name':'ObstacleA','translation':[4.0,3.0,0.5],'extras':{'radius_m':0.4,'height_m':1.0}},
            {'name':'ObstacleB','translation':[7.0,6.0,0.5],'extras':{'radius_m':0.6,'height_m':1.0}},
        ],
    }
    (out/'veap_reference.gltf').write_text(json.dumps(gltf,indent=2),encoding='utf-8')

    manifest={'schema':'veap.scene.manifest/1','scene_sha256':digest,
              'units':'m','up_axis':'Z','robot_representation':'SURROGATE_NOT_CALIBRATED',
              'cad_model_included':False,'geometry_equivalence':'PARTIAL',
              'native_usd_parser_validated':usd_valid,'native_sdf_runtime_validated':sdf_valid,
              'native_mjcf_runtime_validated':False,
              'artifacts':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.glob('veap_reference.*'))}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest
