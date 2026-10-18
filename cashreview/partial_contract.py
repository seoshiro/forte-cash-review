"""Opt-in structural v1 compatibility for real binary results; semantic limits explicit."""
import json,re
from starlette.responses import JSONResponse,Response
from cashreview.schemas import Done,Violation
from xclip_candidate.experimental import BinaryResearchResult

UNCLASSIFIED_TYPE='unclassified_suspected_event'
DESCRIPTION=('Экспериментальная локальная бинарная модель отметила это временное окно как подозрительное. '
             'Содержание действия не классифицировано; тип нарушения и применимая норма не установлены. '
             'Возможна ошибка модели; требуется просмотр исходного фрагмента человеком. '
             'Результат не является подтверждением правового или дисциплинарного нарушения.')
DISCLOSURE_HEADERS={'X-Experimental-Mode':'unclassified-baseline-v1','X-Semantic-Contract':'incomplete-types-and-rules',
                    'X-Rule-Application':'not-assessed','X-Release-Eligible':'false','Cache-Control':'no-store'}


def transport_result(value):
    native=value if isinstance(value,BinaryResearchResult) else BinaryResearchResult.model_validate(value)
    violations=[]
    if native.binary_decision=='violation':
        violations=[Violation(type=UNCLASSIFIED_TYPE,timecode_sec=native.candidate_timecode_sec,
                              description=DESCRIPTION,evidence_frames=native.candidate_frames)]
    return Done(job_id=native.job_id,verdict=native.binary_decision,violations=violations).model_dump()


class PartialV1Bridge:
    """Keep native result files and model unchanged. Translate only authorized v1 responses."""
    def __init__(self,app,enabled=False):self.app=app;self.enabled=enabled
    async def __call__(self,scope,receive,send):
        path=scope.get('path','');method=scope.get('method','')
        upload=path=='/api/v1/analyze' and method=='POST'
        poll=path.startswith('/api/v1/jobs/') and method=='GET'
        if scope['type']!='http' or not self.enabled or not (upload or poll):return await self.app(scope,receive,send)
        child=dict(scope);child['path']=path.replace('/api/v1/','/api/experimental/xclip/',1);child['raw_path']=child['path'].encode('utf-8')
        status=None;headers=[];body=bytearray();overflow=False
        async def collect(message):
            nonlocal status,headers,overflow
            if message['type']=='http.response.start':status=message['status'];headers=message.get('headers',[])
            elif message['type']=='http.response.body':
                payload=message.get('body',b'')
                if len(body)+len(payload)>8*1024*1024:overflow=True
                elif not overflow:body.extend(payload)
        await self.app(child,receive,collect)
        response_headers={k.decode('latin1'):v.decode('latin1') for k,v in headers if k.lower() not in {b'content-length',b'content-encoding',b'transfer-encoding'}}
        response_headers.update(DISCLOSURE_HEADERS)
        if overflow or status is None:return await JSONResponse({'detail':'Experimental transport response invalid'},502,headers=response_headers)(scope,receive,send)
        if status!=200:return await Response(bytes(body),status_code=status,headers=response_headers)(scope,receive,send)
        try:
            value=json.loads(body)
            if not isinstance(value,dict):raise ValueError('Object response required')
            if upload:
                if set(value)!={'job_id'} or not re.fullmatch('[0-9a-f]{32}',value['job_id']):raise ValueError('Unexpected job response')
            elif value.get('status')=='done':value=transport_result(value)
            elif set(value)!={'job_id','status'} or value['status'] not in ['processing','failed']:raise ValueError('Unexpected status response')
            if poll and value['job_id']!=path.removeprefix('/api/v1/jobs/'):raise ValueError('Job identity mismatch')
        except (ValueError,TypeError,KeyError):
            return await JSONResponse({'detail':'Experimental transport response invalid'},502,headers=response_headers)(scope,receive,send)
        return await JSONResponse(value,status_code=200,headers=response_headers)(scope,receive,send)
