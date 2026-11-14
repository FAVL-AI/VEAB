"""Controlled local experiment and conversion jobs. Not a multi-tenant worker system.

Only named, bundled scripts may execute. No shell; no arbitrary file paths from callers.
Status is persisted and orphaned running jobs are marked INTERRUPTED on restart.
"""
from __future__ import annotations
import json, os, shutil, sqlite3, subprocess, sys, threading, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from .world_export import export_reference_world
from .mcap_decode import decode_mcap

SCRIPTS=Path(__file__).parent/'workers'
ALLOWED={'mujoco_fall':'mujoco_fall.py','isaac_fall':'isaac_fall.py',
         'gazebo_fall':'gazebo_fall.py','lerobot_dataset':'lerobot_dataset.py'}
PYENV={'mujoco_fall':'VEAP_MUJOCO_PYTHON','isaac_fall':'VEAP_ISAAC_PYTHON',
       'gazebo_fall':'VEAP_GAZEBO_PYTHON','lerobot_dataset':'VEAP_LEROBOT_PYTHON'}

def utc():return datetime.now(timezone.utc).isoformat(timespec='seconds')
class Jobs:
    def __init__(self,store):
        self.store=store;self.root=store.root/'jobs';self.root.mkdir(exist_ok=True)
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='veap-engine')
        self.lock=threading.RLock()
        with store.connect() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS veap_jobs (id TEXT PRIMARY KEY, kind TEXT, status TEXT,
                 created TEXT, updated TEXT, source_id TEXT, asset_id TEXT, result TEXT, error TEXT)''')
            con.execute("UPDATE veap_jobs SET status='INTERRUPTED',updated=? WHERE status IN ('RUNNING','QUEUED')",(utc(),))
    def create(self,kind,source_id=None):
        if kind not in (*ALLOWED,'mcap_decode','scene_export'):raise ValueError('unsupported job')
        if kind in ('mcap_decode','lerobot_dataset'):
            if not source_id:raise ValueError('source_id required')
            a=self.store.asset(source_id)
            if kind=='mcap_decode' and a['kind']!='MCAP':raise ValueError('MCAP input required')
            if kind=='lerobot_dataset' and a['kind']!='TRAJECTORY':raise ValueError('trajectory input required')
        jid=uuid.uuid4().hex
        with self.store.connect() as con:
            con.execute('INSERT INTO veap_jobs VALUES(?,?,?,?,?,?,?,?,?)',
                        (jid,kind,'QUEUED',utc(),utc(),source_id,None,'{}',''))
        self.pool.submit(self._run,jid,kind,source_id)
        return self.get(jid)
    def _update(self,jid,status,asset_id=None,result=None,error=''):
        with self.store.connect() as con:
            con.execute('UPDATE veap_jobs SET status=?,updated=?,asset_id=?,result=?,error=? WHERE id=?',
                        (status,utc(),asset_id,json.dumps(result or {}),error[:1600],jid))
    def get(self,jid):
        with self.store.connect() as con:
            row=con.execute('SELECT id,kind,status,created,updated,source_id,asset_id,result,error FROM veap_jobs WHERE id=?',(jid,)).fetchone()
        if not row:raise KeyError(jid)
        x=dict(zip(('id','kind','status','created','updated','source_id','asset_id','result','error'),row))
        x['result']=json.loads(x['result']);return x
    def list(self):
        with self.store.connect() as con:
            ids=[r[0] for r in con.execute('SELECT id FROM veap_jobs ORDER BY created DESC LIMIT 40').fetchall()]
        return [self.get(i) for i in ids]
    def _run(self,jid,kind,source):
        self._update(jid,'RUNNING')
        folder=self.root/jid;folder.mkdir(mode=0o700,exist_ok=False)
        try:
            if kind=='scene_export':
                result=export_reference_world(folder)
                self._update(jid,'COMPLETED',result=result);return
            if kind=='mcap_decode':
                a=self.store.asset(source)
                out=folder/'odom_derived.jsonl'
                r=decode_mcap(self.store.blobs/a['blob_name'],out)
                dest=self.store.put('decoded_'+a['name']+'.jsonl',out,
                    origin='DERIVED_MCAP_UNATTESTED',note='Derived from source SHA256='+a['sha256'])
                r['parent_asset_id']=source;r['parent_sha256']=a['sha256']
                self._update(jid,'COMPLETED',asset_id=dest['id'],result=r);return
            envvar=PYENV[kind]
            py=os.environ.get(envvar,'').strip()
            if not py and kind=='lerobot_dataset' and Path('/home/favl/veap-envs/lerobot/bin/python').is_file():
                py='/home/favl/veap-envs/lerobot/bin/python'
            if not py and kind in ('mujoco_fall','gazebo_fall','lerobot_dataset'):
                py=sys.executable
            if not py or not Path(py).is_absolute() or not Path(py).is_file():
                raise RuntimeError('No native runtime configured: '+envvar)
            script=SCRIPTS/ALLOWED[kind];meta=folder/'run.json'
            args=[py,'-u',str(script)]
            if kind=='lerobot_dataset':
                a=self.store.asset(source);data=folder/'lerobot_output'
                args += ['--trace',str(self.store.blobs/a['blob_name']),'--out',str(data),'--meta',str(meta)]
            else:
                data=folder/'trajectory.jsonl'
                args += ['--out',str(data),'--meta',str(meta),'--steps','400','--dt','0.005']
            env=dict(os.environ)
            # Do not inherit from a potentially incompatible Conda / ROS shell.
            for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','CONDA_PREFIX','CONDA_DEFAULT_ENV'):
                env.pop(key,None)
            if kind=='isaac_fall':env['OMNI_KIT_ACCEPT_EULA']='YES'
            cp=subprocess.run(args,capture_output=True,text=True,timeout=240 if kind=='isaac_fall' else 90,
                              check=False,env=env,cwd=str(folder))
            (folder/'process.log').write_text((cp.stdout+'\n'+cp.stderr)[-150_000:],encoding='utf-8')
            if cp.returncode!=0:raise RuntimeError(f'Native worker exited {cp.returncode}; see process.log')
            result=json.loads(meta.read_text(encoding='utf-8'))
            if kind=='lerobot_dataset':
                result.update(source_asset_id=source,local_dataset=str(data),
                    label='Local dataset; not yet benchmark validated')
                self._update(jid,'COMPLETED',result=result);return
            a=self.store.put(kind+'.jsonl',data,origin='NATIVE_SIMULATOR_UNATTESTED',
               note='Engine='+kind+'; see job '+jid+' for simulator metadata')
            self._update(jid,'COMPLETED',asset_id=a['id'],result=result)
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as e:
            self._update(jid,'FAILED',error=str(e))
