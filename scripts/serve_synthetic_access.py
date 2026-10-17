"""Isolated synthetic-only origin. Secret values never appear on stdout/argv."""
from pathlib import Path
import sys,os,json,argparse,hashlib,re,secrets
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def create_origin(directory,session,test_delay=0):
    from scripts.synthetic import generate
    from cashreview.local_secrets import load
    from cashreview.api import create_app
    from starlette.responses import JSONResponse
    directory=Path(directory).resolve();keys=load(directory/'credentials.dpapi')
    if keys['purpose']!='synthetic-infrastructure-only':raise ValueError('Wrong secret purpose')
    media=directory/'fixtures';media.mkdir(exist_ok=True)
    files=[generate(media/'safe.mov'),generate(media/'positive.mov',positive=True)]
    os.environ.update(CASH_MODE='synthetic_test',CASH_ENGINE='baseline',CASH_PRIVATE=str(directory/'service'),
        CASH_API_KEY=keys['primary']+','+keys['other_owner'],CASH_JOB_BUDGET_SEC='45',
        CASH_TEST_DELAY_SEC=str(min(10,max(0,float(test_delay)))),
        CASH_TEST_HASHES=','.join(hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in files),
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
    app=create_app()
    allowed_static={'/','/static/app.js','/static/review.js','/static/review.css','/static/style.css','/static/index.html'}
    async def origin(scope,receive,send):
        if scope['type']!='http':return await app(scope,receive,send)
        path=scope['path'];method=scope['method']
        if path=='/healthz' and method=='GET':return await JSONResponse({'mode':'synthetic_test','purpose':'infrastructure_only','session':session},headers={'Cache-Control':'no-store'})(scope,receive,send)
        if path.startswith('/api/'):
            supplied=[value for key,value in scope['headers'] if key.lower()==b'x-api-key']
            valid=len(supplied)==1 and any(secrets.compare_digest(supplied[0],keys[k].encode('ascii')) for k in ['primary','other_owner'])
            if not valid:return await JSONResponse({'detail':'API key required'},status_code=401,headers={'Cache-Control':'no-store'})(scope,receive,send)
        allowed=(method=='GET' and path in allowed_static) or (method=='POST' and path=='/api/v1/analyze') or (method=='GET' and bool(re.fullmatch(r'/api/v1/jobs/[0-9a-f]{32}',path)))
        # UI's own authenticated result/review routes remain synthetic and isolated.
        allowed=allowed or (method=='GET' and bool(re.fullmatch(r'/api/ui/jobs/[0-9a-f]{32}/(?:detail|reviews)',path)))
        allowed=allowed or (method=='PUT' and bool(re.fullmatch(r'/api/ui/jobs/[0-9a-f]{32}/reviews/[0-9]+',path)))
        if not allowed:return await JSONResponse({'detail':'Not found'},status_code=404,headers={'Cache-Control':'no-store'})(scope,receive,send)
        return await app(scope,receive,send)
    return origin


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--session',required=True);p.add_argument('--test-delay-sec',type=float,default=0);a=p.parse_args()
    try:
        import uvicorn
        uvicorn.run(create_origin(a.directory,a.session,a.test_delay_sec),host='127.0.0.1',port=a.port,access_log=False,log_level='critical',limit_concurrency=16)
    except Exception:raise SystemExit(1)
