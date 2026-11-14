"""Software-only enterprise pilot controls. Not deployment or physics validation."""
from __future__ import annotations
import json
import time
import pytest
from fastapi.testclient import TestClient
from veap.enterprise.db import StudioDB
from veap.enterprise.api import create_app, validate_jsonl, report_html


@pytest.fixture()
def env(tmp_path):
    db=StudioDB(tmp_path)
    tenant,owner=db.bootstrap('Tenant Alpha','owner@alpha.test','Alice')
    other,other_owner=db.bootstrap('Tenant Beta','owner@beta.test','Bob')
    _,reviewer=db.bootstrap('', 'reviewer@alpha.test','Robin','reviewer',tenant_id=tenant)
    _,viewer=db.bootstrap('', 'viewer@alpha.test','Vera','viewer',tenant_id=tenant)
    _,researcher=db.bootstrap('', 'lab@alpha.test','Laboratory','researcher',tenant_id=tenant)
    keys={r:db.issue_dev_token(uid) for r,uid in [('owner',owner),('other',other_owner),
                                                  ('reviewer',reviewer),('viewer',viewer),('researcher',researcher)]}
    with TestClient(create_app(data_dir=tmp_path,mode='dev-token')) as client:
        def h(role):return {'Authorization':'Bearer '+keys[role]}
        yield client,db,tenant,other,keys,h


def add_project(env):
    c,db,t,_,_,h=env
    r=c.post(f'/api/studio/t/{t}/projects',headers=h('owner'),json={'name':'Test laboratory','description':'Assurance demo'})
    assert r.status_code==201,r.text
    return r.json()['id']


def make_run(env,pid,*,role='owner',shield=True,request_key=None):
    c,db,t,_,keys,h=env
    payload={'scenario_id':'warehouse-transfer','policy':'route','seed':17,'shield':shield}
    if request_key:payload['request_key']=request_key
    r=c.post(f'/api/studio/t/{t}/projects/{pid}/runs',headers=h(role),json=payload)
    assert r.status_code==202,r.text
    run_id=r.json()['id']
    for _ in range(150):
        obj=c.get(f'/api/studio/t/{t}/projects/{pid}/runs/{run_id}',headers=h(role)).json()
        if obj['status'] in ('completed','failed','rejected'):break
        time.sleep(.03)
    assert obj['status']=='completed',obj
    return run_id,obj


def test_health_explicit_pilot(env):
    c,*_=env
    r=c.get('/api/studio/health')
    assert r.status_code==200
    assert not r.json()['production_qualified']
    assert not r.json()['robot_actuation']


def test_no_anonymous_access(env):
    c,_,t,_,_,_=env
    assert c.get('/api/studio/me').status_code==401
    assert c.get(f'/api/studio/t/{t}/projects').status_code==401


def test_wrong_token_rejected(env):
    c,*_=env
    assert c.get('/api/studio/me',headers={'Authorization':'Bearer veab_forged'}).status_code==401


def test_membership_server_authority(env):
    c,_,t,other,_,h=env
    assert c.get(f'/api/studio/t/{other}/projects',headers=h('owner')).status_code==404
    assert c.get(f'/api/studio/t/{t}/projects',headers=h('other')).status_code==404


def test_viewer_cannot_create_project(env):
    c,_,t,_,_,h=env
    assert c.post(f'/api/studio/t/{t}/projects',headers=h('viewer'),json={'name':'Cannot'}).status_code==403


def test_reviewer_cannot_queue(env):
    c,_,t,_,_,h=env
    pid=add_project(env)
    r=c.post(f'/api/studio/t/{t}/projects/{pid}/runs',headers=h('reviewer'),json={'scenario_id':'warehouse-transfer'})
    assert r.status_code==403


def test_researcher_can_create_project(env):
    c,_,t,_,_,h=env
    assert c.post(f'/api/studio/t/{t}/projects',headers=h('researcher'),json={'name':'Research project'}).status_code==201


def test_project_access_cross_tenant_404(env):
    c,_,t,other,_,h=env
    pid=add_project(env)
    assert c.get(f'/api/studio/t/{other}/projects/{pid}',headers=h('other')).status_code==404


def test_run_executes_and_bundle_is_authorized(env):
    c,_,t,_,_,h=env
    pid=add_project(env)
    rid,record=make_run(env,pid)
    assert record['summary']['verified']
    assert record['bundle_sha256'] and len(record['bundle_sha256'])==64
    artifact=c.get(f'/api/studio/t/{t}/projects/{pid}/runs/{rid}/bundle',headers=h('owner'))
    assert artifact.status_code==200
    assert artifact.json()['verification']['verified']
    assert c.get(f'/api/studio/t/{t}/projects/{pid}/runs/{rid}/bundle',headers=h('other')).status_code==404


def test_run_idempotency(env):
    c,_,t,_,_,h=env
    p=add_project(env)
    rid,_=make_run(env,p,request_key='demo-fixed-req-001')
    r=c.post(f'/api/studio/t/{t}/projects/{p}/runs',headers=h('owner'),
             json={'scenario_id':'warehouse-transfer','policy':'route','seed':17,'shield':True,'request_key':'demo-fixed-req-001'})
    assert r.status_code==202 and r.json()['id']==rid and r.json()['idempotent_replay']


def test_idempotency_conflict(env):
    c,_,t,_,_,h=env
    p=add_project(env)
    make_run(env,p,request_key='another-fixed-req')
    r=c.post(f'/api/studio/t/{t}/projects/{p}/runs',headers=h('owner'),
             json={'scenario_id':'warehouse-transfer','seed':18,'request_key':'another-fixed-req'})
    assert r.status_code==409


def test_unknown_scenario_does_not_queue(env):
    c,_,t,_,_,h=env
    p=add_project(env)
    r=c.post(f'/api/studio/t/{t}/projects/{p}/runs',headers=h('owner'),json={'scenario_id':'fake-nonexistent'})
    assert r.status_code==404


def test_self_review_prohibited(env):
    c,_,t,_,_,h=env
    p=add_project(env)
    rid,_=make_run(env,p)
    r=c.post(f'/api/studio/t/{t}/projects/{p}/runs/{rid}/reviews',headers=h('owner'),
             json={'verdict':'accepted','rationale':'The trajectory passes replay checks.'})
    assert r.status_code==403


def test_independent_reviewer_records_decision(env):
    c,_,t,_,_,h=env
    p=add_project(env)
    rid,_=make_run(env,p)
    path=f'/api/studio/t/{t}/projects/{p}/runs/{rid}/reviews'
    r=c.post(path,headers=h('reviewer'),json={'verdict':'inconclusive','rationale':'Sensor evidence is not externally authenticated.'})
    assert r.status_code==201
    assert c.get(path,headers=h('viewer')).json()[0]['verdict']=='inconclusive'


def test_duplicate_reviewer_blocked(env):
    c,_,t,_,_,h=env
    p=add_project(env);rid,_=make_run(env,p)
    path=f'/api/studio/t/{t}/projects/{p}/runs/{rid}/reviews'
    body={'verdict':'rejected','rationale':'Ground truth is not independently established.'}
    assert c.post(path,headers=h('reviewer'),json=body).status_code==201
    assert c.post(path,headers=h('reviewer'),json=body).status_code==409


def test_valid_jsonl_upload_unattested(env):
    c,_,t,_,_,h=env
    p=add_project(env)
    data=b'{"tick":0,"x":1,"y":1,"vx":0,"vy":0}\n{"tick":1,"x":1.1,"y":1,"vx":0.1,"vy":0}\n'
    path=f'/api/studio/t/{t}/projects/{p}/evidence?filename=capture.jsonl&format=jsonl'
    r=c.post(path,headers={**h('owner'),'Content-Type':'application/octet-stream'},content=data)
    assert r.status_code==201,r.text
    rec=r.json()
    assert rec['provenance']=='unattested_external'
    assert c.get(f'/api/studio/t/{t}/projects/{p}/evidence/{rec["id"]}/download',headers=h('viewer')).content==data
    assert c.get(f'/api/studio/t/{t}/projects/{p}/evidence/{rec["id"]}/download',headers=h('other')).status_code==404


@pytest.mark.parametrize('bad',[
    b'{"tick":3,"x":0,"y":0,"vx":0,"vy":0}\n{"tick":4,"x":0,"y":0,"vx":0,"vy":0}\n',
    b'{"tick":0,"x":NaN,"y":0,"vx":0,"vy":0}\n{"tick":1,"x":0,"y":0,"vx":0,"vy":0}\n',
    b'{"tick":0,"x":0,"y":0,"vx":0,"vy":0}\n',
    b'{"tick":0,"x":0,"y":0,"vx":0,"vy":0,"secret":4}\n{"tick":1,"x":0,"y":0,"vx":0,"vy":0}\n',
])
def test_bad_jsonl_rejected(env,bad):
    c,_,t,_,_,h=env;p=add_project(env)
    path=f'/api/studio/t/{t}/projects/{p}/evidence?filename=bad.jsonl&format=jsonl'
    assert c.post(path,headers={**h('owner'),'Content-Type':'application/octet-stream'},content=bad).status_code==422


def test_mcap_header_only_not_claimed_valid(env):
    c,_,t,_,_,h=env;p=add_project(env)
    path=f'/api/studio/t/{t}/projects/{p}/evidence?filename=robot.mcap&format=mcap'
    assert c.post(path,headers={**h('owner'),'Content-Type':'application/octet-stream'},content=b'not-a-mcap').status_code==422
    r=c.post(path,headers={**h('owner'),'Content-Type':'application/octet-stream'},content=b'\x89MCAP0\r\nplaceholder')
    assert r.status_code==201
    assert r.json()['provenance']=='unattested_external'


def test_oversize_upload_rejected(env):
    c,_,t,_,_,h=env;p=add_project(env)
    path=f'/api/studio/t/{t}/projects/{p}/evidence?filename=too_large.json&format=json'
    assert c.post(path,headers={**h('owner'),'Content-Type':'application/octet-stream'},content=b'x'*(12*1024*1024+1)).status_code==413


def test_audit_owner_only_and_chain(env):
    c,db,t,_,_,h=env;p=add_project(env)
    assert c.get(f'/api/studio/t/{t}/audit',headers=h('viewer')).status_code==403
    result=c.get(f'/api/studio/t/{t}/audit/verify',headers=h('owner')).json()
    assert result['chain_consistent'] and not result['authenticity_established']


def test_audit_tamper_detection(env):
    c,db,t,_,_,h=env;p=add_project(env)
    with db.conn(write=True) as sql:
        sql.execute('UPDATE audit SET action=? WHERE tenant_id=? AND action=?',('forged.action',t,'project.create'))
    assert not c.get(f'/api/studio/t/{t}/audit/verify',headers=h('owner')).json()['chain_consistent']


def test_report_explicit_limitations(env):
    c,db,t,_,_,h=env;p=add_project(env);make_run(env,p)
    body=c.get(f'/api/studio/t/{t}/projects/{p}/report',headers=h('owner')).json()
    assert body['summary']['completed_runs']==1
    assert not body['summary']['production_qualified']
    assert not body['summary']['physically_validated']


def test_html_report_escapes_user_input():
    malicious='<img src=x onerror=alert(1)>'
    content=report_html({'project':{'name':malicious},'summary':{'runs':1}})
    assert malicious not in content and '&lt;img' in content


def test_legacy_unscoped_api_not_mounted(env):
    c,*_=env
    assert c.get('/api/runs').status_code==404


def test_production_flag_fails_closed(tmp_path,monkeypatch):
    monkeypatch.setenv('VEAB_STUDIO_RELEASE','production')
    with pytest.raises(RuntimeError,match='pilot-only'):
        create_app(data_dir=tmp_path,mode='dev-token')


def test_oidc_unconfigured_fails_closed(tmp_path,monkeypatch):
    for key in ('VEAP_OIDC_ISSUER','VEAP_OIDC_AUDIENCE','VEAP_OIDC_JWKS_URL','VEAB_OIDC_ISSUER','VEAB_OIDC_AUDIENCE','VEAB_OIDC_JWKS_URL'):
        monkeypatch.delenv(key,raising=False)
    with pytest.raises(RuntimeError,match='OIDC mode requires'):
        create_app(data_dir=tmp_path,mode='oidc')


def test_asset_download_tenant_scoped(env):
    c,_,t,other,_,h=env
    path=f'/api/studio/t/{t}/scenarios/warehouse-transfer/assets/urdf'
    assert c.get(path,headers=h('owner')).status_code==200
    assert c.get(path,headers=h('other')).status_code==404


def test_headers_prevent_embedding(env):
    c,*_=env
    r=c.get('/studio')
    assert r.headers['X-Frame-Options']=='DENY'
    assert "script-src 'self'" in r.headers['Content-Security-Policy']


def test_uploaded_content_detects_posthoc_mutation(env):
    c,db,t,_,_,h=env;p=add_project(env)
    path=f'/api/studio/t/{t}/projects/{p}/evidence?filename=record.json&format=json'
    r=c.post(path,headers={**h('owner'),'Content-Type':'application/octet-stream'},content=b'{"tick":0}')
    assert r.status_code==201
    eid=r.json()['id']
    chk=f'/api/studio/t/{t}/projects/{p}/evidence/{eid}/integrity'
    assert c.get(chk,headers=h('owner')).json()['sha256_matches_upload']
    (db.root/'evidence'/t/(eid+'.json')).write_bytes(b'{"tick":1}')
    status=c.get(chk,headers=h('viewer')).json()
    assert not status['sha256_matches_upload'] and not status['source_authenticity_established']


def test_project_report_does_not_truncate_after_100_records(env):
    c,db,t,_,_,h=env;p=add_project(env)
    with db.conn(write=True) as sql:
        for i in range(120):
            sql.execute('''INSERT INTO runs (id,tenant_id,project_id,scenario_id,policy,seed,shield,created_by,
                           status,created_at,updated_at,summary_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (f'{i:032x}',t,p,'warehouse-transfer','route',i,1,'actor','completed',time.time(),time.time(),
                         json.dumps({'verified':True,'task_completed':True,'safety_violations':0})))
    report=c.get(f'/api/studio/t/{t}/projects/{p}/report',headers=h('owner')).json()
    assert report['summary']['completed_runs']==120


def test_whitespace_only_project_name_rejected(env):
    c,db,t,_,_,h=env
    r=c.post(f'/api/studio/t/{t}/projects',headers=h('owner'),json={'name':'   '})
    assert r.status_code==422
