import asyncio
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from httpx import ASGITransport, AsyncClient
from veap_studio.api import create_app
from veap_studio.analysis import load_trace, inspect_trace, crosses_rect, compare_traces, inject_fault, ZONE
from veap_studio.mcap_meta import MAGIC, probe


def test_monitor_detects_between_samples():
    assert crosses_rect((2,3.1),(7,3.1),ZONE)
    assert not crosses_rect((1,1),(2,1),ZONE)


def test_monotonicity_rejects(tmp_path):
    f=tmp_path/'bad.jsonl'
    f.write_text(json.dumps({'t_ns':500,'x_m':1,'y_m':1})+'\n'+json.dumps({'t_ns':499,'x_m':1,'y_m':1})+'\n')
    with pytest.raises(ValueError,match='monotonic'):load_trace(f)


def test_nonfinite_rejects(tmp_path):
    f=tmp_path/'bad.csv';f.write_text('time,x,y\n0,NaN,1\n')
    with pytest.raises(ValueError,match='nonfinite'):load_trace(f)


def test_basic_comparator():
    a=[{'t_ns':i*100_000_000,'x_m':i,'y_m':0} for i in range(3)]
    b=[{'t_ns':i*100_000_000,'x_m':i+.5,'y_m':0} for i in range(3)]
    v=compare_traces(a,b)
    assert v['rmse_m']==.5
    assert v['physics_equivalence']=='NOT_ESTABLISHED'


def test_fault_is_derived_not_hardware():
    rows=[{'t_ns':i*1000,'x_m':i,'y_m':i,'sensor_ok':True,'latency_ms':0,'speed_m_s':.2} for i in range(30)]
    mutated=inject_fault(rows,'sensor_dropout',1)
    assert any(not x['sensor_ok'] for x in mutated)
    assert all(x['sensor_ok'] for x in rows)


def test_mcap_reject_corrupt(tmp_path):
    f=tmp_path/'x.mcap';f.write_bytes(b'123'*10)
    with pytest.raises(ValueError):probe(f)


def test_store_seeds(tmp_path):
    from veap_studio.store import Store
    s=Store(tmp_path)
    a=s.list_assets()
    assert len(a)==4
    assert all(x['origin']=='DEMO_SYNTHETIC' for x in a)
    m3=next(x for x in a if x['name'].startswith('M3 · Yard'))
    report=s.report(m3['id'])
    assert report['task_complete'] is True
    assert report['violations']>0


def test_api_smoke_and_fault(tmp_path):
    async def run():
        app=create_app(tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://testserver') as c:
            health=await c.get('/api/health');assert health.status_code==200
            r=await c.get('/api/assets');assert r.status_code==200
            data=r.json()['assets'];assert len(data)==4
            id=next(x['id'] for x in data if x['name'].startswith('M3 · Yard'))
            ref=next(x['id'] for x in data if x['name'].startswith('Isaac Lab'))
            a=await c.get(f'/api/traces/{id}');assert a.status_code==200
            assert a.json()['report']['violations']>0
            b=await c.post('/api/compare',json={'reference_id':id,'candidate_id':ref})
            assert b.status_code==200 and b.json()['rmse_m']>=0
            f=await c.post('/api/counterfactual',json={'asset_id':id,'fault':'sensor_dropout','severity':1,'seed':17})
            assert f.status_code==200
            assert f.json()['report']['dropouts']>0
            rep=await c.post('/api/reports',json={'source_id':id,'candidate_id':ref})
            assert rep.status_code==200 and 'not_claimed' in rep.json()
    asyncio.run(run())


def test_upload_valid_csv_and_reject_unsupported(tmp_path):
    async def run():
        app=create_app(tmp_path,seed_demo=False)
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://t') as c:
            good=b'time,x,y\n0,0,0\n1,1,1\n'
            r=await c.post('/api/assets',files={'file':('test.csv',good,'text/csv')},data={'classification':'TELEMETRY'})
            assert r.status_code==200,r.text
            a=r.json()['asset'];assert a['meta']['samples']==2
            r=await c.post('/api/assets',files={'file':('bad.exe',b'EXE','application/octet-stream')})
            assert r.status_code==400
    asyncio.run(run())


def test_upload_fake_mcap_rejected(tmp_path):
    async def run():
        app=create_app(tmp_path,seed_demo=False)
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://t') as c:
            r=await c.post('/api/assets',files={'file':('broken.mcap',MAGIC+b'x'*28,'application/octet-stream')})
            assert r.status_code==422
    asyncio.run(run())


def test_no_unsafe_website_headers(tmp_path):
    async def run():
        app=create_app(tmp_path,seed_demo=False)
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://t') as c:
            r=await c.get('/');assert r.status_code==200
            assert 'VEAP Studio' in r.text
            assert r.headers['X-Content-Type-Options']=='nosniff'
    asyncio.run(run())


def test_ascii_xyz_reconstruction(tmp_path):
    from veap_studio.geometry import pointcloud
    p=tmp_path/'scan.xyz';p.write_text('1 2 0.1\n1.1 2.2 0.4\n3 4 0.8\n')
    m=pointcloud(p)
    assert m['point_count_inspected']==3
    assert m['physical_surface_reconstruction']=='NOT_ESTABLISHED'


def test_urdf_topology(tmp_path):
    from veap_studio.geometry import model_preview
    p=tmp_path/'m3.urdf';p.write_text('<robot name="m3"><link name="base_link"/><link name="wheel"/><joint name="drive" type="continuous"><parent link="base_link"/><child link="wheel"/></joint></robot>')
    m=model_preview(p)
    assert len(m['joints'])==1
    assert m['physics_ready'] is False


def test_geometry_api(tmp_path):
    async def run():
        app=create_app(tmp_path,seed_demo=False)
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://t') as c:
            r=await c.post('/api/assets',files={'file':('points.xyz',b'1 1 0\n1 2 0.3\n','text/plain')})
            assert r.status_code==200
            asset=r.json()['asset']
            view=await c.get('/api/reconstruct/'+asset['id'])
            assert view.status_code==200
            assert len(view.json()['reconstruction']['points'])==2
    asyncio.run(run())


def test_minimal_valid_mcap_header(tmp_path):
    import struct
    from veap_studio.mcap_meta import MAGIC,probe
    def record(op,body):return bytes([op])+struct.pack('<Q',len(body))+body
    f=tmp_path/'tiny.mcap'
    # MCAP header, data end, footer, and both magic markers.
    f.write_bytes(MAGIC+record(1,struct.pack('<II',0,0))+record(0x0F,struct.pack('<I',0))+record(2,b'\x00'*20)+MAGIC)
    v=probe(f)
    assert v['container_valid'] is True
    assert v['decode_status'].startswith('NOT_DECODED')


def test_mcap_bad_footer(tmp_path):
    import struct
    def rec(op,data):return bytes([op])+struct.pack('<Q',len(data))+data
    f=tmp_path/'bad.mcap';f.write_bytes(MAGIC+rec(1,b'\x00'*8)+rec(2,b'\x00'*20)+MAGIC)
    with pytest.raises(ValueError,match='Data End'):probe(f)


def test_trace_derived_speed_overlimit():
    from veap_studio.analysis import inspect_trace
    rows=[{'t_ns':0,'x_m':0.,'y_m':0.,'speed_m_s':None,'sensor_ok':True,'latency_ms':None,'event':''},
          {'t_ns':100000000,'x_m':5.,'y_m':0.,'speed_m_s':None,'sensor_ok':True,'latency_ms':None,'event':''}]
    r=inspect_trace(rows)
    assert r['overspeed_count']>0
    assert r['max_latency_ms'] is None


def test_auth_token_blocks_access(tmp_path,monkeypatch):
    async def run():
        monkeypatch.setenv('VEAP_STUDIO_TOKEN','long-secret')
        app=create_app(tmp_path,seed_demo=False)
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://t') as c:
            assert (await c.get('/api/assets')).status_code==401
            assert (await c.get('/api/assets',headers={'x-veap-token':'long-secret'})).status_code==200
    asyncio.run(run())


def test_uploaded_files_are_hashed(tmp_path):
    from veap_studio.store import Store,sha_file
    a=Store(tmp_path,seed_demo=False)
    f=tmp_path/'points.xyz';f.write_text('1 2 3\n')
    meta=a.put('points.xyz',f)
    assert meta['sha256']==sha_file(a.blobs/a.asset(meta['id'])['blob_name'])
    assert meta['meta']['provenance']=='UNATTESTED'


def test_asset_tags_and_log_preview(tmp_path):
    async def run():
        app=create_app(tmp_path,seed_demo=False)
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://t') as c:
            r=await c.post('/api/assets',files={'file':('motor.log',b'2026-11-13 ERROR motor unavailable\n','text/plain')},data={'classification':'TELEMETRY'})
            assert r.status_code==200
            id=r.json()['asset']['id']
            assert r.json()['asset']['meta']['classification']=='TELEMETRY'
            patch=await c.patch('/api/assets/'+id,json={'note':'Inspection only','tags':['M3','hardware']})
            assert patch.status_code==200
            assert patch.json()['asset']['meta']['tags']==['M3','hardware']
            preview=await c.get('/api/assets/'+id+'/text-preview')
            assert preview.status_code==200 and 'motor unavailable' in preview.json()['text']
    asyncio.run(run())
