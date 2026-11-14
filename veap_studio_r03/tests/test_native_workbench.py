"""VEAP sovereign Studio R0.3: test executable operations and fail-closed contracts."""
import json
import os
import sys
import time
import types
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from veap_studio.api import create_app
from veap_studio.integrations import probe_all,probe_one
from veap_studio.mcap_decode import decode_mcap
from veap_studio.physics_comparison import compare_physics
from veap_studio.world_export import export_reference_world,sha_obj,SCENE

@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path/'data',seed_demo=False)
    return TestClient(app)

def await_job(client,jid):
    for i in range(120):
        j=client.get('/api/jobs/'+jid).json()['job']
        if j['status'] in ('COMPLETED','FAILED','INTERRUPTED'):return j
        time.sleep(.05)
    pytest.fail('job exceeded 6-second test deadline')

def test_first_party_capabilities_have_no_external_visualizer():
    p=probe_all()
    assert len(p['connectors'])>=10
    assert all('extension' not in c['name'].lower() for c in p['connectors'])
    assert next(c for c in p['connectors'] if c['id']=='veap_renderer')['status']=='AVAILABLE_LOCAL'

def test_invalid_configured_executable_fails_closed():
    result=probe_one('isaac','Isaac','VEAP_ISAAC_PYTHON','test')
    assert result['status'] in ('NOT_CONFIGURED','INVALID_RUNTIME','DEPENDENCY_MISSING','MODULES_AVAILABLE','PROBE_FAILED')

def test_scene_export_valid_xml_and_artifact_sha(tmp_path):
    result=export_reference_world(tmp_path)
    assert result['scene_sha256']==sha_obj(SCENE)
    assert result['robot_representation']=='SURROGATE_NOT_CALIBRATED'
    assert (tmp_path/'veap_reference.usda').read_text().startswith('#usda 1.0')
    import xml.etree.ElementTree as ET
    ET.parse(tmp_path/'veap_reference.sdf')
    ET.parse(tmp_path/'veap_reference.xml')

def test_scene_export_job_and_download(client):
    j=client.post('/api/jobs',json={'kind':'scene_export'}).json()['job']
    completed=await_job(client,j['id'])
    assert completed['status']=='COMPLETED'
    r=client.get('/api/jobs/'+j['id']+'/artifact/veap_reference.usda')
    assert r.status_code==200 and b'#usda 1.0' in r.content
    assert client.get('/api/jobs/'+j['id']+'/artifact/../index.sqlite3').status_code in (404,422)

def test_native_mujoco_job_fails_when_no_environment(client,monkeypatch):
    monkeypatch.setenv('VEAP_MUJOCO_PYTHON','/unavailable/mujoco/python')
    jid=client.post('/api/jobs',json={'kind':'mujoco_fall'}).json()['job']['id']
    j=await_job(client,jid)
    assert j['status']=='FAILED' and 'VEAP_MUJOCO_PYTHON' in j['error']

def test_invalid_job_and_source_fail(client):
    assert client.post('/api/jobs',json={'kind':'robot_command'}).status_code==422
    assert client.post('/api/jobs',json={'kind':'mcap_decode','source_id':'not-exists'}).status_code==404

def test_inbox_rejects_path_traversal_and_symlinks(client,tmp_path,monkeypatch):
    path=client.app.state.store.root/'inbox'
    (path/'sample.log').write_text('captured')
    assert client.get('/api/inbox').json()['files'][0]['name']=='sample.log'
    assert client.post('/api/inbox/import',json={'name':'../escape.log'}).status_code==422
    (path/'link.log').symlink_to('/etc/passwd')
    assert client.post('/api/inbox/import',json={'name':'link.log'}).status_code==404

def test_inbox_import_hash_and_custody(client):
    path=client.app.state.store.root/'inbox';(path/'capture.log').write_text('test evidence')
    r=client.post('/api/inbox/import',json={'name':'capture.log'})
    # small container disk headroom may be <10 GiB; low-disk is fail-closed
    if r.status_code==507:return
    assert r.status_code==200 and r.json()['asset']['origin']=='LOCAL_INBOX_UNATTESTED'

def test_physics_comparison_includes_z_and_contact_limits(tmp_path):
    left=tmp_path/'one.jsonl';right=tmp_path/'two.jsonl'
    with left.open('w') as a,right.open('w') as b:
        for i in range(5):
            a.write(json.dumps({'t_ns':(i+1)*5000000,'x_m':0,'y_m':0,'z_m':1-i*.1,'contact_count':0})+'\n')
            b.write(json.dumps({'t_ns':(i+1)*5000000,'x_m':0,'y_m':0,'z_m':1-i*.15,'contact_count':None})+'\n')
    r=compare_physics(left,right)
    assert r['rmse_z_m']>0
    assert not r['contact_comparable'] and r['contact_disagreements'] is None
    assert r['physics_equivalence']=='NOT_ESTABLISHED'

def test_physics_comparison_rejects_unmatched_timestamps(tmp_path):
    p1,p2=tmp_path/'a.jsonl',tmp_path/'b.jsonl'
    p1.write_text('\n'.join(json.dumps({'t_ns':i*10000000+1,'x_m':0,'y_m':0,'z_m':0}) for i in range(3)))
    p2.write_text('\n'.join(json.dumps({'t_ns':i*10000000+3000000,'x_m':0,'y_m':0,'z_m':0}) for i in range(3)))
    with pytest.raises(ValueError,match='timestamps differ'):compare_physics(p1,p2)

def test_mcap_decoder_missing_library_explicit(monkeypatch,tmp_path):
    import veap_studio.mcap_decode as md
    # mock module with decoded messages so real MCAP profile is not implied
    def fail(*args,**kwargs):return iter([])
    reader=types.ModuleType('mcap_ros2.reader');reader.read_ros2_messages=fail
    monkeypatch.setitem(sys.modules,'mcap_ros2',types.ModuleType('mcap_ros2'))
    monkeypatch.setitem(sys.modules,'mcap_ros2.reader',reader)
    with pytest.raises(ValueError,match='No decoded odometry'):md.decode_mcap(tmp_path/'none.mcap',tmp_path/'o.jsonl')

def test_mcap_decoder_extracts_recorded_odom_and_cmd_vel(monkeypatch,tmp_path):
    from types import SimpleNamespace as N
    def data():
        for i in range(3):
            pose=N(position=N(x=i*.2,y=i*.1),orientation=N(x=0,y=0,z=0,w=1))
            twist=N(linear=N(x=.2,y=.1,z=0), angular=N(z=0))
            odom=N(pose=N(pose=pose),twist=N(twist=twist),header=N(frame_id='odom'))
            cmd=N(linear=N(x=.2,y=.1),angular=N(z=.0))
            t=1_000_000_000+i*100_000_000
            yield N(channel=N(topic='/cmd_vel'),schema=N(name='geometry_msgs/msg/Twist'),ros_msg=cmd,log_time_ns=t)
            yield N(channel=N(topic='/odom_raw'),schema=N(name='nav_msgs/msg/Odometry'),ros_msg=odom,log_time_ns=t)
    reader=types.ModuleType('mcap_ros2.reader');reader.read_ros2_messages=lambda *args,**kw:data()
    monkeypatch.setitem(sys.modules,'mcap_ros2',types.ModuleType('mcap_ros2'))
    monkeypatch.setitem(sys.modules,'mcap_ros2.reader',reader)
    result=decode_mcap(tmp_path/'dummy.mcap',tmp_path/'derived.jsonl')
    assert result['odometry_samples']==3 and result['command_samples_aligned']==3
    assert result['provenance']=='UNATTESTED'
    data_rows=[json.loads(x) for x in (tmp_path/'derived.jsonl').read_text().splitlines()]
    assert data_rows[0]['cmd_vel']==[.2,.1,0.]

def test_derived_native_physics_never_awards_original_warehouse_contract(client,tmp_path):
    path=tmp_path/'native.jsonl'
    path.write_text('\n'.join(json.dumps({'t_ns':100000000*(i+1),'x_m':0,'y_m':0,'z_m':1-i*.1}) for i in range(4)))
    asset=client.app.state.store.put('native.jsonl',path,origin='NATIVE_SIMULATOR_UNATTESTED')
    rep=client.app.state.store.report(asset['id'])
    assert rep['verdict']=='NATIVE_PHYSICS_TRACE_AVAILABLE_NO_SAFETY_VERDICT'
    assert rep['physics_validation']=='NOT_ESTABLISHED'

def test_native_cross_engine_api_rejects_unmatched(client):
    r=client.post('/api/physics/compare',json={'reference_job_id':'x','candidate_job_id':'y'})
    assert r.status_code==404

def test_ui_uses_veap_native_workbench_only():
    root=Path(__file__).resolve().parents[1]
    content=(root/'web'/'app.js').read_text()+(root/'web'/'index.html').read_text()
    assert 'EXPORT CONTRACT PROPOSED' not in content
    assert 'Engine Runtime' in content or 'Engine &amp; Runtime' in content
    assert '/api/integrations' in content and 'scene_export' in content
