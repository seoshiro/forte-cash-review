"""Long generated MOV through the frozen final baseline; no semantic results out."""
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json
from cashreview.technical_diagnostics import safe_exception
OUT=ROOT/'.private/final-long-synthetic-qa'


def main():
    import av,numpy as np,httpx
    from cashreview.local_secrets import load
    from cashreview.final_delivery import validate_session
    from cashreview.schemas import Done
    OUT.mkdir(exist_ok=False);phase='generate';started=time.monotonic();media=OUT/'generated_145s.mov'
    try:
        with av.open(str(media),'w',format='mov',options={'movflags':'faststart'}) as container:
            stream=container.add_stream('libx264',rate=30);stream.width=960;stream.height=540;stream.pix_fmt='yuv420p';stream.options={'crf':'25','preset':'ultrafast','threads':'2'}
            for index in range(4350):
                array=np.empty((540,960,3),dtype=np.uint8);array[:]=[31,57,45];x=(index*3)%880;array[200:280,x:x+60]=[150,185,140]
                for packet in stream.encode(av.VideoFrame.from_ndarray(array,format='rgb24')):container.mux(packet)
            for packet in stream.encode():container.mux(packet)
        generation=time.monotonic()-started
        record=validate_session(load(ROOT/'.private/final-access/credentials.dpapi'));endpoint=json.loads((ROOT/'.private/final-access/endpoint.json').read_text());assert endpoint['active_expected'];url=endpoint['url'];headers={'X-API-Key':record['operator']}
        phase='public_real_baseline';atomic_json(OUT/'progress-safe-summary.json',{'phase':phase,'generated_duration_sec':145,'bank_data_used':False})
        with httpx.Client(timeout=25,trust_env=False,follow_redirects=False) as client:
            tick=time.monotonic()
            with media.open('rb') as stream:response=client.post(url+'/api/v1/analyze',headers=headers,files={'file':('generated_long.mov',stream,'video/quicktime')})
            assert response.status_code==200;job=response.json()['job_id'];deadline=tick+299
            while time.monotonic()<deadline:
                response=client.get(url+'/api/v1/jobs/'+job,headers=headers);assert response.status_code==200;value=response.json()
                if value['status']!='processing':break
                time.sleep(.5)
            Done.model_validate(value);wall=time.monotonic()-tick;assert wall<300
        report={'status':'PASS','scope':'Long generated geometric MOV technical latency only; not bank quality, complex-video performance or SLA',
            'generated_jobs_completed':1,'duration_sec':145,'fps':30,'width':960,'height':540,'generated_frames':4350,'generated_file_bytes':media.stat().st_size,
            'generation_wall_sec':generation,'public_upload_to_done_wall_sec':wall,'configured_native_job_budget_sec':295,'below_300_sec':True,
            'real_baseline_unchanged':True,'bank_data_used':False,'tune_holdout_accessed':False,'predictions_or_frames_emitted':False}
        atomic_json(OUT/'safe-summary.json',report);print(json.dumps(report))
    except Exception as error:
        atomic_json(OUT/'failure-safe-summary.json',{'status':'failed','phase':phase,'diagnostic':safe_exception(error,ROOT),'private_content_emitted':False});raise


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
