import base64,copy,time
from io import BytesIO
from PIL import Image
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from cashreview.partial_contract import PartialV1Bridge,transport_result,UNCLASSIFIED_TYPE,DESCRIPTION
from cashreview.research_delivery import ResearchOrigin
from cashreview.schemas import Done

JOB='a'*32


def native(positive=True):
    image=Image.new('RGB',(32,24),(22,77,111));buffer=BytesIO();image.save(buffer,'JPEG')
    return {'job_id':JOB,'status':'done','mode':'xclip_experimental','binary_decision':'violation' if positive else 'no_violation',
            'decision_margin':.2 if positive else -.2,'threshold':0.,'event_type_status':'unverified','rule_application_status':'not_assessed',
            'candidate_timecode_sec':1. if positive else None,'candidate_frames':[{'timestamp_sec':1.,'image_base64':base64.b64encode(buffer.getvalue()).decode()}] if positive else [],
            'duration_sec':3.,'elapsed_engine_sec':1.,'release_eligible':False,
            'limitation':'Binary research candidate only; type, physical explanation and legal rule are unverified. No complete multi-event detection claim.'}


@pytest.mark.parametrize('positive',[False,True])
def test_real_fields_preserved_without_semantic_invention(positive):
    value=native(positive);before=copy.deepcopy(value);result=Done.model_validate(transport_result(value))
    assert value==before and result.verdict==value['binary_decision']
    assert set(result.model_dump())=={'job_id','status','verdict','violations'}
    if positive:
        event=result.violations[0];assert event.type==UNCLASSIFIED_TYPE and event.description==DESCRIPTION
        assert event.timecode_sec==value['candidate_timecode_sec'] and event.evidence_frames[0].model_dump()==value['candidate_frames'][0]
        assert 'норма не установлены' in event.description
    else:assert result.violations==[]


def test_bridge_is_opt_in_and_preserves_processing_failure_and_errors():
    async def native_upload(request):return JSONResponse({'job_id':JOB})
    async def native_poll(request):
        name=request.path_params['job'];value={'job_id':name,'status':'failed' if name=='b'*32 else 'processing'}
        return JSONResponse(value)
    async def blocked(request):return JSONResponse({'detail':'Experimental mode disabled'},503)
    app=Starlette(routes=[Route('/api/experimental/xclip/analyze',native_upload,methods=['POST']),Route('/api/experimental/xclip/jobs/{job}',native_poll),Route('/api/v1/analyze',blocked,methods=['POST'])])
    assert TestClient(PartialV1Bridge(app)).post('/api/v1/analyze').status_code==503
    wrapped=ResearchOrigin(PartialV1Bridge(app,True),['test-primary'],time.time()+60,partial_v1=True)
    with TestClient(wrapped) as client:
        assert client.post('/api/v1/analyze').status_code==401
        headers={'X-API-Key':'test-primary'}
        response=client.post('/api/v1/analyze',headers=headers);assert response.status_code==200 and response.json()=={'job_id':JOB}
        assert response.headers['X-Experimental-Mode']=='unclassified-baseline-v1'
        assert client.get('/api/v1/jobs/'+JOB,headers=headers).json()=={'job_id':JOB,'status':'processing'}
        assert client.get('/api/v1/jobs/'+'b'*32,headers=headers).json()=={'job_id':'b'*32,'status':'failed'}
        assert client.get('/healthz').json()['semantic_contract_complete'] is False


@pytest.mark.parametrize('payload',[{'job_id':JOB,'status':'done','binary_decision':'no_violation'},[]])
def test_malformed_result_is_technical_error_never_negative(payload):
    async def malformed(request):return JSONResponse(payload)
    app=Starlette(routes=[Route('/api/experimental/xclip/jobs/{job}',malformed)])
    response=TestClient(PartialV1Bridge(app,True)).get('/api/v1/jobs/'+JOB)
    assert response.status_code==502 and 'verdict' not in response.json()


def test_done_positive_get_has_exact_required_schema():
    value=native(True)
    async def reply(request):return JSONResponse(value)
    app=Starlette(routes=[Route('/api/experimental/xclip/jobs/{job}',reply)])
    response=TestClient(PartialV1Bridge(app,True)).get('/api/v1/jobs/'+JOB)
    parsed=Done.model_validate(response.json());assert parsed.verdict=='violation' and parsed.violations[0].type==UNCLASSIFIED_TYPE
