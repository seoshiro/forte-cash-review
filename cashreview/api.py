from __future__ import annotations
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio, hashlib, secrets, os, json, sys, time, shutil, re
from .schemas import Done

ROOT=Path(__file__).resolve().parents[1]


def create_app():
    private=Path(os.environ.get("CASH_PRIVATE",ROOT/".private")).resolve()
    jobs=private/"jobs"; jobs.mkdir(parents=True,exist_ok=True)
    keys=[x for x in os.environ.get("CASH_API_KEY","").split(",") if x]
    if not keys: raise RuntimeError("Set CASH_API_KEY locally before starting")
    budget=float(os.environ.get('CASH_JOB_BUDGET_SEC','295'))
    if not 0<budget<=295:raise RuntimeError('Job budget must be within 295 seconds')
    lock=asyncio.Lock(); active={}; tasks=set()

    def safe_remove(folder):
        target=folder.resolve()
        if target.parent!=jobs.resolve() or not re.fullmatch(r'[0-9a-f]{32}',target.name): raise RuntimeError('Unsafe cleanup target')
        shutil.rmtree(target)

    async def auth(x_api_key:str|None=Header(default=None)):
        if x_api_key is None or not any(secrets.compare_digest(x_api_key,k) for k in keys): raise HTTPException(401,"API key required")
        return hashlib.sha256(x_api_key.encode()).hexdigest()

    def folder_for(job_id,owner):
        if not re.fullmatch(r"[0-9a-f]{32}",job_id): raise HTTPException(404,"Unknown job")
        folder=jobs/job_id
        try: meta=json.loads((folder/"meta.json").read_text())
        except (FileNotFoundError,json.JSONDecodeError): raise HTTPException(404,"Unknown job")
        if not secrets.compare_digest(owner,meta["owner"]): raise HTTPException(404,"Unknown job")
        return folder,meta

    async def run_job(folder,created):
        proc=None
        try:
            remaining=budget-(time.time()-created)
            if remaining<=0: raise TimeoutError()
            child_env=os.environ.copy()
            child_env.update(HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_TELEMETRY="1")
            # No user filename, labels, dataset directory or owner key passed as model input.
            child_env.pop("CASH_API_KEY",None)
            for k in ['HF_TOKEN','HUGGING_FACE_HUB_TOKEN','OPENAI_API_KEY','ANTHROPIC_API_KEY']: child_env.pop(k,None)
            proc=await asyncio.create_subprocess_exec(sys.executable,"-m","cashreview.worker",str(folder),cwd=str(ROOT),env=child_env,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            active[folder.name]=proc
            await asyncio.wait_for(proc.wait(),timeout=remaining)
            if proc.returncode or not (folder/"result.json").exists(): (folder/"failed").touch()
        except (TimeoutError,asyncio.TimeoutError,asyncio.CancelledError):
            if proc and proc.returncode is None: proc.kill(); await proc.wait()
            (folder/"failed").touch()
        except Exception:
            (folder/"failed").touch()
        finally:
            active.pop(folder.name,None)
            lock.release()

    async def cleanup():
        while True:
            for folder in jobs.iterdir():
                if folder.is_dir() and folder.name not in active:
                    try:
                        age=time.time()-json.loads((folder/"meta.json").read_text())["created"]
                        if age>3600: safe_remove(folder)
                    except (OSError,ValueError): pass
            await asyncio.sleep(30)

    @asynccontextmanager
    async def lifespan(app):
        # Interrupted jobs become failed; never reinterpret a crash as no_violation.
        for folder in jobs.iterdir():
            if folder.is_dir() and not (folder/"result.json").exists(): (folder/"failed").touch()
        cleaner=asyncio.create_task(cleanup())
        yield
        cleaner.cancel()
        for t in list(tasks): t.cancel()
        if tasks: await asyncio.gather(*tasks,return_exceptions=True)

    app=FastAPI(title="Cash Review Local",version="0.1.0",lifespan=lifespan,docs_url=None,redoc_url=None)

    @app.middleware("http")
    async def headers(request:Request,call_next):
        reserved=False
        request.state.admitted_at=time.time()
        request.state.capacity_transferred=False
        if request.url.path.startswith('/api/'):
            key=request.headers.get('x-api-key','')
            if not key or not any(secrets.compare_digest(key,k) for k in keys): return JSONResponse({'detail':'API key required'},status_code=401)
        # Multipart parser may spool. Bound the whole body before it reaches it.
        if request.method=="POST":
            try: length=int(request.headers.get('content-length','0'))
            except ValueError: return JSONResponse({'detail':'Invalid content length'},status_code=400)
            if length>129*1024*1024: return JSONResponse({"detail":"Upload too large"},status_code=413)
            size=0; receive=request._receive
            async def limited_receive():
                nonlocal size
                message=await receive(); size+=len(message.get("body",b""))
                if size>129*1024*1024: raise HTTPException(413,"Upload too large")
                return message
            request._receive=limited_receive
        if request.method=='POST' and request.url.path=='/api/v1/analyze':
            if lock.locked():return JSONResponse({'detail':'Processing capacity busy; retry shortly'},status_code=429,headers={'Retry-After':'15'})
            await lock.acquire();reserved=True
        try:
            response=await call_next(request)
        finally:
            if reserved and not request.state.capacity_transferred:lock.release()
        response.headers.update({"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","Content-Security-Policy":"default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"})
        return response

    @app.post("/api/v1/analyze",dependencies=[])
    async def analyze(request:Request,file:UploadFile=File(...),owner:str=Depends(auth)):
        if Path(file.filename or "").suffix.lower()!=".mov": raise HTTPException(415,"Use MOV video")
        created=request.state.admitted_at; job_id=secrets.token_hex(16); folder=jobs/job_id; folder.mkdir()
        try:
            total=0
            with (folder/"input.mov").open("wb") as out:
                while chunk:=await file.read(1024*1024):
                    total+=len(chunk)
                    if total>128*1024*1024: raise HTTPException(413,"Upload too large")
                    out.write(chunk)
            if not total: raise HTTPException(400,"Empty upload")
            (folder/"meta.json").write_text(json.dumps({"owner":owner,"created":created}),encoding="ascii")
            t=asyncio.create_task(run_job(folder,created)); tasks.add(t); t.add_done_callback(tasks.discard)
            request.state.capacity_transferred=True
            return {"job_id":job_id}
        except BaseException:
            safe_remove(folder); raise
        finally: await file.close()

    @app.get("/api/v1/jobs/{job_id}")
    async def status(job_id:str,owner:str=Depends(auth)):
        folder,meta=folder_for(job_id,owner)
        # Publish done only after worker exits and capacity is released.
        if job_id in active: return {"job_id":job_id,"status":"processing"}
        if (folder/"failed").exists(): return {"job_id":job_id,"status":"failed"}
        if (folder/"result.json").exists():
            return Done.model_validate_json((folder/"result.json").read_text(encoding="utf-8")).model_dump()
        if time.time()-meta["created"]>300: return {"job_id":job_id,"status":"failed"}
        return {"job_id":job_id,"status":"processing"}

    @app.get("/api/ui/jobs/{job_id}/detail")
    async def detail(job_id:str,owner:str=Depends(auth)):
        folder,_=folder_for(job_id,owner)
        if not (folder/"result.json").exists(): raise HTTPException(409,"Job not complete")
        try:return json.loads((folder/"detail.json").read_text(encoding="utf-8"))
        except FileNotFoundError:raise HTTPException(404,"No detail")

    @app.get("/healthz")
    async def health(): return {"status":"ok","mode":os.environ.get("CASH_MODE","model")}

    @app.get("/")
    async def index(): return FileResponse(ROOT/"static/index.html")
    app.mount("/static",StaticFiles(directory=ROOT/"static"),name="static")
    return app
