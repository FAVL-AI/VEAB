import os
import time
from fastapi.testclient import TestClient
from veab import api
from veab.store import Store


def test_api_local_run_and_evidence_bundle(tmp_path,monkeypatch):
    monkeypatch.delenv('VEAB_ADMIN_TOKEN',raising=False)
    monkeypatch.setattr(api,'store',Store(tmp_path))
    client=TestClient(api.app)
    assert client.get('/api/health').status_code==200
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert len(client.get('/api/scenarios').json())>=5
    request=client.post('/api/runs',json={'scenario_id':'campus-patrol','policy':'route','shield':True,'seed':7})
    assert request.status_code==202
    run_id=request.json()['run_id']
    for _ in range(150):
        data=client.get('/api/runs/'+run_id).json()
        if data['status'] in ('completed','failed'):break
        time.sleep(.04)
    assert data['status']=='completed',data
    assert data['summary']['verified']
    assert data['manifest']['seed']==7
    assert client.get('/api/runs/'+run_id+'/bundle').status_code==200
    assert client.get('/api/runs').json()[0]['id']==run_id


def test_api_rejects_bad_input_and_requires_token(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'store',Store(tmp_path))
    monkeypatch.setenv('VEAB_ADMIN_TOKEN','test-sentry')
    client=TestClient(api.app)
    assert client.get('/api/health').status_code==401
    headers={'Authorization':'Bearer test-sentry'}
    assert client.get('/api/health',headers=headers).status_code==200
    assert client.post('/api/runs',headers=headers,json={'scenario_id':'bad-id'}).status_code==404
    assert client.post('/api/runs',headers=headers,json={'scenario_id':'campus-patrol','seed':-1}).status_code==422
    assert client.get('/api/runs/bad-id/bundle',headers=headers).status_code==400
