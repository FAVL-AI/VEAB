"""Bounded offline geometry inspection. Display geometry is NOT calibrated physics."""
from __future__ import annotations
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_POINTS=25000

def pointcloud(path):
    path=Path(path);ext=path.suffix.lower();points=[]
    if ext not in ('.xyz','.ply','.pcd'):raise ValueError('unsupported point-cloud format')
    with path.open('rb') as f:
        head=f.read(512)
    if b'\x00' in head:raise ValueError('binary point clouds require native decoder; ASCII only in local pilot')
    with path.open('r',encoding='utf-8',errors='replace') as f:
        fields=None
        if ext=='.ply':
            if f.readline().strip()!='ply':raise ValueError('invalid PLY header')
            found=False
            for k in range(200):
                line=f.readline()
                if not line:break
                if line.strip().startswith('format binary'):raise ValueError('binary PLY unsupported')
                if line.strip()=='end_header':found=True;break
            if not found:raise ValueError('unterminated PLY header')
        if ext=='.pcd':
            found=False
            for k in range(200):
                line=f.readline()
                if not line:break
                if line.startswith('FIELDS '):fields=line.strip().split()[1:]
                if line.strip().lower()=='data ascii':found=True;break
                if line.lower().startswith('data binary'):raise ValueError('binary PCD unsupported')
            if not found:raise ValueError('PCD ASCII DATA marker missing')
            if not fields or not all(i in fields for i in ('x','y','z')):raise ValueError('PCD xyz fields missing')
        for line in f:
            if len(points)>=MAX_POINTS:break
            v=line.split()
            if len(v)<3:continue
            try:
                a=[float(v[fields.index(k)]) for k in ('x','y','z')] if fields else [float(v[i]) for i in range(3)]
            except (ValueError,IndexError):continue
            if all(math.isfinite(x) and abs(x)<=1e6 for x in a):points.append([round(x,4) for x in a])
    if not points:raise ValueError('no readable finite xyz points')
    mins=[min(p[i] for p in points) for i in range(3)]
    maxs=[max(p[i] for p in points) for i in range(3)]
    vs=.4;vox={}
    for x,y,z in points:
        key=(math.floor(x/vs),math.floor(y/vs))
        vox[key]=vox.get(key,0)+1
    cells=sorted([{'x_m':(x+.5)*vs,'y_m':(y+.5)*vs,'hits':n} for (x,y),n in vox.items()],key=lambda e:-e['hits'])[:1000]
    step=max(1,len(points)//3000)
    return {'points':points[::step],'point_count_inspected':len(points),'bounds_m':{'min':mins,'max':maxs},
            'occupancy_cells':cells,'voxel_m':vs,'source_registration':'UNKNOWN','calibration':'NOT_ESTABLISHED',
            'algorithm':'UNREGISTERED_2D_VOXEL_PROJECTION','physical_surface_reconstruction':'NOT_ESTABLISHED'}

def model_preview(path):
    path=Path(path);ext=path.suffix.lower()
    if ext=='.urdf':
        try:root=ET.parse(path).getroot()
        except ET.ParseError as e:raise ValueError('URDF XML is invalid') from e
        links=[n.get('name') for n in root.findall('link') if n.get('name')]
        joints=[{'name':n.get('name'),'type':n.get('type'),
                 'parent':(n.find('parent').get('link') if n.find('parent') is not None else None),
                 'child':(n.find('child').get('link') if n.find('child') is not None else None)} for n in root.findall('joint')]
        return {'type':'URDF','links':links[:1200],'joints':joints[:1200], 'mesh_preview':'KINEMATIC_TREE_ONLY',
                'physics_ready':False,'asset_calibration':'NOT_ESTABLISHED'}
    if ext not in ('.obj','.stl','.glb','.gltf'):
        return {'type':ext.lstrip('.').upper(),'mesh_preview':'REQUIRES_NATIVE_ENGINE_IMPORT',
                'physics_ready':False,'asset_calibration':'NOT_ESTABLISHED'}
    try:
        import trimesh
    except ImportError:
        return {'type':ext.lstrip('.').upper(),'mesh_preview':'INSTALL_OPTIONAL_TRIMESH',
                'physics_ready':False,'asset_calibration':'NOT_ESTABLISHED'}
    try:
        mesh=trimesh.load(str(path),force='mesh',process=False)
    except Exception as e:raise ValueError('mesh parsing failed: '+type(e).__name__) from e
    vertices=mesh.vertices
    if not len(vertices):raise ValueError('empty mesh')
    if len(vertices)>2_000_000:raise ValueError('mesh exceeds preview vertex limit')
    step=max(1,len(vertices)//3000)
    pts=vertices[::step]
    bounds=mesh.bounds.tolist()
    if not all(math.isfinite(float(v)) for p in bounds for v in p):raise ValueError('nonfinite mesh bounds')
    return {'type':ext.lstrip('.').upper(),'vertices_sampled':[[round(float(v),5) for v in p] for p in pts],
            'vertex_count':len(vertices),'face_count':len(mesh.faces), 'bounds_in_file_units':bounds,
            'mesh_preview':'VERTEX_SAMPLE_ONLY','physics_ready':False,'asset_calibration':'NOT_ESTABLISHED',
            'units':'UNVERIFIED_SOURCE_UNITS'}
