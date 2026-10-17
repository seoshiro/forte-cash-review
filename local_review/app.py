from pathlib import Path
from datetime import datetime,timezone
from typing import Literal
import json,hmac,hashlib
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import FileResponse,HTMLResponse,JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from filelock import FileLock
from pydantic import BaseModel,ConfigDict,Field
ROOT=Path(__file__).resolve().parents[1]

class Annotation(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    label_matches:Literal['yes','no','unclear']
    rule_or_type:str=Field(min_length=1,max_length=500)
    visibility:Literal['sufficient','insufficient','unclear']
    comment:str=Field(default='',max_length=3000)
    reviewed_time_sec:float|None=Field(default=None,ge=0)

def create_review_app(rows,private,token,registration_sha256,synthetic=False):
    if len(rows)!=8 or any(r['split']!='train' for r in rows):raise ValueError('Exactly eight frozen TRAIN sources required')
    private=Path(private);private.mkdir(parents=True,exist_ok=True)
    data_path=private/'annotations.json';lock=FileLock(str(private/'annotations.lock'))
    mode='synthetic_review_test' if synthetic else 'private_train_review'
    instance=hashlib.sha256(token.encode('ascii')).hexdigest()[:16]
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost']+(['testserver'] if synthetic else []))
    def equal(value):return isinstance(value,str) and hmac.compare_digest(value.encode('utf-8'),token.encode('ascii'))
    def authorized(request):
        if not equal(request.cookies.get('train_review_session')):raise HTTPException(403,'Откройте приватный локальный ярлык формы.')
    def load():
        if not data_path.exists():return {'schema_version':1,'registration_sha256':registration_sha256,'annotations':{}}
        data=json.loads(data_path.read_text(encoding='utf-8'))
        if data.get('registration_sha256')!=registration_sha256:raise RuntimeError('Annotation selection mismatch; existing data preserved')
        return data
    def progress(data):
        count=len(data['annotations'])
        report={'selected_train_cases':8,'saved_cases':count,'remaining_cases':8-count,'manual_proposals_unverified':True,
                'automatic_results_modified':False,'official_labels_modified':False,'holdout_opened':False}
        (private/'progress-safe-summary.json').write_text(json.dumps(report,indent=2))
        return report
    with lock:progress(load())
    @app.middleware('http')
    async def guard(request:Request,call_next):
        if request.method=='POST':
            if request.headers.get('origin')!=str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Local same-origin form required'},status_code=403)
            try:length=int(request.headers.get('content-length','0'))
            except ValueError:length=0
            if not 0<length<=16384:return JSONResponse({'detail':'Bounded JSON body required'},status_code=413)
        response=await call_next(request)
        response.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
          'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
          'Permissions-Policy':'camera=(), microphone=(), geolocation=()'})
        return response
    @app.get('/healthz')
    def health():return {'review_app':'train_manual_v1','mode':mode,'selected_cases':8,'instance':instance,'model_inference':False}
    @app.get('/')
    def index(request:Request):
        bootstrap=equal(request.query_params.get('token'))
        if not bootstrap:authorized(request)
        response=FileResponse(ROOT/'review_ui/index.html',media_type='text/html')
        if bootstrap:response.set_cookie('train_review_session',token,httponly=True,samesite='strict',secure=False)
        return response
    @app.get('/assets/{name}')
    def assets(name:str,request:Request):
        authorized(request)
        if name not in ['app.js','style.css']:raise HTTPException(404)
        return FileResponse(ROOT/'review_ui'/name)
    @app.get('/api/items')
    def items(request:Request):
        authorized(request)
        with lock:data=load();summary=progress(data)
        return {'items':[{'case_id':i+1,'target':r['target'],'label_sec':r['label_sec'],'duration_sec':r['duration_sec'],
                         'annotation':data['annotations'].get(str(i+1),{}).get('answers')} for i,r in enumerate(rows)],'progress':summary}
    @app.get('/media/{case_id}')
    def media(case_id:int,request:Request):
        authorized(request)
        if not 1<=case_id<=len(rows):raise HTTPException(404)
        return FileResponse(Path(rows[case_id-1]['path']),media_type='video/quicktime',filename='local-train.mov',content_disposition_type='inline')
    @app.post('/api/annotations/{case_id}')
    def save(case_id:int,annotation:Annotation,request:Request):
        authorized(request)
        if not 1<=case_id<=len(rows):raise HTTPException(404)
        row=rows[case_id-1]
        if annotation.reviewed_time_sec is not None and annotation.reviewed_time_sec>row['duration_sec']+.001:raise HTTPException(422,'Time outside local video')
        if not annotation.rule_or_type.strip():raise HTTPException(422,'Укажите тип/правило либо «неясно».')
        record={'source_sha256':row['sha256'],'official_target':row['target'],'official_label_sec':row['label_sec'],
                'answers':annotation.model_dump(),'saved_utc':datetime.now(timezone.utc).isoformat(),
                'status':'human_proposal_unverified','training_eligible':False}
        with lock:
            data=load();data['annotations'][str(case_id)]=record
            temp=private/'annotations.tmp';temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(data_path)
            with (private/'revisions.private.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'case_id':case_id,**record},ensure_ascii=False)+'\n')
            summary=progress(data)
        return {'saved':True,'case_id':case_id,'progress':summary}
    return app
