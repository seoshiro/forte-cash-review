"""Real frozen baseline via final public API, generated MOV only; aggregates out."""
from pathlib import Path
import base64,hashlib,json,secrets,subprocess,sys,time
from io import BytesIO
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json
from cashreview.technical_diagnostics import safe_exception
OUT=ROOT/'.private/final-runtime-qa'


def main():
    import httpx
    from cashreview.local_secrets import load
    from cashreview.final_delivery import validate_session
    from cashreview.schemas import Done
    from cashreview.video import sample
    from scripts.synthetic import generate
    OUT.mkdir(exist_ok=False);record=validate_session(load(ROOT/'.private/final-access/credentials.dpapi'))
    endpoint=json.loads((ROOT/'.private/final-access/endpoint.json').read_text());assert endpoint['active_expected'];url=endpoint['url']
    media=generate(OUT/'fixtures/safe.mov');digest=hashlib.sha256(media.read_bytes()).hexdigest();headers={'X-API-Key':record['operator']};walls=[];jpeg_checks=0;phase='security'
    def comparable(result):
        value=result.model_dump();value.pop('job_id');return value
    try:
        with httpx.Client(timeout=20,trust_env=False,follow_redirects=False) as client:
            def poll(job):
                until=time.monotonic()+299
                while time.monotonic()<until:
                    response=client.get(url+'/api/v1/jobs/'+job,headers=headers);assert response.status_code==200;value=response.json()
                    if value['status']!='processing':return value
                    time.sleep(.25)
                raise TimeoutError('Final public API deadline')
            def run(filename):
                started=time.monotonic()
                with media.open('rb') as stream:response=client.post(url+'/api/v1/analyze',headers=headers,files={'file':(filename,stream,'video/quicktime')})
                assert response.status_code==200;job=response.json()['job_id'];result=Done.model_validate(poll(job));walls.append(time.monotonic()-started)
                assert walls[-1]<300
                for key in [None,'incorrect',record['jury'],record['other_owner']]:
                    response=client.get(url+'/api/v1/jobs/'+job,headers={} if key is None else {'X-API-Key':key})
                    assert response.status_code==(401 if key in [None,'incorrect'] else 404)
                for path in ['/.private/final-service/jobs/'+job+'/input.mov','/jobs/'+job+'/result.json','/api/v1/jobs/'+job+'/input.mov','/input.mov','/raw']:
                    assert client.get(url+path,headers=headers).status_code==404
                return job,result
            phase='real_baseline_first_generated_upload';job,first=run('generated_original.mov')
            phase='restart_completed_job'
            response=subprocess.run([sys.executable,str(ROOT/'scripts/final_access.py'),'restart-origin'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60)
            assert response.returncode==0 and json.loads(response.stdout)['same_public_url'] is True
            assert json.loads((ROOT/'.private/final-access/endpoint.json').read_text())['url']==url
            restored=Done.model_validate(client.get(url+'/api/v1/jobs/'+job,headers=headers).json());assert restored.model_dump()==first.model_dump()
            phase='rename_stability';second_job,second=run('renamed_same_content.mov');assert comparable(first)==comparable(second)
            assert hashlib.sha256(media.read_bytes()).hexdigest()==digest
            for result in [first,second]:
                for event in result.violations:
                    for frame in event.evidence_frames:
                        actual=sample(media,[frame.timestamp_sec],max_side=768);assert actual and abs(actual[0].sec-frame.timestamp_sec)<1e-6
                        buffer=BytesIO();actual[0].image.save(buffer,'JPEG',quality=90);assert buffer.getvalue()==base64.b64decode(frame.image_base64,validate=True);jpeg_checks+=1
            phase='invalid_input'
            bad=client.post(url+'/api/v1/analyze',headers=headers,files={'file':('generated_invalid.mov',b'Generated invalid container only','video/quicktime')});assert bad.status_code==200
            bad_job=bad.json()['job_id'];assert poll(bad_job)=={'job_id':bad_job,'status':'failed'}
            phase='default_background_ttl_cleanup'
            # Only a freshly created generated fixture is aged; no existing job is edited.
            expired_id=secrets.token_hex(16);folder=ROOT/'.private/final-service/jobs'/expired_id;folder.mkdir()
            origin=json.loads((ROOT/'.private/final-access/origin-identity.json').read_text())
            (folder/'input.mov').write_bytes(b'Generated expired cleanup fixture, no video content')
            atomic_json(folder/'meta.json',{'owner':hashlib.sha256(record['operator'].encode()).hexdigest(),'created':time.time()-3601,'server_pid':origin['pid'],'server_created':origin['created']})
            until=time.monotonic()+40
            while folder.exists():
                if time.monotonic()>until:raise TimeoutError('Default background TTL cleanup')
                time.sleep(.25)
            assert client.get(url+'/api/v1/jobs/'+expired_id,headers=headers).status_code==404
        report={'status':'PASS','scope':'Real frozen baseline on generated MOV through final public API; technical mechanics, no bank quality',
            'generated_model_jobs_completed':2,'public_upload_to_done_wall_sec':walls,'public_upload_to_done_max_sec':max(walls),'configured_native_job_budget_sec':295,
            'both_generated_jobs_under_300_sec':True,'rename_same_content_output_stable':True,'completed_job_survived_origin_restart':True,'public_url_preserved_on_origin_restart':True,
            'jury_and_other_owner_cannot_read_operator_jobs':True,'missing_wrong_keys_rejected':True,'raw_and_private_paths_blocked':True,
            'corrupt_generated_input_failed_without_verdict':True,'default_3600sec_ttl_removed_aged_generated_fixture':True,'real_model_source_jpeg_checks':jpeg_checks,
            'tune_or_holdout_accessed':False,'bank_data_used':False,'predictions_or_frames_emitted':False,'real_inference_changed':False,'model_quality_claim':False}
        atomic_json(OUT/'safe-summary.json',report);print(json.dumps(report))
    except Exception as error:
        atomic_json(OUT/'failure-safe-summary.json',{'status':'failed','phase':phase,'diagnostic':safe_exception(error,ROOT),'private_content_emitted':False});raise


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
