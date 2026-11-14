from __future__ import annotations
import hashlib
import math
import json
import os
import random
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .analysis import load_trace, inspect_trace, inject_fault, compare_traces
from .mcap_meta import probe

MAX_UPLOAD = 128*1024*1024
KINDS={'.mcap':'MCAP','.db3':'ROS_BAG','.jsonl':'TRAJECTORY','.csv':'TRAJECTORY','.json':'DATASET',
       '.mp4':'VIDEO','.webm':'VIDEO','.mov':'VIDEO','.jpg':'IMAGE','.jpeg':'IMAGE','.png':'IMAGE',
       '.glb':'MODEL_3D','.gltf':'MODEL_3D','.obj':'MODEL_3D','.stl':'MODEL_3D','.usd':'MODEL_3D',
       '.usda':'MODEL_3D','.usdc':'MODEL_3D','.urdf':'ROBOT_DESCRIPTION','.xml':'ROBOT_DESCRIPTION',
       '.step':'CAD','.stp':'CAD','.ply':'POINT_CLOUD','.pcd':'POINT_CLOUD','.xyz':'POINT_CLOUD',
       '.txt':'LOG','.log':'LOG'}

def utc():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def sha_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

class Store:
    def __init__(self, root, seed_demo=True):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.blobs=self.root/'blobs';self.blobs.mkdir(exist_ok=True)
        self.lock=threading.RLock();self.db=self.root/'index.sqlite3'
        with self.connect() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,
              sha256 TEXT NOT NULL, size INTEGER NOT NULL,created TEXT NOT NULL,origin TEXT NOT NULL,
              note TEXT NOT NULL,meta TEXT NOT NULL,blob_name TEXT NOT NULL)''')
            con.execute('''CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,source_id TEXT,ref_id TEXT,
                created TEXT,body TEXT NOT NULL)''')
        if seed_demo and not self.list_assets():self.seed()
    def connect(self):return sqlite3.connect(str(self.db),timeout=12)
    def list_assets(self):
        with self.connect() as con:
            rows=con.execute('SELECT id,name,kind,sha256,size,created,origin,note,meta FROM assets ORDER BY created DESC,id DESC').fetchall()
        return [dict(zip(('id','name','kind','sha256','size','created','origin','note','meta'),
                         r[:8]+(json.loads(r[8]),))) for r in rows]
    def asset(self,id):
        with self.connect() as con:
            r=con.execute('SELECT id,name,kind,sha256,size,created,origin,note,meta,blob_name FROM assets WHERE id=?',(id,)).fetchone()
        if r is None:raise KeyError(id)
        return dict(zip(('id','name','kind','sha256','size','created','origin','note','meta','blob_name'),r[:8]+(json.loads(r[8]),r[9])))
    def put(self, name, path, origin='UPLOAD_UNATTESTED', note='', forced_kind=None, max_size=MAX_UPLOAD):
        ext=Path(name).suffix.lower();kind=KINDS.get(ext)
        if not kind:raise ValueError('unsupported file extension')
        if forced_kind and forced_kind not in ('UNKNOWN','ROBOT','SCENE','TELEMETRY','SIMULATOR'):
            raise ValueError('invalid classification')
        size=Path(path).stat().st_size
        if size>max_size:raise ValueError('file exceeds configured size limit')
        if not size:raise ValueError('empty file')
        fid=uuid.uuid4().hex
        blob=f'{fid}{ext}'
        import shutil
        dest=self.blobs/blob
        shutil.copyfile(path,dest)
        dest.chmod(0o600)
        digest=sha_file(dest)
        meta={'provenance':'UNATTESTED','source_type':kind,'analysis_status':'NOT_ANALYSED','classification':forced_kind or 'UNKNOWN','tags':[]}
        if kind=='TRAJECTORY':
            try:
                rows=load_trace(dest);s=inspect_trace(rows)
                meta.update({'samples':len(rows),'duration_s':s['duration_s'],'analysis_status':'ANALYSED_2D_TRACE','verdict':s['verdict']})
            except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
                dest.unlink(missing_ok=True);raise ValueError('invalid trajectory: '+str(e))
        elif kind=='MCAP':
            try:meta.update(probe(dest))
            except ValueError as e:dest.unlink(missing_ok=True);raise ValueError('invalid MCAP: '+str(e))
        elif kind=='IMAGE':
            from PIL import Image
            try:
                with Image.open(dest) as im:im.verify()
            except Exception as e:dest.unlink(missing_ok=True);raise ValueError('invalid image') from e
        with self.lock,self.connect() as con:
            con.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (fid,Path(name).name[:150],kind,digest,size,utc(),origin,note[:1000],json.dumps(meta),blob))
        return self.asset(fid)
    def annotate(self,id,note,tags):
        with self.lock,self.connect() as con:
            row=con.execute('SELECT meta FROM assets WHERE id=?',(id,)).fetchone()
            if row is None:raise KeyError(id)
            meta=json.loads(row[0]);meta['tags']=tags
            con.execute('UPDATE assets SET note=?,meta=? WHERE id=?',(note,json.dumps(meta),id))
        return self.asset(id)
    def trace(self,id):
        a=self.asset(id)
        if a['kind']!='TRAJECTORY':raise ValueError('this asset is not a decoded trajectory')
        return load_trace(self.blobs/a['blob_name'])
    def report(self,id):
        rows=self.trace(id);a=self.asset(id)
        rep=inspect_trace(rows)
        rep.update({'asset_id':id,'name':a['name'],'sha256':a['sha256'],'source':a['origin'],'provenance':a['meta'].get('provenance','UNATTESTED')})
        # R0.2 used a fixed demonstration warehouse goal and keep-out region for every
        # uploaded file. That is scientifically invalid for unrelated real robot logs.
        if a['origin'] not in ('DEMO_SYNTHETIC','DERIVED_SYNTHETIC_FAULT'):
            rep['demo_contract_analysis']={key:rep[key] for key in ('task_complete','process_accepted','violations','issues')}
            rep['task_complete']=None
            rep['process_accepted']=None
            rep['violations']=None
            rep['issues']=['No authenticated, calibrated task contract is bound to this source']
            rep['contract_applicability']='NO_MATCHING_CONTRACT'
            rep['verdict']='MEASURED_TRACE_ONLY_NO_ASSURANCE_VERDICT'
            rep['physics_validation']='NOT_ESTABLISHED'
            rep['analysis_scope']='TIME_SERIES_2D_AUDIT_WITHOUT_SCOPED_TASK_CONTRACT'
        if a['origin']=='NATIVE_SIMULATOR_UNATTESTED':
            rep['verdict']='NATIVE_PHYSICS_TRACE_AVAILABLE_NO_SAFETY_VERDICT'
            rep['analysis_scope']='NATIVE_3D_TRACE_NO_SCOPED_TASK_CONTRACT'
            rep['issues']=['Native physics trace has no matching physics-specific safety contract']
        return rep
    def compare(self,left,right):
        res=compare_traces(self.trace(left),self.trace(right))
        res['reference_id']=left;res['candidate_id']=right
        return res
    def counterfactual(self,id,kind,severity,seed=17):
        if not 0.05<=severity<=5:raise ValueError('severity must be between 0.05 and 5')
        asset=self.asset(id)
        rows=inject_fault(self.trace(id),kind,severity,seed)
        f=self.root/f'counterfactual-{uuid.uuid4().hex}.jsonl'
        try:
            with f.open('w') as w:
                for row in rows:w.write(json.dumps(row,allow_nan=False)+'\n')
            result=self.put(f'{kind}_{asset["name"].removesuffix(".jsonl").removesuffix(".csv")}.jsonl',f,
                            origin='DERIVED_SYNTHETIC_FAULT',note='Counterfactual analytic perturbation; NOT physical fault injection')
        finally:f.unlink(missing_ok=True)
        return {'asset':result,'report':self.report(result['id']),'fault':kind,'severity':severity,'seed':seed,
                'simulation_scope':'ANALYTIC_COUNTERFACTUAL_ONLY'}
    def save_report(self,source,ref=None):
        result=self.report(source)
        if ref:result['comparison']=self.compare(source,ref)
        result['evidence_level']='IMPLEMENTED / DEMONSTRATED WITHIN RECORDED-TRACE SCOPE'
        result['not_claimed']=['independent sensor truth','physical safety','digital twin validated','certification','SOTA']
        report_id=uuid.uuid4().hex
        with self.connect() as con:
            con.execute('INSERT INTO reports VALUES(?,?,?,?,?)',(report_id,source,ref,utc(),json.dumps(result)))
        result['report_id']=report_id
        return result
    def seed(self):
        import tempfile
        rng=random.Random(22)
        demo=[('M3 · Yard Inspection',.0,'DEMO_SYNTHETIC'),('Isaac Lab · M3 surrogate',.10,'DEMO_SYNTHETIC'),('MuJoCo · M3 surrogate',-.13,'DEMO_SYNTHETIC'),('G1 · Facility Walk',.42,'DEMO_SYNTHETIC')]
        for name,offset,origin in demo:
            rows=[]
            for i in range(161):
                u=i/160;t=i*100_000_000
                x=.9+9.6*u+offset*math.sin(u*math.pi*3)
                y=1.2+6*u+offset*math.cos(u*math.pi*2)
                if name.startswith('M3 ·') and 65<=i<=84:y=3.35;x=4.0+0.05*(i-65)
                rows.append({'t_ns':t,'x_m':round(x,4),'y_m':round(y,4),'yaw_rad':round(math.atan2(6,9.6),3),
                  'speed_m_s':round(.55+.12*math.sin(i*.15),3),'clearance_m':round(.65+.18*math.sin(i*.12),3),
                  'latency_ms':round(14+5*math.cos(i*.16),2),'sensor_ok':True,
                  'cmd_vel':[round(.6+.05*math.cos(i*.1),3),round(.375+.03*math.sin(i*.1),3),0.0],
                  'event':('UNSAFE KEEP-OUT' if i==75 and name.startswith('M3 ·') else '')})
            tfile=self.root/'_demo.jsonl'
            with tfile.open('w') as o:
                for r in rows:o.write(json.dumps(r)+'\n')
            self.put(name+'.jsonl',tfile,origin=origin,note='Generated surrogate data; not real Isaac/MuJoCo/hardware')
            tfile.unlink(missing_ok=True)
