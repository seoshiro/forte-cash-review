"""Expiring, revocable jury access to the explicitly incomplete prototype."""
from pathlib import Path
import math,re,secrets,time
from starlette.responses import JSONResponse,FileResponse
from cashreview.research_delivery import ResearchOrigin
from cashreview.partial_contract import PartialV1Bridge


def validate_session(record,now=None):
    now=time.time() if now is None else now
    required={'purpose','jury','operator','other_owner','issued_unix','expires_unix'}
    if set(record)!=required or record['purpose']!='jury-experimental-prototype':raise ValueError('Wrong session purpose')
    issued=record['issued_unix'];expires=record['expires_unix']
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in [issued,expires]):raise ValueError('Finite session times required')
    if not issued<=now<expires or not 0<expires-issued<=24*3600:raise ValueError('Bounded active session required')
    values=[record[k] for k in ['jury','operator','other_owner']]
    if any(not isinstance(x,str) or not re.fullmatch('[A-Za-z0-9_-]{40,128}',x) for x in values) or len(set(values))!=3:raise ValueError('Distinct strong keys required')
    return record


class FinalOrigin:
    def __init__(self,app,record,directory,clock=time.time):
        self.record=validate_session(record,clock());self.directory=Path(directory);self.clock=clock
        self.app=ResearchOrigin(PartialV1Bridge(app,True),[record[k] for k in ['jury','operator','other_owner']],record['expires_unix'],clock,partial_v1=True)
    async def __call__(self,scope,receive,send):
        if scope['type']=='http':
            path=scope['path'];expired=self.clock()>=self.record['expires_unix'];revoked=(self.directory/'revoke-jury.request').exists()
            if expired or (self.directory/'revoke-all.request').exists():
                return await JSONResponse({'detail':'Prototype access session inactive'},503,headers={'Cache-Control':'no-store'})(scope,receive,send)
            if path=='/healthz' and scope['method']=='GET':
                return await JSONResponse({'status':'ok','mode':'xclip_experimental','prototype':True,'partial_v1_enabled':True,
                    'semantic_contract_complete':False,'release_eligible':False,'jury_key_revoked':revoked,
                    'expires_utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(self.record['expires_unix']))},headers={'Cache-Control':'no-store'})(scope,receive,send)
            if path in {'/','/static/style.css'} and scope['method']=='GET':
                filename='final.html' if path=='/' else 'style.css'
                return await FileResponse(Path(__file__).resolve().parents[1]/'static'/filename,headers={'Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
                    'Content-Security-Policy':"default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"})(scope,receive,send)
            if revoked and path.startswith('/api/'):
                values=[v for k,v in scope['headers'] if k.lower()==b'x-api-key']
                if any(secrets.compare_digest(v,self.record['jury'].encode('ascii')) for v in values):
                    return await JSONResponse({'detail':'API key revoked'},401,headers={'Cache-Control':'no-store'})(scope,receive,send)
        return await self.app(scope,receive,send)
