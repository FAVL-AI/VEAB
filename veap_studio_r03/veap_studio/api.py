"""Localhost-only research-pilot API. Do not expose to untrusted networks."""
from __future__ import annotations
import os
import shutil
import tempfile
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .store import Store, MAX_UPLOAD, KINDS
from .geometry import pointcloud, model_preview
from .integrations import probe_all
from .operations import Jobs
from .physics_comparison import compare_physics
from .contract_registry import Registry,Contract

ROOT=Path(__file__).resolve().parent.parent
WEB=ROOT/'web'

class CompareReq(BaseModel):
    reference_id: str
    candidate_id: str
class FaultReq(BaseModel):
    asset_id: str
    fault: str
    severity: float=Field(1,ge=.05,le=5)
    seed: int=17
class AnnotateReq(BaseModel):
    note: str=Field('',max_length=1000)
    tags: list[str]=Field(default_factory=list,max_length=16)
class JobReq(BaseModel):
    kind: str
    source_id: str | None=None

class InboxReq(BaseModel):
    name: str=Field(min_length=1,max_length=200)

class PhysicsCompareReq(BaseModel):
    reference_job_id: str
    candidate_job_id: str

class ReportReq(BaseModel):
    source_id: str
    candidate_id: str | None=None

def create_app(data_root=None, seed_demo=True):
    store=Store(data_root or os.environ.get('VEAP_STUDIO_DATA',str(ROOT/'local_data')),seed_demo=seed_demo)
    jobs=Jobs(store)
    registry=Registry(store)
    inbox=Path(os.environ.get('VEAP_INBOX',str(store.root/'inbox'))).resolve()
    inbox.mkdir(parents=True,exist_ok=True)
    app=FastAPI(title='VEAP Studio R0.3 — sovereign robotics workspace',docs_url='/docs')
    app.state.store=store
    app.state.jobs=jobs
    app.mount('/assets', StaticFiles(directory=WEB), name='assets')
    async def auth(request:Request):
        secret=os.environ.get('VEAP_STUDIO_TOKEN')
        if secret:
            import hmac
            v=request.headers.get('x-veap-token','')
            if not hmac.compare_digest(v,secret):raise HTTPException(status_code=401,detail='invalid token')
    @app.middleware('http')
    async def headers(request:Request,call_next):
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'self' 'unsafe-inline' data: blob:; img-src 'self' data: blob:; media-src 'self' data: blob:; connect-src 'self'"
        return response
    @app.get('/')
    def index():return FileResponse(WEB/'index.html',media_type='text/html')
    @app.get('/api/health')
    def health():return {'status':'LOCAL_RESEARCH_PILOT','schema':'veap.studio.v0.3','source_authenticity':'UNATTESTED','network_boundary':'127.0.0.1 only','ui':'VEAP_NATIVE','external_visualization_dependencies':False,'robot_actuator_authority':False}
    @app.get('/api/assets',dependencies=[Depends(auth)])
    def assets():return {'assets':store.list_assets()}
    @app.post('/api/assets',dependencies=[Depends(auth)])
    async def upload(file: UploadFile=File(...),classification:str=Form('UNKNOWN')):
        suffix=Path(file.filename or '').suffix.lower()
        if suffix not in KINDS:raise HTTPException(status_code=400,detail='unsupported file extension')
        fd,tmp=tempfile.mkstemp(suffix=suffix)
        count=0
        try:
            with os.fdopen(fd,'wb') as writer:
                while data:=await file.read(1024*1024):
                    count+=len(data)
                    if count>MAX_UPLOAD:raise HTTPException(status_code=413,detail='upload exceeds 128MB')
                    writer.write(data)
            return {'asset':store.put(file.filename or ('asset'+suffix),tmp,forced_kind=classification)}
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
        finally:
            Path(tmp).unlink(missing_ok=True)
            await file.close()
    @app.get('/api/assets/{asset_id}',dependencies=[Depends(auth)])
    def get_asset(asset_id:str):
        try:return store.asset(asset_id)
        except KeyError:raise HTTPException(status_code=404)
    @app.patch('/api/assets/{asset_id}',dependencies=[Depends(auth)])
    def annotate(asset_id:str,req:AnnotateReq):
        if any(not tag or len(tag)>35 or any(x in tag for x in '\x00\n\r') for tag in req.tags):
            raise HTTPException(status_code=422,detail='invalid tag')
        try:return {'asset':store.annotate(asset_id,req.note,req.tags)}
        except KeyError:raise HTTPException(status_code=404)
    @app.get('/api/assets/{asset_id}/text-preview',dependencies=[Depends(auth)])
    def text_preview(asset_id:str):
        try:a=store.asset(asset_id)
        except KeyError:raise HTTPException(status_code=404)
        if a['kind']!='LOG':raise HTTPException(status_code=422,detail='not a text log')
        with (store.blobs/a['blob_name']).open('r',encoding='utf-8',errors='replace') as f:
            text=f.read(128_000)
        return {'asset_id':asset_id,'text':text,'truncated':a['size']>128_000,
                'scope':'TEXT_PREVIEW_ONLY','source_authenticity':'UNATTESTED'}
    @app.get('/api/assets/{asset_id}/raw',dependencies=[Depends(auth)])
    def raw(asset_id:str):
        try:a=store.asset(asset_id)
        except KeyError:raise HTTPException(status_code=404)
        extension=Path(a['name']).suffix.lower()
        content_type={'.mp4':'video/mp4','.webm':'video/webm','.png':'image/png','.jpeg':'image/jpeg','.jpg':'image/jpeg','.jsonl':'application/x-ndjson','.csv':'text/csv'}.get(extension,'application/octet-stream')
        return FileResponse(store.blobs/a['blob_name'],media_type=content_type,filename=a['name'] if content_type=='application/octet-stream' else None)
    @app.get('/api/traces/{asset_id}',dependencies=[Depends(auth)])
    def trace(asset_id:str):
        try:
            a=store.asset(asset_id)
            rows=store.trace(asset_id)
            step=max(1,len(rows)//4000)
            return {'asset':a,'rows':rows[::step],'sampling_stride':step,'report':store.report(asset_id)}
        except KeyError:raise HTTPException(status_code=404)
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.get('/api/geometry/{asset_id}',dependencies=[Depends(auth)])
    def geometry(asset_id:str):
        try:
            a=store.asset(asset_id)
            if a['kind'] not in ('MODEL_3D','CAD','ROBOT_DESCRIPTION'):
                raise ValueError('asset is not a robot model or CAD file')
            return {'asset_id':asset_id,'geometry':model_preview(store.blobs/a['blob_name'])}
        except KeyError:raise HTTPException(status_code=404)
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.get('/api/reconstruct/{asset_id}',dependencies=[Depends(auth)])
    def reconstruct(asset_id:str):
        try:
            a=store.asset(asset_id)
            if a['kind']!='POINT_CLOUD':raise ValueError('asset is not a point cloud')
            return {'asset_id':asset_id,'reconstruction':pointcloud(store.blobs/a['blob_name'])}
        except KeyError:raise HTTPException(status_code=404)
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.post('/api/compare',dependencies=[Depends(auth)])
    def compare(req:CompareReq):
        try:return store.compare(req.reference_id,req.candidate_id)
        except KeyError:raise HTTPException(status_code=404)
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.post('/api/counterfactual',dependencies=[Depends(auth)])
    def fault(req:FaultReq):
        try:return store.counterfactual(req.asset_id,req.fault,req.severity,req.seed)
        except KeyError:raise HTTPException(status_code=404)
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.post('/api/reports',dependencies=[Depends(auth)])
    def create_report(req:ReportReq):
        try:return store.save_report(req.source_id,req.candidate_id)
        except KeyError:raise HTTPException(status_code=404)
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.post('/api/physics/compare',dependencies=[Depends(auth)])
    def compare_native(req:PhysicsCompareReq):
        try:
            a=jobs.get(req.reference_job_id);b=jobs.get(req.candidate_job_id)
            if a['kind']==b['kind'] or {a['kind'],b['kind']}!={'mujoco_fall','isaac_fall'}:
                raise ValueError('requires one Isaac and one MuJoCo native run')
            if a['status']!='COMPLETED' or b['status']!='COMPLETED':
                raise ValueError('both native runs must complete')
            return compare_physics(jobs.root/a['id']/'trajectory.jsonl',
                                   jobs.root/b['id']/'trajectory.jsonl',a['result'],b['result'])
        except KeyError:raise HTTPException(status_code=404,detail='missing physics job')
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.get('/api/inbox',dependencies=[Depends(auth)])
    def list_inbox():
        files=[]
        for entry in sorted(inbox.iterdir(),key=lambda x:x.name)[:200]:
            if entry.is_file() and not entry.is_symlink() and entry.suffix.lower() in KINDS:
                files.append({'name':entry.name,'bytes':entry.stat().st_size})
        return {'root':str(inbox),'files':files,'custody':'UNATTESTED_LOCAL_STAGING'}
    @app.post('/api/inbox/import',dependencies=[Depends(auth)])
    def import_inbox(req:InboxReq):
        if Path(req.name).name!=req.name or '/' in req.name or '\\' in req.name:
            raise HTTPException(status_code=422,detail='filename must be a single basename')
        path=inbox/req.name
        if not path.is_file() or path.is_symlink():raise HTTPException(status_code=404)
        size=path.stat().st_size
        if size==0 or size>8*1024**3:raise HTTPException(status_code=413,detail='local import outside size limits')
        if shutil.disk_usage(store.root).free < size+10*1024**3:
            raise HTTPException(status_code=507,detail='insufficient available storage for protected copy')
        try:return {'asset':store.put(req.name,path,origin='LOCAL_INBOX_UNATTESTED',
                          max_size=8*1024**3)}
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.get('/api/contracts',dependencies=[Depends(auth)])
    def contracts():return {'contracts':registry.list()}
    @app.post('/api/contracts',dependencies=[Depends(auth)])
    def add_contract(contract:Contract):return registry.add(contract)
    @app.post('/api/contracts/{contract_id}/evaluate/{asset_id}',dependencies=[Depends(auth)])
    def evaluate_contract(contract_id:str,asset_id:str):
        try:return registry.evaluate(contract_id,asset_id)
        except KeyError:raise HTTPException(status_code=404,detail='contract or asset not found')
        except (ValueError,RuntimeError) as e:raise HTTPException(status_code=422,detail=str(e))
    @app.get('/api/integrations',dependencies=[Depends(auth)])
    def integrations():return probe_all()
    @app.get('/api/jobs',dependencies=[Depends(auth)])
    def list_jobs():return {'jobs':jobs.list()}
    @app.post('/api/jobs',dependencies=[Depends(auth)])
    def create_job(req:JobReq):
        try:return {'job':jobs.create(req.kind,req.source_id)}
        except KeyError:raise HTTPException(status_code=404,detail='source asset missing')
        except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    @app.get('/api/jobs/{job_id}',dependencies=[Depends(auth)])
    def job(job_id:str):
        try:return {'job':jobs.get(job_id)}
        except KeyError:raise HTTPException(status_code=404)
    @app.get('/api/jobs/{job_id}/artifact/{name}',dependencies=[Depends(auth)])
    def job_artifact(job_id:str,name:str):
        try:j=jobs.get(job_id)
        except KeyError:raise HTTPException(status_code=404)
        if j['status']!='COMPLETED' or name not in ('veap_reference.usda','veap_reference.xml','veap_reference.sdf','veap_reference.gltf','manifest.json','run.json'):
            raise HTTPException(status_code=404)
        file=jobs.root/job_id/name
        if not file.is_file():raise HTTPException(status_code=404)
        return FileResponse(file,media_type='application/octet-stream',filename=name)
    return app

app=create_app()
