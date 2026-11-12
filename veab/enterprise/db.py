"""Tenant-scoped, SQLite-backed evidence registry for a single-node research pilot.

This is deliberately NOT a distributed database, a WORM ledger, or a safety
certification system. All tenant queries require an explicit tenant identifier.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROLES = frozenset({'owner', 'researcher', 'reviewer', 'auditor', 'viewer'})
SCHEMA = 1


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def new_id() -> str:
    return uuid.uuid4().hex


class StudioDB:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        self.path = self.root / 'studio.sqlite3'
        self._init_schema()
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @contextmanager
    def conn(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA busy_timeout=10000')
        try:
            if write:
                c.execute('BEGIN IMMEDIATE')
            yield c
            if write:
                c.commit()
        except Exception:
            if write:
                c.rollback()
            raise
        finally:
            c.close()

    def _init_schema(self):
        with self.conn(write=True) as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS principals (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                oidc_issuer TEXT, oidc_subject TEXT, created_at REAL NOT NULL,
                UNIQUE(oidc_issuer,oidc_subject));
            CREATE TABLE IF NOT EXISTS memberships (
                tenant_id TEXT NOT NULL REFERENCES tenants(id),
                principal_id TEXT NOT NULL REFERENCES principals(id),
                role TEXT NOT NULL CHECK(role IN ('owner','researcher','reviewer','auditor','viewer')),
                PRIMARY KEY(tenant_id,principal_id));
            CREATE TABLE IF NOT EXISTS tokens (
                token_sha256 TEXT PRIMARY KEY, principal_id TEXT NOT NULL REFERENCES principals(id),
                created_at REAL NOT NULL, expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
                name TEXT NOT NULL, description TEXT NOT NULL, created_by TEXT NOT NULL,
                created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_project_tenant ON projects(tenant_id);
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
                project_id TEXT NOT NULL REFERENCES projects(id),
                scenario_id TEXT NOT NULL, policy TEXT NOT NULL, seed INTEGER NOT NULL,
                shield INTEGER NOT NULL, created_by TEXT NOT NULL,
                request_key TEXT, status TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL,
                summary_json TEXT, bundle_sha256 TEXT, error TEXT,
                UNIQUE(tenant_id, project_id, request_key));
            CREATE INDEX IF NOT EXISTS ix_run_project ON runs(tenant_id,project_id,created_at);
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
                project_id TEXT NOT NULL REFERENCES projects(id),
                filename TEXT NOT NULL, format TEXT NOT NULL,
                content_sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                provenance TEXT NOT NULL, created_by TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_evidence_project ON evidence(tenant_id,project_id);
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
                run_id TEXT NOT NULL REFERENCES runs(id),
                reviewer_id TEXT NOT NULL REFERENCES principals(id),
                verdict TEXT NOT NULL CHECK(verdict IN ('accepted','rejected','inconclusive')),
                rationale TEXT NOT NULL, created_at REAL NOT NULL,
                UNIQUE(run_id,reviewer_id));
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL REFERENCES tenants(id),
                actor_id TEXT NOT NULL, action TEXT NOT NULL, object_id TEXT NOT NULL,
                details_json TEXT NOT NULL, created_at REAL NOT NULL,
                prev_sha256 TEXT NOT NULL, event_sha256 TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_audit_tenant ON audit(tenant_id,id);
            ''')
            previous = c.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if previous is None:
                c.execute("INSERT INTO metadata VALUES ('schema_version',?)", (str(SCHEMA),))
            elif int(previous['value']) != SCHEMA:
                raise RuntimeError('Unsupported enterprise schema version; migration required')

    def row(self, query: str, *args) -> dict | None:
        with self.conn() as c:
            r = c.execute(query, args).fetchone()
        return dict(r) if r else None

    def rows(self, query: str, *args) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(query, args).fetchall()]

    def bootstrap(self, org: str, email: str, name: str, role: str = 'owner', *,
                  oidc_issuer: str | None = None, oidc_subject: str | None = None,
                  tenant_id: str | None = None) -> tuple[str, str]:
        if role not in ROLES:
            raise ValueError('Unknown role')
        email=email.strip().lower()
        with self.conn(write=True) as c:
            now = time.time()
            if tenant_id is None:
                tenant_id = new_id()
                c.execute('INSERT INTO tenants VALUES (?,?,?)', (tenant_id, org, now))
            elif not c.execute('SELECT id FROM tenants WHERE id=?', (tenant_id,)).fetchone():
                raise ValueError('Tenant not found')
            existing = c.execute('SELECT id,oidc_issuer,oidc_subject FROM principals WHERE email=?', (email,)).fetchone()
            if existing:
                principal_id = existing['id']
                if oidc_issuer is not None and (existing['oidc_issuer'],existing['oidc_subject']) != (oidc_issuer,oidc_subject):
                    raise ValueError('Email already bound to a different OIDC identity')
            else:
                principal_id = new_id()
                c.execute('INSERT INTO principals VALUES (?,?,?,?,?,?)',
                          (principal_id, email.lower(), name, oidc_issuer, oidc_subject, now))
            c.execute('INSERT INTO memberships VALUES (?,?,?)', (tenant_id, principal_id, role))
            self._audit_tx(c, tenant_id, 'system-bootstrap', 'membership.create', principal_id, {'role': role})
        return tenant_id, principal_id

    def issue_dev_token(self, principal_id: str, *, valid_hours: int = 24) -> str:
        token = 'veab_' + secrets.token_urlsafe(40)
        with self.conn(write=True) as c:
            c.execute('INSERT INTO tokens VALUES (?,?,?,?,0)',
                      (hashlib.sha256(token.encode()).hexdigest(), principal_id, time.time(), time.time()+valid_hours*3600))
        return token

    def principal_for_dev_token(self, token: str) -> dict | None:
        if not token.startswith('veab_') or len(token) > 128:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        return self.row('''SELECT p.id,p.email,p.name FROM tokens t JOIN principals p ON p.id=t.principal_id
                           WHERE t.token_sha256=? AND t.revoked=0 AND t.expires_at>?''', digest, time.time())

    def principal_for_oidc(self, issuer: str, sub: str) -> dict | None:
        return self.row('SELECT id,email,name FROM principals WHERE oidc_issuer=? AND oidc_subject=?', issuer,sub)

    def my_tenants(self, principal_id: str) -> list[dict]:
        return self.rows('''SELECT t.id,t.name,m.role FROM memberships m JOIN tenants t ON t.id=m.tenant_id
                            WHERE m.principal_id=? ORDER BY t.name''', principal_id)

    def member_role(self, tenant_id: str, principal_id: str) -> str | None:
        record = self.row('SELECT role FROM memberships WHERE tenant_id=? AND principal_id=?', tenant_id,principal_id)
        return record['role'] if record else None

    def project(self, tenant: str, project_id: str) -> dict | None:
        return self.row('SELECT * FROM projects WHERE tenant_id=? AND id=?', tenant,project_id)

    def projects(self, tenant: str) -> list[dict]:
        return self.rows('SELECT * FROM projects WHERE tenant_id=? ORDER BY created_at DESC',tenant)

    def create_project(self, tenant: str, actor: str, name: str, description: str) -> dict:
        project_id, now = new_id(), time.time()
        with self.conn(write=True) as c:
            c.execute('INSERT INTO projects VALUES (?,?,?,?,?,?)', (project_id,tenant,name,description,actor,now))
            self._audit_tx(c, tenant,actor,'project.create',project_id,{'name':name})
        return self.project(tenant,project_id)

    def create_run(self, tenant: str, project: str, actor: str, scenario: str,
                   policy: str, seed: int, shield: bool, request_key: str | None = None) -> tuple[dict,bool]:
        rid, now = new_id(), time.time()
        with self.conn(write=True) as c:
            if request_key:
                found = c.execute('SELECT * FROM runs WHERE tenant_id=? AND project_id=? AND request_key=?',
                                  (tenant,project,request_key)).fetchone()
                if found:
                    if (found['scenario_id'],found['policy'],found['seed'],bool(found['shield'])) != (scenario,policy,seed,shield):
                        raise ValueError('Idempotency key reused with different experiment parameters')
                    return dict(found),False
            c.execute('''INSERT INTO runs (id,tenant_id,project_id,scenario_id,policy,seed,shield,created_by,
                         request_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (rid,tenant,project,scenario,policy,seed,int(shield),actor,request_key,'queued',now,now))
            self._audit_tx(c,tenant,actor,'run.queue',rid,{'scenario':scenario,'policy':policy,'seed':seed,'shield':shield})
        return self.run(tenant,rid),True

    def run(self, tenant: str, run_id: str) -> dict | None:
        record = self.row('SELECT * FROM runs WHERE tenant_id=? AND id=?',tenant,run_id)
        if record:
            record['shield']=bool(record['shield'])
            record['summary']=json.loads(record.pop('summary_json')) if record['summary_json'] else None
        return record

    def runs(self, tenant: str, project: str) -> list[dict]:
        return [self.run(tenant,r['id']) for r in self.rows('''SELECT id FROM runs WHERE tenant_id=? AND project_id=?
                                                                   ORDER BY created_at DESC LIMIT 100''',tenant,project)]

    def update_run(self, tenant: str, run_id: str, *, status: str, summary: dict | None = None,
                   sha256: str | None = None, error: str | None = None):
        with self.conn(write=True) as c:
            c.execute('''UPDATE runs SET status=?,summary_json=?,bundle_sha256=?,error=?,updated_at=?
                         WHERE id=? AND tenant_id=?''', (status,canonical(summary) if summary else None,
                            sha256,error,time.time(),run_id,tenant))
            self._audit_tx(c,tenant,'studio-worker','run.'+status,run_id,{'sha256':sha256 or '',
                           'verified':bool(summary.get('verified')) if summary else False})

    def interrupt_orphans(self):
        with self.conn(write=True) as c:
            c.execute("UPDATE runs SET status='interrupted', updated_at=? WHERE status IN ('queued','running')", (time.time(),))

    def record_evidence(self,tenant:str,project:str,actor:str,filename:str,fmt:str,
                        sha256:str,size:int,provenance:str) -> dict:
        eid,now=new_id(),time.time()
        with self.conn(write=True) as c:
            c.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (eid,tenant,project,filename,fmt,sha256,size,provenance,actor,now))
            self._audit_tx(c,tenant,actor,'evidence.upload',eid,{'sha256':sha256,'format':fmt,'bytes':size})
        return self.evidence_one(tenant,eid)

    def evidence_one(self,tenant:str,eid:str) -> dict | None:
        return self.row('SELECT * FROM evidence WHERE tenant_id=? AND id=?',tenant,eid)

    def evidence_list(self,tenant:str,project:str) -> list[dict]:
        return self.rows('''SELECT * FROM evidence WHERE tenant_id=? AND project_id=?
                            ORDER BY created_at DESC LIMIT 100''',tenant,project)

    def review(self,tenant:str,run_id:str,actor:str,verdict:str,rationale:str) -> dict:
        now,rid=time.time(),new_id()
        with self.conn(write=True) as c:
            target=c.execute('SELECT created_by,status FROM runs WHERE tenant_id=? AND id=?', (tenant,run_id)).fetchone()
            if not target or target['status']!='completed':
                raise ValueError('Only completed tenant runs can be reviewed')
            if target['created_by']==actor:
                raise PermissionError('Review must be by someone other than the run creator')
            c.execute('INSERT INTO reviews VALUES (?,?,?,?,?,?,?)',(rid,tenant,run_id,actor,verdict,rationale,now))
            self._audit_tx(c,tenant,actor,'run.review',run_id,{'verdict':verdict,'review_id':rid})
        return self.row('SELECT * FROM reviews WHERE tenant_id=? AND id=?',tenant,rid)

    def reviews(self,tenant:str,run_id:str) -> list[dict]:
        return self.rows('SELECT * FROM reviews WHERE tenant_id=? AND run_id=? ORDER BY created_at DESC',tenant,run_id)

    @staticmethod
    def _audit_tx(c: sqlite3.Connection, tenant:str, actor:str, action:str, object_id:str, details:dict):
        previous=c.execute('SELECT event_sha256 FROM audit WHERE tenant_id=? ORDER BY id DESC LIMIT 1',(tenant,)).fetchone()
        prev=previous['event_sha256'] if previous else '0'*64
        now=time.time()
        envelope={'tenant_id':tenant,'actor_id':actor,'action':action,'object_id':object_id,
                  'details':details,'created_at':now,'prev_sha256':prev}
        digest=hashlib.sha256(canonical(envelope).encode()).hexdigest()
        c.execute('''INSERT INTO audit (tenant_id,actor_id,action,object_id,details_json,created_at,prev_sha256,event_sha256)
                     VALUES (?,?,?,?,?,?,?,?)''', (tenant,actor,action,object_id,canonical(details),now,prev,digest))

    def audit_events(self,tenant:str,limit:int=100) -> list[dict]:
        records=self.rows('SELECT * FROM audit WHERE tenant_id=? ORDER BY id DESC LIMIT ?',tenant,min(max(limit,1),500))
        for r in records:
            r['details']=json.loads(r.pop('details_json'))
        return records

    def audit_verify(self,tenant:str) -> dict:
        rows=self.rows('SELECT * FROM audit WHERE tenant_id=? ORDER BY id',tenant)
        prev='0'*64
        for i,r in enumerate(rows):
            payload={'tenant_id':r['tenant_id'],'actor_id':r['actor_id'],'action':r['action'],
                     'object_id':r['object_id'],'details':json.loads(r['details_json']),
                     'created_at':r['created_at'],'prev_sha256':prev}
            expected=hashlib.sha256(canonical(payload).encode()).hexdigest()
            if not hmac.compare_digest(r['prev_sha256'],prev) or not hmac.compare_digest(r['event_sha256'],expected):
                return {'chain_consistent':False,'events_checked':i,'failed_event_id':r['id'],
                        'authenticity_established':False}
            prev=expected
        return {'chain_consistent':True,'events_checked':len(rows),'chain_root_sha256':prev,
                'authenticity_established':False,
                'caveat':'Local database chain; administrators can rehash without independent anchoring.'}
