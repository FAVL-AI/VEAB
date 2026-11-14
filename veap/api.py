"""Local control plane. Network exposure requires external review and stronger IAM."""
from __future__ import annotations
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .sim import run_episode
from .spec import list_scenarios, load_scenario
from .store import Store
from .verifier import verify_bundle

ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = ROOT / "web"
DATA_ROOT = Path(os.getenv("VEAP_DATA_DIR",str(ROOT / "artifacts")))
store = Store(DATA_ROOT)
executor = ThreadPoolExecutor(max_workers=2,thread_name_prefix="veap-benchmark")
app = FastAPI(title="VEAP Evidence and Evaluation API",version="0.1.0",docs_url="/api/docs",redoc_url=None)


@app.middleware("http")
async def security(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        token = os.getenv("VEAP_ADMIN_TOKEN")
        if token:
            import hmac
            supplied = request.headers.get("authorization","")
            if not hmac.compare_digest(supplied,"Bearer " + token):
                return Response(status_code=401,content='{"detail":"Authorization required"}',media_type="application/json")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    response.headers["Cache-Control"] = "no-store"
    return response


class RunRequest(BaseModel):
    scenario_id: str = Field(pattern="^[a-z0-9-]+$", max_length=64)
    policy: Literal["greedy","route"] = "route"
    shield: bool = True
    seed: int = Field(default=17,ge=0,le=2**32-1)


def execute(run_id: str, req: RunRequest):
    start = time.perf_counter()
    store.set_status(run_id,"running")
    try:
        scenario = load_scenario(req.scenario_id)
        key = os.getenv("VEAP_ATTESTATION_KEY")
        bundle = run_episode(scenario,req.policy,req.seed,req.shield,
                             lambda record:store.append_live(run_id,record),key)
        report = verify_bundle(bundle,key)
        store.finish(run_id,bundle,report,round((time.perf_counter()-start)*1000,2))
    except Exception as exc:
        # Error text is shown only in local dashboard; no Python stack exposed to client.
        store.set_status(run_id,"failed",error=f"{type(exc).__name__}: {str(exc)[:200]}")


@app.get("/api/health")
def health():
    return {"status":"ok","version":"0.1.0","mode":"local simulation only",
            "authentication":bool(os.getenv("VEAP_ADMIN_TOKEN"))}


@app.get("/api/scenarios")
def scenarios():
    return [s.model_dump(mode="json") for s in list_scenarios()]


@app.post("/api/runs",status_code=202)
def start_run(req: RunRequest):
    try:
        load_scenario(req.scenario_id)
    except (FileNotFoundError,ValueError):
        raise HTTPException(status_code=404,detail="Unknown scenario")
    # Prevent unbounded job queue / accidental expensive fan-out.
    active = sum(1 for r in store.recent(200) if r["status"] in ("running","queued"))
    if active >= 4:
        raise HTTPException(status_code=429,detail="Queue capacity reached")
    run_id = store.create(req.scenario_id,req.policy,req.seed,req.shield)
    executor.submit(execute,run_id,req)
    return {"run_id":run_id,"status":"queued"}


@app.get("/api/runs")
def list_runs():
    return store.recent()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    result = store.get(run_id)
    if not result:
        raise HTTPException(status_code=404,detail="Unknown run")
    return result


@app.get("/api/runs/{run_id}/bundle")
def download_bundle(run_id: str):
    try:
        path = store.bundle_path(run_id)
    except ValueError:
        raise HTTPException(status_code=400,detail="Invalid ID")
    if not path.exists():
        raise HTTPException(status_code=404,detail="Evidence bundle not found")
    return FileResponse(path,filename=f"veap-evidence-{run_id[:8]}.json",media_type="application/json")


@app.get("/")
def index():
    return FileResponse(WEB_ROOT / "index.html")


app.mount("/static",StaticFiles(directory=WEB_ROOT),name="static")
