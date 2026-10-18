"""Narrow, expiring research gateway. No credentials are generated here."""
import re,secrets,time
from starlette.responses import JSONResponse

STATIC={'/','/static/research.html','/static/research.js','/static/research.css'}


def validate_credentials(record, now=None):
    now=time.time() if now is None else now
    if set(record)!={'purpose','primary','other_owner','expires_unix'} or record['purpose']!='research-prototype-only':raise ValueError('Research-only credentials required')
    if type(record['expires_unix']) not in (int,float) or not now<record['expires_unix']<=now+8*3600:raise ValueError('Bounded future expiry required')
    for name in ['primary','other_owner']:
        value=record[name]
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}',value) or any(s in value.lower() for s in ['temporary','example','test-only']):raise ValueError('Strong separately provisioned key required')
    if secrets.compare_digest(record['primary'],record['other_owner']):raise ValueError('Distinct owner keys required')
    return record


class ResearchOrigin:
    def __init__(self,app,keys,expires,clock=time.time):
        self.app=app;self.keys=tuple(value.encode('ascii') for value in keys);self.expires=expires;self.clock=clock
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        if self.clock()>=self.expires:return await self.reject(scope,receive,send,503,'Research session expired')
        path=scope['path'];method=scope['method']
        if path=='/healthz' and method=='GET':return await JSONResponse({'status':'ok','mode':'xclip_experimental','release_eligible':False},headers={'Cache-Control':'no-store'})(scope,receive,send)
        if path.startswith('/api/'):
            values=[value for key,value in scope['headers'] if key.lower()==b'x-api-key']
            if len(values)!=1 or not any(secrets.compare_digest(values[0],key) for key in self.keys):return await self.reject(scope,receive,send,401,'API key required')
        allowed=(method=='GET' and path in STATIC) or (method=='POST' and path=='/api/experimental/xclip/analyze')
        allowed=allowed or (method=='GET' and bool(re.fullmatch(r'/api/experimental/xclip/jobs/[0-9a-f]{32}',path)))
        # Existing engine explicitly returns 503 for this contract in research mode.
        allowed=allowed or (method=='POST' and path=='/api/v1/analyze') or (method=='GET' and bool(re.fullmatch(r'/api/v1/jobs/[0-9a-f]{32}',path)))
        if not allowed:return await self.reject(scope,receive,send,404,'Not found')
        return await self.app(scope,receive,send)
    @staticmethod
    async def reject(scope,receive,send,status,detail):
        return await JSONResponse({'detail':detail},status_code=status,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})(scope,receive,send)
