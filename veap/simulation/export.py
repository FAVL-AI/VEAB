"""Portable scene exports: USD visual stage, MuJoCo MJCF, Gazebo SDF,
URDF descriptive robot, glTF preview and a machine-readable provenance manifest.

No native simulator is required to run the exporter. Output must be imported
and calibrated before physics-equivalence or SimReady claims can be made.
"""
from __future__ import annotations
import json
import math
import hashlib
import struct
from pathlib import Path
from xml.etree import ElementTree as ET
from .scene import validate_scene
from ..spec import digest


def v3(xs):
    return " ".join(f"{x:.7g}" for x in xs)


def _mujoco(scene:dict) -> ET.Element:
    root = ET.Element("mujoco", model=scene["scene_id"])
    ET.SubElement(root,"compiler",angle="radian",coordinate="local",autolimits="true")
    ET.SubElement(root,"option",timestep="0.01",gravity="0 0 -9.81",integrator="implicitfast")
    ET.SubElement(root,"visual")
    asset = ET.SubElement(root,"asset")
    ET.SubElement(asset,"material",name="robot_matte",rgba="0.17 0.78 0.82 1")
    world = ET.SubElement(root,"worldbody")
    for obj in scene["objects"]:
        if obj["role"] in ("waypoint","forbidden"):
            attrs = {"name":obj["id"],"type":obj["shape"],"pos":v3(obj["position_m"]),
                     "rgba":v3(obj["rgba"]),"contype":"0","conaffinity":"0"}
            attrs["size"] = v3([k/2 for k in obj["size_m"]]) if obj["shape"]=="box" else v3([obj["size_m"][0],obj["size_m"][1]/2])
            ET.SubElement(world,"geom",**attrs)
            continue
        attrs = {"name":obj["id"],"type":obj["shape"],"pos":v3(obj["position_m"]),
                 "rgba":v3(obj["rgba"]),"friction":"0.8 0.1 0.1"}
        attrs["size"] = v3([k/2 for k in obj["size_m"]]) if obj["shape"]=="box" else v3([obj["size_m"][0],obj["size_m"][1]/2])
        ET.SubElement(world,"geom",**attrs)
    robot=scene["robot"]
    base=ET.SubElement(world,"body",name="veab_scout",pos=v3(robot["initial_pose_xyz_m"]))
    ET.SubElement(base,"joint",name="planar_x",type="slide",axis="1 0 0",damping="2")
    ET.SubElement(base,"joint",name="planar_y",type="slide",axis="0 1 0",damping="2")
    ET.SubElement(base,"joint",name="planar_yaw",type="hinge",axis="0 0 1",damping=".3")
    ET.SubElement(base,"geom",name="scout_chassis",type="cylinder",
                  size=v3([robot["footprint_radius_m"],robot["height_m"]/2]),
                  rgba="0.14 0.85 0.77 1",mass=str(robot["mass_kg"]),friction="1 .005 .0001")
    ET.SubElement(base,"site",name="scout_origin",pos="0 0 0",size=".02",rgba="1 1 1 1")
    ET.SubElement(base,"camera",name="inspection_camera",pos="-.55 -1.5 1.7",mode="trackcom",fovy="60")
    act=ET.SubElement(root,"actuator")
    for axis in ("x","y","yaw"):
        ET.SubElement(act,"motor",name=f"cmd_{axis}",joint=f"planar_{axis}",
                      ctrllimited="true",ctrlrange=("-50 50" if axis!="yaw" else "-8 8"),gear="1")
    return root


def _box_visual(link, tag, obj):
    element=ET.SubElement(link,tag)
    ET.SubElement(element,"origin",xyz=v3(obj["position_m"]),rpy="0 0 0")
    geom=ET.SubElement(element,"geometry")
    if obj["shape"]=="box":
        ET.SubElement(geom,"box",size=v3(obj["size_m"]))
    else:
        ET.SubElement(geom,"cylinder",radius=str(obj["size_m"][0]),length=str(obj["size_m"][1]))
    if tag=="visual":
        mat=ET.SubElement(element,"material",name=f"mat_{obj['id']}")
        ET.SubElement(mat,"color",rgba=v3(obj["rgba"]))


def _urdf(scene):
    root=ET.Element("robot",name=f"veab_{scene['scene_id']}")
    ET.SubElement(root,"link",name="world")
    robot=scene["robot"]
    chassis={"id":"robot","shape":"cylinder","size_m":[robot["footprint_radius_m"],robot["height_m"]],
             "position_m":[0,0,0],"rgba":[.12,.83,.76,1]}
    for obj in [*scene["objects"],chassis]:
        link=ET.SubElement(root,"link",name=obj["id"])
        local=dict(obj)
        if obj is not chassis:
            local["position_m"]=[0,0,0]
        _box_visual(link,"visual",local)
        if obj is chassis or obj.get("collision",False):
            _box_visual(link,"collision",local)
        inertial=ET.SubElement(link,"inertial")
        ET.SubElement(inertial,"origin",xyz="0 0 0",rpy="0 0 0")
        mass=robot["mass_kg"] if obj is chassis else 1.0
        ET.SubElement(inertial,"mass",value=str(mass))
        ET.SubElement(inertial,"inertia",ixx="0.12",iyy="0.12",izz="0.12",ixy="0",ixz="0",iyz="0")
        joint=ET.SubElement(root,"joint",name=f"anchor_{obj['id']}",type="fixed")
        ET.SubElement(joint,"parent",link="world")
        ET.SubElement(joint,"child",link=obj["id"])
        ET.SubElement(joint,"origin",xyz=v3(robot["initial_pose_xyz_m"] if obj is chassis else obj["position_m"]),rpy="0 0 0")
    return root


def _sdf_shape(parent, obj):
    shape=ET.SubElement(parent,"geometry")
    if obj["shape"]=="box":
        ET.SubElement(ET.SubElement(shape,"box"),"size").text=v3(obj["size_m"])
    else:
        cyl=ET.SubElement(shape,"cylinder")
        ET.SubElement(cyl,"radius").text=str(obj["size_m"][0])
        ET.SubElement(cyl,"length").text=str(obj["size_m"][1])


def _sdf(scene):
    root=ET.Element("sdf",version="1.10")
    world=ET.SubElement(root,"world",name=f"veab_{scene['scene_id']}")
    ET.SubElement(world,"gravity").text="0 0 -9.81"
    physics=ET.SubElement(world,"physics",name="default",type="ignored")
    ET.SubElement(physics,"max_step_size").text="0.01"
    ET.SubElement(physics,"real_time_factor").text="1"
    for name,filename in [("gz::sim::systems::Physics","gz-sim-physics-system"),
                          ("gz::sim::systems::UserCommands","gz-sim-user-commands-system"),
                          ("gz::sim::systems::SceneBroadcaster","gz-sim-scene-broadcaster-system"),
                          ("gz::sim::systems::Sensors","gz-sim-sensors-system")]:
        plugin=ET.SubElement(world,"plugin",name=name,filename=filename)
        if "Sensors" in name: ET.SubElement(plugin,"render_engine").text="ogre2"
    for o in scene["objects"]:
        model=ET.SubElement(world,"model",name=o["id"])
        ET.SubElement(model,"static").text="true"
        link=ET.SubElement(model,"link",name="geometry")
        ET.SubElement(link,"pose").text=v3([*o["position_m"],0,0,0])
        visual=ET.SubElement(link,"visual",name="visual")
        _sdf_shape(visual,o)
        material=ET.SubElement(visual,"material")
        ET.SubElement(material,"diffuse").text=v3(o["rgba"])
        ET.SubElement(material,"ambient").text=v3(o["rgba"])
        if o["collision"]:
            collider=ET.SubElement(link,"collision",name="collision")
            _sdf_shape(collider,o)
    r=scene["robot"]
    model=ET.SubElement(world,"model",name="veab_scout_surrogate")
    ET.SubElement(model,"pose").text=v3([*r["initial_pose_xyz_m"],0,0,0])
    chassis=ET.SubElement(model,"link",name="base_link")
    ET.SubElement(chassis,"gravity").text="true"
    inertial=ET.SubElement(chassis,"inertial")
    ET.SubElement(inertial,"mass").text=str(r["mass_kg"])
    i=ET.SubElement(inertial,"inertia")
    radius=r["footprint_radius_m"]; h=r["height_m"]; mass=r["mass_kg"]
    Ixy=mass*(3*radius*radius+h*h)/12; Iz=mass*radius*radius/2
    for name, val in (("ixx",Ixy),("iyy",Ixy),("izz",Iz),("ixy",0),("ixz",0),("iyz",0)):
        ET.SubElement(i,name).text=f"{val:.8f}"
    robotshape={"shape":"cylinder","size_m":[radius,h]}
    _sdf_shape(ET.SubElement(chassis,"visual",name="body_visual"),robotshape)
    _sdf_shape(ET.SubElement(chassis,"collision",name="body_collision"),robotshape)
    sensor=ET.SubElement(chassis,"sensor",name="scan_2d",type="gpu_lidar")
    ET.SubElement(sensor,"pose").text="0 0 .19 0 0 0"
    ET.SubElement(sensor,"topic").text="/scan"
    ET.SubElement(sensor,"update_rate").text="10"
    lidar=ET.SubElement(sensor,"lidar")
    hscan=ET.SubElement(ET.SubElement(lidar,"scan"),"horizontal")
    for k,v in (("samples",360),("resolution",1),("min_angle",-math.pi),("max_angle",math.pi)):
        ET.SubElement(hscan,k).text=str(v)
    rr=ET.SubElement(lidar,"range")
    for k,v in (("min",.05),("max",12),("resolution",.01)):
        ET.SubElement(rr,k).text=str(v)
    for side, y in (("left",.15),("right",-.15)):
        wheel=ET.SubElement(model,"link",name=f"{side}_wheel")
        ET.SubElement(wheel,"pose").text=v3([0,y,-.075,math.pi/2,0,0])
        inert=ET.SubElement(wheel,"inertial")
        ET.SubElement(inert,"mass").text=".28"
        ii=ET.SubElement(inert,"inertia")
        for k,v in (("ixx",.00065),("iyy",.00065),("izz",.00035),("ixy",0),("ixz",0),("iyz",0)):
            ET.SubElement(ii,k).text=str(v)
        wheelshape={"shape":"cylinder","size_m":[.085,.04]}
        _sdf_shape(ET.SubElement(wheel,"visual",name="wheel_visual"),wheelshape)
        _sdf_shape(ET.SubElement(wheel,"collision",name="wheel_collision"),wheelshape)
        joint=ET.SubElement(model,"joint",name=f"{side}_wheel_joint",type="revolute")
        ET.SubElement(joint,"parent").text="base_link"
        ET.SubElement(joint,"child").text=f"{side}_wheel"
        axis=ET.SubElement(joint,"axis")
        ET.SubElement(axis,"xyz").text="0 0 1"
        limit=ET.SubElement(axis,"limit")
        ET.SubElement(limit,"effort").text="20"
        ET.SubElement(limit,"velocity").text="100"
    plugin=ET.SubElement(model,"plugin",filename="gz-sim-diff-drive-system",name="gz::sim::systems::DiffDrive")
    for k,v in (("left_joint","left_wheel_joint"),("right_joint","right_wheel_joint"),
                ("wheel_separation","0.30"),("wheel_radius","0.085"),
                ("topic","/cmd_vel"),("odom_topic","/odom"),("frame_id","odom"),("child_frame_id","base_link")):
        ET.SubElement(plugin,k).text=v
    return root


def _usda(scene):
    def prim_name(s):
        return "V_"+"".join(c if c.isalnum() or c=="_" else "_" for c in s)
    lines=["#usda 1.0", "(", '    defaultPrim = "World"', "    metersPerUnit = 1", '    upAxis = "Z"', ")", "",'def Xform "World"',"{"]
    for obj in scene["objects"]:
        p=obj["position_m"]; rgb=obj["rgba"][:3]; a=obj["rgba"][3]
        if obj["shape"]=="box":
            typename="Cube"; scale=obj["size_m"]; prop="double size = 1"
        else:
            typename="Cylinder"; scale=[obj["size_m"][0],obj["size_m"][0],obj["size_m"][1]]
            prop="double radius = 1\n        double height = 1"
        lines.extend([f'    def {typename} "{prim_name(obj["id"])}"',"    {",
                      f"        {prop}",
                      f"        double3 xformOp:translate = ({v3(p).replace(' ', ', ')})",
                      f"        float3 xformOp:scale = ({v3(scale).replace(' ', ', ')})",
                      '        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]',
                      f"        color3f[] primvars:displayColor = [({v3(rgb).replace(' ', ', ')})]",
                      f"        float[] primvars:displayOpacity = [{a}]",
                      "    }"])
    r=scene["robot"]
    p=r["initial_pose_xyz_m"]
    lines.extend(['    def Cylinder "RobotSurrogate"',"    {",
                  f'        double radius = {r["footprint_radius_m"]}',
                  f'        double height = {r["height_m"]}',
                  f"        double3 xformOp:translate = ({v3(p).replace(' ', ', ')})",
                  '        uniform token[] xformOpOrder = ["xformOp:translate"]',
                  '        color3f[] primvars:displayColor = [(0.15, 0.84, 0.77)]',
                  "    }","}",""])
    return "\n".join(lines)


def _glb(scene) -> bytes:
    try:
        import trimesh
        import numpy as np
        result=trimesh.Scene()
        for obj in scene["objects"]:
            if obj["shape"]=="box":
                mesh=trimesh.creation.box(extents=obj["size_m"])
            else:
                mesh=trimesh.creation.cylinder(radius=obj["size_m"][0],height=obj["size_m"][1],sections=32)
            mesh.visual.face_colors=np.array([round(255*x) for x in obj["rgba"]],dtype=np.uint8)
            tf=np.eye(4); tf[:3,3]=obj["position_m"]
            result.add_geometry(mesh,node_name=obj["id"],transform=tf)
        r=scene["robot"]
        robot=trimesh.creation.cylinder(radius=r["footprint_radius_m"],height=r["height_m"],sections=32)
        robot.visual.face_colors=[35,220,192,255]
        tf=np.eye(4);tf[:3,3]=r["initial_pose_xyz_m"]
        result.add_geometry(robot,node_name="veab_scout",transform=tf)
        return result.export(file_type="glb")
    except ImportError:
        nodes = [
            {"name": obj["id"], "translation": obj["position_m"]}
            for obj in scene["objects"]
        ] + [{"name": "veab_scout", "translation": scene["robot"]["initial_pose_xyz_m"]}]
        gltf = {
            "asset": {"version": "2.0", "generator": "veap.simulation.export"},
            "scene": 0,
            "scenes": [{"name": scene["scene_id"], "nodes": list(range(len(nodes)))}],
            "nodes": nodes,
        }
        jb = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        pad = (4 - (len(jb) % 4)) % 4
        jb += b" " * pad
        total_len = 12 + 8 + len(jb)
        return struct.pack("<III", 0x46546C67, 2, total_len) + struct.pack("<II", len(jb), 0x4E4F534A) + jb


def export_scene(scene:dict, output_dir:str|Path) -> dict:
    validate_scene(scene)
    folder=Path(output_dir)
    folder.mkdir(parents=True,exist_ok=True)
    stem=scene["scene_id"]
    files={}
    items={"mjcf":(f"{stem}.xml",ET.tostring(_mujoco(scene),encoding="utf-8",xml_declaration=True)),
           "sdf":(f"{stem}.sdf",ET.tostring(_sdf(scene),encoding="utf-8",xml_declaration=True)),
           "urdf":(f"{stem}.urdf",ET.tostring(_urdf(scene),encoding="utf-8",xml_declaration=True)),
           "usda":(f"{stem}.usda",_usda(scene).encode("utf-8")),
           "glb":(f"{stem}.glb",_glb(scene)),
           "scene":(f"{stem}.scene.json",json.dumps(scene,indent=2,allow_nan=False).encode("utf-8"))}
    for key,(name,blob) in items.items():
        target=folder/name
        target.write_bytes(blob)
        files[key]={"name":name,"sha256":hashlib.sha256(blob).hexdigest(),"bytes":len(blob)}
    manifest={"schema_version":"veab-assets/1", "scene_id":stem,
              "scene_sha256":scene["content_sha256"],
              "source_scenario_sha256":scene["source_scenario_sha256"],
              "engine_readiness":{
                  "mjcf":"exported; native MuJoCo loading and dynamic calibration required",
                  "sdf":"exported; Gazebo plugin, joints and native dynamics require verification",
                  "urdf":"static visual/collision descriptor, not an actuated robot description",
                  "usda":"visual geometry; Isaac/Unreal physics authoring and import checks outstanding",
                  "glb":"3D visual preview only"},
              "files":files}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest
