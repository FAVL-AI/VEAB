"""Deterministic *static* checks of generated interchange assets.

Success establishes XML/mesh readability and exported scene consistency, NOT
physics correctness, native runtime compatibility, or vendor calibration.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET
from .scene import validate_scene
from ..spec import digest


def audit_assets(folder: str | Path) -> dict:
    root=Path(folder)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    findings=[]
    def check(condition:bool,description:str):
        findings.append({'check':description,'passed':bool(condition)})
    expected=set(['mjcf','sdf','urdf','usda','glb','scene'])
    check(manifest.get('schema_version')=='veab-assets/1','asset manifest schema')
    check(set(manifest.get('files',{}))==expected,'all six standard exports present')
    for fmt,info in manifest.get('files',{}).items():
        name=info.get('name','')
        safe=bool(name) and Path(name).name==name and not name.startswith('.')
        if not safe:
            check(False,fmt+' safe relative asset path');continue
        path=root/name
        exists=path.is_file()
        check(exists,fmt+' file exists')
        if exists:
            blob=path.read_bytes()
            check(hashlib.sha256(blob).hexdigest()==info.get('sha256'),fmt+' SHA-256 matches manifest')
            check(len(blob)==info.get('bytes'),fmt+' byte count matches manifest')
    if any(not f['passed'] for f in findings):
        return {'valid':False,'checks':findings,'scope':'static exports only, not native physics'}
    scene=json.loads((root/manifest['files']['scene']['name']).read_text(encoding='utf-8'))
    try:
        validate_scene(scene)
        check(True,'canonical scene contract and digest')
    except ValueError:
        check(False,'canonical scene contract and digest')
    check(manifest.get('scene_sha256')==scene.get('content_sha256'),'scene digest matches manifest')
    check(manifest.get('source_scenario_sha256')==scene.get('source_scenario_sha256'),'scenario digest matches manifest')
    check(scene.get('coordinate_frame')=='ENU_z_up_m' and scene.get('meters_per_unit')==1,'metric ENU coordinate frame')
    mj=ET.parse(root/manifest['files']['mjcf']['name']).getroot()
    sdf=ET.parse(root/manifest['files']['sdf']['name']).getroot()
    urdf=ET.parse(root/manifest['files']['urdf']['name']).getroot()
    check(mj.tag=='mujoco','MuJoCo root tag')
    check(sdf.tag=='sdf' and sdf.get('version')=='1.10','Gazebo SDF root tag / version')
    check(urdf.tag=='robot','URDF root tag')
    mj_names={g.get('name') for g in mj.findall('.//worldbody/geom')}
    sdf_names={m.get('name') for m in sdf.findall('.//world/model')}
    urdf_names={link.get('name') for link in urdf.findall('./link')}
    ids={o['id'] for o in scene['objects']}
    check(ids <= mj_names,'MuJoCo includes all canonical objects')
    check(ids <= sdf_names,'Gazebo includes all canonical objects')
    check(ids <= urdf_names,'URDF includes all canonical objects')
    glb_path=root/manifest['files']['glb']['name']
    try:
        import trimesh
        mesh=trimesh.load(glb_path,force='scene')
        check(len(mesh.geometry)>=len(ids)+1,'glTF contains all objects plus robot')
        check(math.isfinite(float(mesh.bounds[0][0])) and math.isfinite(float(mesh.bounds[1][2])),'glTF finite geometry')
    except Exception:
        check(False,'glTF readability / optional trimesh dependency')
    usd=(root/manifest['files']['usda']['name']).read_text(encoding='utf-8')
    check(usd.lstrip().startswith('#usda 1.0'),'OpenUSD USDA header')
    check('metersPerUnit = 1' in usd and 'upAxis = "Z"' in usd,'USD metric Z-up stage')
    return {'schema_version':'veab-static-asset-audit/1','valid':all(f['passed'] for f in findings),
            'scene_sha256':scene.get('content_sha256'),'checks':findings,
            'scope':'Static integrity and interchange consistency ONLY; native engine load/dynamics unverified',
            'engine_conflicts':['MuJoCo planar-force surrogate differs from Gazebo differential-drive surrogate',
               'OpenUSD is visual-only without UsdPhysics authoring',
               'URDF world scene does not specify a mobile articulated drive',
               'Unreal uses LUF centimeters; convert from ENU Z-up meters with validation']}
