"""Versioned user-authored recorded-trajectory contracts + separate-process monitoring."""
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile,uuid
from pathlib import Path
from pydantic import BaseModel, Field, model_validator

class Zone(BaseModel):
    label: str=Field(min_length=1,max_length=80)
    x1: float=Field(ge=-1e6,le=1e6)
    y1: float=Field(ge=-1e6,le=1e6)
    x2: float=Field(ge=-1e6,le=1e6)
    y2: float=Field(ge=-1e6,le=1e6)
    @model_validator(mode='after')
    def correct(self):
        if not self.x1<self.x2 or not self.y1<self.y2:raise ValueError('invalid forbidden zone')
        return self

class Goal(BaseModel):
    x:float=Field(ge=-1e6,le=1e6)
    y:float=Field(ge=-1e6,le=1e6)

class Contract(BaseModel):
    schema_id: str='veap.contract/1'
    name: str=Field(min_length=2,max_length=100)
    frame: str=Field('map',min_length=1,max_length=80)
    goal: Goal
    goal_tolerance_m:float=Field(.45,gt=0,le=100)
    max_speed_m_s:float=Field(1.2,gt=0,le=100)
    max_gap_s:float=Field(.4,gt=0,le=100)
    forbidden_zones:list[Zone]=Field(default_factory=list,max_length=30)
    require_actions:bool=False
    calibration: str=Field('UNVALIDATED_EXAMPLE',min_length=3,max_length=100)
    @model_validator(mode='after')
    def schema(self):
        if self.schema_id!='veap.contract/1':raise ValueError('unsupported contract schema')
        return self

def digest(contract):return hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class Registry:
    def __init__(self,store):
        self.store=store
        with store.connect() as con:
            con.execute('CREATE TABLE IF NOT EXISTS veap_contracts(id TEXT PRIMARY KEY, body TEXT NOT NULL, sha256 TEXT NOT NULL)')
    def add(self,c:Contract):
        body=c.model_dump(mode='json');cid=digest(body)
        with self.store.connect() as con:
            con.execute('INSERT OR IGNORE INTO veap_contracts VALUES(?,?,?)',(cid,json.dumps(body,sort_keys=True),cid))
        return {'id':cid,'sha256':cid,'contract':body}
    def get(self,cid):
        with self.store.connect() as con:
            row=con.execute('SELECT body FROM veap_contracts WHERE id=?',(cid,)).fetchone()
        if not row:raise KeyError(cid)
        return json.loads(row[0])
    def list(self):
        with self.store.connect() as con:
            rows=con.execute('SELECT id,body FROM veap_contracts ORDER BY rowid DESC LIMIT 200').fetchall()
        return [{'id':cid,'contract':json.loads(body)} for cid,body in rows]
    def evaluate(self,cid,asset_id):
        c=self.get(cid);asset=self.store.asset(asset_id)
        rows=self.store.trace(asset_id)
        root=Path(__file__).resolve().parent.parent
        script=root/'external_monitor'/'contract_monitor.py'
        # The monitor runs as a separate Python interpreter and does not import VEAP.
        with tempfile.TemporaryDirectory(prefix='veap-monitor-') as td:
            con=Path(td)/'contract.json';src=Path(td)/'trace.jsonl'
            con.write_text(json.dumps(c),encoding='utf-8')
            with src.open('w',encoding='utf-8') as f:
                for row in rows:f.write(json.dumps(row,allow_nan=False)+'\n')
            cp=subprocess.run([sys.executable,str(script),'--contract',str(con),'--trace',str(src)],
                              text=True,capture_output=True,timeout=20,check=False)
            if cp.returncode:raise RuntimeError('external monitor failed: '+cp.stderr[-400:])
            result=json.loads(cp.stdout)
        result.update(contract_id=cid,contract_sha256=cid,source_asset_id=asset_id,
                      source_sha256=asset['sha256'],calibration_declaration=c['calibration'],
                      validation_level='RECORDED_TRACE_CHECK_NOT_PHYSICAL_VALIDATION')
        return result
