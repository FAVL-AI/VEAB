"""VEAP Assurance Studio: separated pilot API, no robot actuation endpoints.

Run with: uvicorn veap.enterprise.api:app --host 127.0.0.1 --port 8010
The legacy unscoped /api/runs is NOT mounted here. This is an isolated app.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import Identity, authenticate, authorize, check_deployment_config
from .db import StudioDB, canonical
from ..sim import run_episode
from ..spec import list_scenarios, load_scenario
from ..verifier import verify_bundle
from ..simulation.engine import engine_status
from ..simulation.scene import compile_scene

BASE=Path(__file__).resolve().parent.parent.parent
STATIC=BASE / 'web' / 'assurance_studio'
LIMIT_BYTES=12*1024*1024
NAME_RX=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
ALLOWED_ASSETS={'usda','xml','sdf','urdf','glb','scene.json'}
WRITERS={'owner','researcher'}
READERS={'owner','researcher','reviewer','auditor','viewer'}
REVIEWERS={'owner','reviewer'}
AUDITORS={'owner','auditor'}


class ProjectCreate(BaseModel):
    name: str=Field(min_length=2,max_length=100)
    description: str=Field(default='',max_length=1200)

class RunCreate(BaseModel):
    scenario_id: str=Field(pattern=r'^[a-z0-9-]{1,64}$')
    policy: Literal['greedy','route']='route'
    seed: int=Field(default=17,ge=0,le=2**32-1)
    shield: bool=True
    request_key: str | None=Field(default=None,min_length=6,max_length=90,pattern=r'^[a-zA-Z0-9_-]+$')

class ReviewCreate(BaseModel):
    verdict: Literal['accepted','rejected','inconclusive']
    rationale: str=Field(min_length=8,max_length=3000)


class Worker:
    """Bounded single-process demo executor. No HA or durable cross-node leasing."""
    def __init__(self,db: StudioDB, *, max_workers: int=2, capacity: int=8):
        self.db=db
        self.pool=ThreadPoolExecutor(max_workers=max_workers,thread_name_prefix='veap-studio')
        self.slots=threading.BoundedSemaphore(capacity)

    def submit(self,tenant:str,run_id:str,scenario_id:str,policy:str,seed:int,shield:bool) -> bool:
        if not self.slots.acquire(blocking=False):
            return False
        try:
            self.pool.submit(self._execute,tenant,run_id,scenario_id,policy,seed,shield)
            return True
        except Exception:
            self.slots.release()
            raise

    def _execute(self,tenant:str,run_id:str,scenario_id:str,policy:str,seed:int,shield:bool):
        try:
            self.db.update_run(tenant,run_id,status='running')
            scenario=load_scenario(scenario_id)
            # This invokes the EXISTING local deterministic simulator only.
            # No ROS 2, Isaac Lab, MuJoCo or physical robot commands are issued.
            key=os.getenv('VEAP_STUDIO_BUNDLE_HMAC_KEY') or os.getenv('VEAB_STUDIO_BUNDLE_HMAC_KEY')
            bundle=run_episode(scenario,policy,seed,shield,attestation_key=key)
            report=verify_bundle(bundle,key,require_attestation=bool(key))
            data=canonical({**bundle,'verification':report}).encode()
            sha=hashlib.sha256(data).hexdigest()
            folder=self.db.root / 'runs' / tenant
            folder.mkdir(parents=True,exist_ok=True,mode=0o700)
            target=folder / (run_id+'.json')
            fd,tmp=tempfile.mkstemp(dir=folder,prefix='.partial-')
            try:
                with os.fdopen(fd,'wb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(tmp,0o600)
                os.replace(tmp,target)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            self.db.update_run(tenant,run_id,status='completed',summary=report,sha256=sha)
        except Exception:
            # Keep sensitive paths and tracebacks out of customers' responses.
            self.db.update_run(tenant,run_id,status='failed',error='Execution failed; check operator logs')
        finally:
            self.slots.release()

    def close(self):
        self.pool.shutdown(wait=True,cancel_futures=False)


def tenant_guard(tenant:str,principal:Identity,request:Request,roles:set[str])->str:
    return authorize(request.app.state.studio_db,tenant,principal.id,roles)

def project_guard(tenant:str,project:str,request:Request)->dict:
    result=request.app.state.studio_db.project(tenant,project)
    if result is None:raise HTTPException(404,'Project not found')
    return result

def run_guard(tenant:str,project:str,run_id:str,request:Request)->dict:
    result=request.app.state.studio_db.run(tenant,run_id)
    if result is None or result['project_id']!=project:raise HTTPException(404,'Run not found')
    return result


def validate_jsonl(path:Path)->dict:
    import math
    n=0
    with path.open('r',encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            item=json.loads(line)
            if type(item) is not dict or set(item)!={'tick','x','y','vx','vy'}:
                raise ValueError('JSONL requires exactly tick,x,y,vx,vy')
            if type(item['tick']) is not int or item['tick']!=n:
                raise ValueError('Ticks must be contiguous from zero')
            if not all(type(item[k]) in (int,float) and math.isfinite(item[k]) and abs(item[k])<1e5
                       for k in ('x','y','vx','vy')):
                raise ValueError('Invalid numeric state')
            n+=1
            if n>30000: raise ValueError('Too many samples')
    if n<2:raise ValueError('At least two samples required')
    return {'samples':n,'schema':'veab-positional-jsonl/1'}


def report_html(report:dict)->str:
    h=lambda value: html.escape(str(value),quote=True)
    rows=''.join('<tr><th>'+h(k.replace('_',' ').title())+'</th><td>'+h(v)+'</td></tr>'
                 for k,v in report['summary'].items())
    return ('<!doctype html><html><head><meta charset="utf-8"><title>VEAP Evidence Report</title>'
            '<style>body{font:16px system-ui;max-width:820px;margin:48px auto;padding:0 22px;color:#172434}'
            'table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ccd5dc;padding:12px;text-align:left}'
            '.alert{border-left:4px solid #ab7222;padding:12px;background:#fbf5eb}</style></head><body>'
            '<h1>VEAP Assurance Studio</h1><p>Research / operational evidence report</p><h2>'+h(report['project']['name'])+'</h2>'
            '<table>'+rows+'</table><h2>Validation boundary</h2><p class="alert">'
            'Local toy-world results and uploaded files do not establish hardware safety, sensor authenticity, '
            'physical fidelity, certification, or SOTA. Uploaded evidence is not attested.</p>'
            '<p>Generated from the tenant-scoped Studio registry. Review raw evidence before any operational decision.</p>'
            '</body></html>')


def create_app(*, data_dir: str | Path | None = None, mode: str | None = None) -> FastAPI:
    auth_mode=mode or os.getenv('VEAP_STUDIO_AUTH_MODE') or os.getenv('VEAB_STUDIO_AUTH_MODE','dev-token')
    check_deployment_config(auth_mode)
    if (os.getenv('VEAP_STUDIO_RELEASE') or os.getenv('VEAB_STUDIO_RELEASE','pilot')) != 'pilot':
        raise RuntimeError('This release is pilot-only; production qualification gates are incomplete')
    root=data_dir or os.getenv('VEAP_STUDIO_DATA_DIR') or os.getenv('VEAB_STUDIO_DATA_DIR',str(BASE/'studio-data'))
    db=StudioDB(root)

    @asynccontextmanager
    async def lifespan(app:FastAPI):
        db.interrupt_orphans()
        app.state.worker=Worker(db)
        yield
        app.state.worker.close()

    api=FastAPI(title='VEAP Assurance Studio',version='0.5.0-dev',
                docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    api.state.studio_db=db
    api.state.auth_mode=auth_mode

    @api.middleware('http')
    async def security_headers(request:Request,call_next):
        response=await call_next(request)
        for key,value in {
            'X-Content-Type-Options':'nosniff',
            'X-Frame-Options':'DENY',
            'Referrer-Policy':'no-referrer',
            'Cross-Origin-Resource-Policy':'same-origin',
            'Content-Security-Policy':"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            'Cache-Control':'no-store',
        }.items():response.headers[key]=value
        return response

    @api.get('/api/studio/health')
    def health():
        return {'status':'ok','release':'0.5.0-dev','mode':'research-pilot',
                'auth_mode':auth_mode,'robot_actuation':False,'production_qualified':False}

    @api.get('/api/studio/me')
    def me(principal:Identity=Depends(authenticate)):
        return {'id':principal.id,'name':principal.name,'email':principal.email,
                'tenants':db.my_tenants(principal.id)}

    @api.get('/api/studio/engines')
    def engines(principal:Identity=Depends(authenticate)):
        return engine_status()

    @api.get('/api/studio/t/{tenant}/scenarios')
    def scenarios(tenant:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        return [{'id':s.id,'title':s.title,'family':s.family,'split':s.split}
                for s in list_scenarios()]

    @api.get('/api/studio/t/{tenant}/scenarios/{scenario_id}/scene')
    def scene(tenant:str,scenario_id:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        try:return compile_scene(load_scenario(scenario_id))
        except (FileNotFoundError,ValueError):raise HTTPException(404,'Scenario not found')

    @api.get('/api/studio/t/{tenant}/scenarios/{scenario_id}/assets/{extension}')
    def scene_asset(tenant:str,scenario_id:str,extension:str,request:Request,
                    principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        if extension not in ALLOWED_ASSETS or not re.fullmatch(r'[a-z0-9-]{1,64}',scenario_id):
            raise HTTPException(404,'Asset not found')
        try:load_scenario(scenario_id)
        except (FileNotFoundError,ValueError):raise HTTPException(404,'Scenario not found')
        folder=BASE/'assets'/'generated'/scenario_id
        filename=scenario_id+'.'+extension
        p=folder/filename
        if not p.is_file():raise HTTPException(404,'Asset not generated')
        return FileResponse(p,filename=filename,media_type='application/octet-stream')

    @api.get('/api/studio/t/{tenant}/projects')
    def projects(tenant:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        return db.projects(tenant)

    @api.post('/api/studio/t/{tenant}/projects',status_code=201)
    def create_project(tenant:str,body:ProjectCreate,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,WRITERS)
        
        if len(body.name.strip())<2:raise HTTPException(422,'Project name must contain at least two non-whitespace characters')
        return db.create_project(tenant,principal.id,body.name.strip(),body.description)

    @api.get('/api/studio/t/{tenant}/projects/{project}')
    def get_project(tenant:str,project:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        return project_guard(tenant,project,request)

    @api.get('/api/studio/t/{tenant}/projects/{project}/runs')
    def runs(tenant:str,project:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        project_guard(tenant,project,request)
        return db.runs(tenant,project)

    @api.post('/api/studio/t/{tenant}/projects/{project}/runs',status_code=202)
    def start_run(tenant:str,project:str,body:RunCreate,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,WRITERS)
        project_guard(tenant,project,request)
        try:load_scenario(body.scenario_id)
        except (FileNotFoundError,ValueError):raise HTTPException(404,'Scenario not found')
        try:
            row,created=db.create_run(tenant,project,principal.id,body.scenario_id,body.policy,
                                      body.seed,body.shield,body.request_key)
        except ValueError as exc:raise HTTPException(409,str(exc))
        if created and not request.app.state.worker.submit(tenant,row['id'],body.scenario_id,body.policy,
                                                           body.seed,body.shield):
            db.update_run(tenant,row['id'],status='rejected',error='Queue at capacity')
            raise HTTPException(429,'Experiment queue capacity reached')
        return {'id':row['id'],'status':row['status'],'idempotent_replay':not created}

    @api.get('/api/studio/t/{tenant}/projects/{project}/runs/{run_id}')
    def get_run(tenant:str,project:str,run_id:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        return run_guard(tenant,project,run_id,request)

    @api.get('/api/studio/t/{tenant}/projects/{project}/runs/{run_id}/bundle')
    def bundle(tenant:str,project:str,run_id:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        run_guard(tenant,project,run_id,request)
        path=db.root/'runs'/tenant/(run_id+'.json')
        if not path.is_file():raise HTTPException(404,'Evidence is not ready')
        return FileResponse(path,filename='veap-'+run_id[:8]+'.json',media_type='application/json')

    @api.post('/api/studio/t/{tenant}/projects/{project}/runs/{run_id}/reviews',status_code=201)
    def add_review(tenant:str,project:str,run_id:str,body:ReviewCreate,
                   request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,REVIEWERS)
        run_guard(tenant,project,run_id,request)
        try:return db.review(tenant,run_id,principal.id,body.verdict,body.rationale)
        except PermissionError as exc:raise HTTPException(403,str(exc))
        except ValueError as exc:raise HTTPException(409,str(exc))
        except Exception as exc:
            if 'UNIQUE constraint' in str(exc):raise HTTPException(409,'Reviewer already submitted an assessment')
            raise

    @api.get('/api/studio/t/{tenant}/projects/{project}/runs/{run_id}/reviews')
    def list_reviews(tenant:str,project:str,run_id:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        run_guard(tenant,project,run_id,request)
        return db.reviews(tenant,run_id)

    @api.post('/api/studio/t/{tenant}/projects/{project}/evidence',status_code=201)
    async def upload_evidence(tenant:str,project:str,request:Request,
                              filename:str=Query(...,min_length=1,max_length=128),
                              format:Literal['jsonl','json','mcap']=Query(...),
                              principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,WRITERS)
        project_guard(tenant,project,request)
        if not NAME_RX.fullmatch(filename) or not filename.endswith('.'+format):
            raise HTTPException(422,'Filename must be simple and end in the selected format')
        if request.headers.get('content-type','').split(';',1)[0] != 'application/octet-stream':
            raise HTTPException(415,'Use application/octet-stream with a raw file body')
        folder=db.root/'evidence'/tenant
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd,tmp=tempfile.mkstemp(dir=folder,prefix='.upload-')
        h=hashlib.sha256()
        total=0
        try:
            with os.fdopen(fd,'wb') as f:
                async for chunk in request.stream():
                    total+=len(chunk)
                    if total>LIMIT_BYTES:raise HTTPException(413,'Evidence exceeds 12 MiB pilot limit')
                    h.update(chunk);f.write(chunk)
                f.flush();os.fsync(f.fileno())
            if total==0:raise HTTPException(422,'Empty evidence file')
            p=Path(tmp)
            if format=='jsonl':
                try:validate_jsonl(p)
                except (ValueError,UnicodeError,json.JSONDecodeError) as exc:
                    raise HTTPException(422,'Invalid JSONL evidence: '+str(exc)[:150])
            elif format=='json':
                try:
                    obj=json.loads(p.read_text(encoding='utf-8'),parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))
                    if not isinstance(obj,dict):raise ValueError('Top-level JSON object required')
                except (ValueError,UnicodeError,json.JSONDecodeError) as exc:
                    raise HTTPException(422,'Invalid JSON evidence: '+str(exc)[:150])
            elif format=='mcap':
                with p.open('rb') as f:
                    if f.read(8)!=b'\x89MCAP0\r\n':
                        raise HTTPException(422,'Not an MCAP container (invalid header)')
                # Header-only checking cannot validate MCAP messages or their provenance.
            digest=h.hexdigest()
            from .db import new_id
            eid=new_id()
            # Write record id after rename? File ID is stored in database; on DB error
            # the orphan is not listed, and can be garbage-collected by an operator.
            target=folder/(eid+'.'+format)
            os.chmod(tmp,0o600)
            os.replace(tmp,target)
            record=db.record_evidence(tenant,project,principal.id,filename,format,digest,total,
                                      'unattested_external')
            # Registry-generated id is authoritative; move file to that id atomically.
            final=folder/(record['id']+'.'+format)
            os.replace(target,final)
            return record
        finally:
            if os.path.exists(tmp):os.unlink(tmp)

    @api.get('/api/studio/t/{tenant}/projects/{project}/evidence')
    def evidence_list(tenant:str,project:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        project_guard(tenant,project,request)
        return db.evidence_list(tenant,project)

    @api.get('/api/studio/t/{tenant}/projects/{project}/evidence/{eid}/download')
    def evidence_download(tenant:str,project:str,eid:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        target=db.evidence_one(tenant,eid)
        if not target or target['project_id']!=project:raise HTTPException(404,'Evidence not found')
        p=db.root/'evidence'/tenant/(eid+'.'+target['format'])
        if not p.is_file():raise HTTPException(404,'Evidence object missing')
        return FileResponse(p,filename=target['filename'],media_type='application/octet-stream')

    @api.get('/api/studio/t/{tenant}/projects/{project}/evidence/{eid}/integrity')
    def evidence_integrity(tenant:str,project:str,eid:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        record=db.evidence_one(tenant,eid)
        if not record or record['project_id']!=project:raise HTTPException(404,'Evidence not found')
        p=db.root/'evidence'/tenant/(eid+'.'+record['format'])
        if not p.is_file():return {'record_found':True,'file_found':False,'sha256_matches_upload':False,
                                   'source_authenticity_established':False}
        hasher=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):hasher.update(chunk)
        return {'record_found':True,'file_found':True,'sha256_matches_upload':hasher.hexdigest()==record['content_sha256'],
                'source_authenticity_established':False,
                'caveat':'Storage consistency is not capture authenticity or physical truth.'}

    @api.get('/api/studio/t/{tenant}/projects/{project}/report')
    def assurance_report(tenant:str,project:str,request:Request,
                         format:Literal['json','html']='json',principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,READERS)
        p=project_guard(tenant,project,request)
        # Full project aggregation. Paginated dashboard lists must not silently
        # truncate assurance totals after their first 100 rows.
        records=db.rows('SELECT status,summary_json FROM runs WHERE tenant_id=? AND project_id=?',tenant,project)
        completed=[r for r in records if r['status']=='completed']
        with_summary=[json.loads(r['summary_json']) for r in completed if r['summary_json']]
        n_evidence=db.row('SELECT COUNT(*) AS n FROM evidence WHERE tenant_id=? AND project_id=?',tenant,project)['n']
        n_reviews=db.row('''SELECT COUNT(*) AS n FROM reviews a JOIN runs r ON a.run_id=r.id
                             WHERE a.tenant_id=? AND r.project_id=?''',tenant,project)['n']
        summary={
            'completed_runs':len(completed),
            'verifier_accepted_runs':sum(bool(s.get('verified')) for s in with_summary),
            'task_completed_runs':sum(bool(s.get('task_completed')) for s in with_summary),
            'recorded_constraint_violations':sum(int(s.get('safety_violations') or 0) for s in with_summary),
            'uploaded_evidence_files':n_evidence,
            'human_reviews':n_reviews,
            'external_sensor_truth_established':False,
            'physically_validated':False,
            'production_qualified':False,
        }
        report={'schema_version':'veab-assurance-report/1','project':p,'summary':summary,
                'limitations':['Toy-world simulator execution only','Imported evidence is unattested',
                               'Hash chains establish internal consistency, not external authenticity',
                               'No independent physical safety certification']}
        if format=='html':return HTMLResponse(report_html(report),headers={'Content-Disposition':'attachment; filename="veap-report.html"'})
        return report

    @api.get('/api/studio/t/{tenant}/audit')
    def audit(tenant:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,AUDITORS)
        return db.audit_events(tenant)

    @api.get('/api/studio/t/{tenant}/audit/verify')
    def audit_verify(tenant:str,request:Request,principal:Identity=Depends(authenticate)):
        tenant_guard(tenant,principal,request,AUDITORS)
        return db.audit_verify(tenant)

    @api.get('/studio',response_class=HTMLResponse)
    def dashboard():return FileResponse(STATIC/'index.html')

    api.mount('/studio/static',StaticFiles(directory=STATIC),name='studio-static')
    return api


app=create_app()
