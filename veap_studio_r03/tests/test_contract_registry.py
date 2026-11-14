import json,ast
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from veap_studio.api import create_app
from veap_studio.contract_registry import Contract,digest


def source_rows(tmp_path,violation=False,with_action=True):
    src=tmp_path/'trace.jsonl'
    points=[(0,0),(.2,.2),(.4,.4),(.6,.6),(1,1)] if violation else [(0,0),(0,.2),(0,.4),(.4,.9),(1,1)]
    with src.open('w') as f:
        for i,(x,y) in enumerate(points):
            r={'t_ns':(i+1)*100_000_000,'x_m':x,'y_m':y,'sensor_ok':True}
            if with_action:r['cmd_vel']=[0.0,0.0,0.0]
            f.write(json.dumps(r)+'\n')
    return src


def contract():
    return {'schema_id':'veap.contract/1','name':'Synthetic zone test','frame':'map',
     'goal':{'x':1,'y':1},'goal_tolerance_m':.1,'max_speed_m_s':12,
     'max_gap_s':.2,'forbidden_zones':[{'label':'center','x1':.28,'x2':.55,'y1':.28,'y2':.55}],
     'require_actions':True,'calibration':'UNVALIDATED_EXAMPLE'}

def test_contract_id_is_stable():
    a=Contract(**contract())
    assert digest(a.model_dump(mode='json'))==digest(a.model_dump(mode='json'))

def test_invalid_geometry_rejected():
    c=contract();c['forbidden_zones'][0]['x2']=.1
    with pytest.raises(ValueError):Contract(**c)

def test_separate_monitor_has_no_veap_imports():
    root=Path(__file__).resolve().parents[1]
    script=root/'external_monitor'/'contract_monitor.py'
    node=ast.parse(script.read_text())
    names=[]
    for n in ast.walk(node):
        if isinstance(n,ast.Import):names.extend(a.name for a in n.names)
        if isinstance(n,ast.ImportFrom) and n.module:names.append(n.module)
    assert not any(n.startswith('veap') or n.startswith('ros') or n.startswith('mujoco') for n in names)

def test_safe_trace_accepted_with_limited_claim(tmp_path):
    app=create_app(tmp_path/'db',seed_demo=False);client=TestClient(app)
    src=source_rows(tmp_path,violation=False)
    asset=app.state.store.put('safe.jsonl',src)
    c=client.post('/api/contracts',json=contract())
    assert c.status_code==200
    cid=c.json()['id']
    r=client.post(f'/api/contracts/{cid}/evaluate/{asset["id"]}')
    assert r.status_code==200, r.text
    data=r.json();assert data['recorded_contract_pass']
    assert data['physical_safety']=='NOT_ESTABLISHED'
    assert data['source_sha256']==asset['sha256']

def test_interpolated_zone_crossing_rejected(tmp_path):
    app=create_app(tmp_path/'db',seed_demo=False);client=TestClient(app)
    asset=app.state.store.put('unsafe.jsonl',source_rows(tmp_path,violation=True))
    cid=client.post('/api/contracts',json=contract()).json()['id']
    r=client.post(f'/api/contracts/{cid}/evaluate/{asset["id"]}');assert r.status_code==200
    data=r.json();assert not data['recorded_contract_pass']
    assert data['violations']>0 and 'KEEP_OUT_CROSSING' in data['issues']

def test_missing_recorded_actions_rejected(tmp_path):
    app=create_app(tmp_path/'db',seed_demo=False);client=TestClient(app)
    asset=app.state.store.put('noactions.jsonl',source_rows(tmp_path,with_action=False))
    cid=client.post('/api/contracts',json=contract()).json()['id']
    r=client.post(f'/api/contracts/{cid}/evaluate/{asset["id"]}').json()
    assert r['missing_actions']==5 and not r['recorded_contract_pass']

def test_real_trace_not_automatically_scored_against_demo_zone(tmp_path):
    app=create_app(tmp_path/'db',seed_demo=False)
    asset=app.state.store.put('recorded.jsonl',source_rows(tmp_path),origin='UPLOAD_UNATTESTED')
    result=app.state.store.report(asset['id'])
    assert result['process_accepted'] is None
    assert result['task_complete'] is None
    assert result['verdict']=='MEASURED_TRACE_ONLY_NO_ASSURANCE_VERDICT'
