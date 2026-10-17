"""One bounded actual-model API smoke using newly generated rectangles only."""
from pathlib import Path
import sys,os,time,json,base64,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import supervise,await_start_gate,atomic_json,ControlSummary,write_progress


def worker():
    directory,deadline=await_start_gate()
    from scripts.synthetic import generate
    from fastapi.testclient import TestClient
    from cashreview.api import create_app
    from cashreview.video import sample
    from xclip_candidate.experimental import BinaryResearchResult
    from io import BytesIO
    media=generate(directory/'generated-rectangles.mov',positive=True)
    key='temporary-synthetic-xclip-smoke-only'
    os.environ.update(CASH_MODE='xclip_experimental',CASH_ENGINE='xclip_experimental',CASH_PRIVATE=str(directory/'service'),
        CASH_API_KEY=key,CASH_JOB_BUDGET_SEC='75')
    completed=0;passed=0;latencies=[];results=[];evidence_checked=0;started=time.monotonic()
    try:
        with TestClient(create_app()) as client:
            assert client.get('/healthz').json()['mode']=='xclip_experimental'
            for name in ['artificial-a.mov','renamed-artificial-b.mov']:
                tick=time.monotonic()
                with media.open('rb') as stream:
                    response=client.post('/api/experimental/xclip/analyze',headers={'X-API-Key':key},files={'file':(name,stream,'video/quicktime')})
                assert response.status_code==200;job=response.json()['job_id']
                while True:
                    if time.monotonic()>=deadline:raise TimeoutError('Synthetic smoke budget')
                    response=client.get('/api/experimental/xclip/jobs/'+job,headers={'X-API-Key':key})
                    assert response.status_code==200;value=response.json()
                    if value['status']!='processing':break
                    time.sleep(.1)
                assert value['status']=='done'
                result=BinaryResearchResult.model_validate(value)
                for frame in result.candidate_frames:
                    actual=sample(media,[frame.timestamp_sec],max_side=768)
                    assert len(actual)==1 and abs(actual[0].sec-frame.timestamp_sec)<1e-6
                    buffer=BytesIO();actual[0].image.save(buffer,'JPEG',quality=90)
                    assert buffer.getvalue()==base64.b64decode(frame.image_base64,validate=True)
                    evidence_checked+=1
                assert client.get('/api/experimental/xclip/jobs/'+job).status_code==401
                assert client.get('/api/v1/jobs/'+job,headers={'X-API-Key':key}).status_code==503
                results.append(result);latencies.append(time.monotonic()-tick);completed+=1;passed+=1
                write_progress(directory,'fixture',completed,passed,2)
            a,b=results
            assert a.binary_decision==b.binary_decision and abs(a.decision_margin-b.decision_margin)<1e-6
            assert a.candidate_timecode_sec==b.candidate_timecode_sec
            assert [f.model_dump() for f in a.candidate_frames]==[f.model_dump() for f in b.candidate_frames]
        atomic_json(directory/'integration-safe-summary.json',{'status':'passed','split':'synthetic','generated_media_only':True,
            'actual_xclip_encoder_run':True,'api_uploads_completed':completed,'filename_invariance_passed':True,
            'strict_research_schema_passed':True,'auth_and_official_contract_block_passed':True,
            'actual_source_jpeg_checks':evidence_checked,'jpeg_check_conditional_on_binary_positive':True,
            'upload_to_result_sec':latencies,'elapsed_sec':time.monotonic()-started,
            'bank_media_opened':False,'detection_quality_test':False,'public_access_test':False,
            'physical_network_disconnection_test':False,'inference_worker_socket_guard_enabled':True,
            'per_input_predictions_emitted':False,'permanent_key_created':False})
        report=ControlSummary(status='completed',completed_cases=completed,passed_cases=passed,total_cases=2)
    except Exception as error:
        atomic_json(directory/'integration-safe-summary.json',{'status':'failed','split':'synthetic','completed_uploads':completed,
            'technical_error_type':type(error).__name__,'raw_response_or_exception_emitted':False,'bank_media_opened':False})
        report=ControlSummary(status='failed',completed_cases=completed,passed_cases=passed,total_cases=2,failure='exception')
    atomic_json(directory/'worker-safe-summary.json',report.model_dump())
    if report.status!='completed':raise SystemExit(1)


if __name__=='__main__':
    if '--worker' in sys.argv:worker()
    else:
        report=supervise([sys.executable,str(Path(__file__).resolve()),'--worker'],ROOT/'.private/xclip-api-synthetic-smoke',180,2,str(ROOT))
        print(json.dumps(report),flush=True)
        if not report['quality_gate_passed']:raise SystemExit(1)
