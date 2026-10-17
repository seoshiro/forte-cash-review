"""Isolated child: receives opaque path, never prints content or inference results."""
from pathlib import Path
import os, sys, json, hashlib, base64
os.environ.update(HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_TELEMETRY="1",DO_NOT_TRACK="1")


def main():
    from .offline import deny_network
    deny_network()
    folder=Path(sys.argv[1]).resolve(); job_id=folder.name
    # A reader must never observe the empty interval created by write_text.
    # Publish ownership before model imports, using an atomic same-dir rename.
    temporary_pid=folder/'worker.pid.tmp'
    with temporary_pid.open('x',encoding='ascii') as stream:
        stream.write(str(os.getpid()));stream.flush();os.fsync(stream.fileno())
    temporary_pid.replace(folder/'worker.pid')
    try:
        if os.environ.get("CASH_MODE")=="synthetic_test":
            # Isolated test fixture, never a detector. Only generated test videos accepted.
            from .video import inspect, sample
            from io import BytesIO
            from .schemas import Done
            digest=hashlib.file_digest((folder/"input.mov").open('rb'),'sha256').hexdigest()
            if digest not in os.environ.get('CASH_TEST_HASHES','').split(','): raise ValueError('Not a whitelisted synthetic fixture')
            # Only hash-whitelisted generated media can exercise the test delay.
            if os.environ.get('CASH_TEST_DELAY_SEC'):
                import time
                time.sleep(min(30,max(0,float(os.environ['CASH_TEST_DELAY_SEC']))))
            info=inspect(folder/"input.mov",decode=True)
            if info["width"]!=320 or info["height"]!=240 or info["duration_sec"]>4: raise ValueError("Fixture only")
            fs=sample(folder/'input.mov',[.5,1,1.5],320)
            positive=any(f.image.getchannel('R').getextrema()[1]>200 for f in fs)
            events=[]
            if positive:
                enc=[]
                for f in fs:
                    b=BytesIO();f.image.save(b,'JPEG');enc.append({'timestamp_sec':f.sec,'image_base64':base64.b64encode(b.getvalue()).decode('ascii')})
                events=[{'type':'Искусственный тест: цветной квадрат','timecode_sec':fs[1].sec,'description':'Синтетический тест контракта, не банковское нарушение.','evidence_frames':enc}]
            result=Done(job_id=job_id,verdict='violation' if events else 'no_violation',violations=events).model_dump()
            detail=[{'observation':'Искусственный квадрат для проверки интерфейса.','rule':{'requirement':'Тестовое условие; нормативная применимость отсутствует.','paragraph':'—'},'limitation':'Это тест UI, качество модели не измерено.'}] if events else []
            (folder/"detail.json").write_text(json.dumps({"events":detail,"duration_sec":info["duration_sec"],"limitations":["Искусственный тест API; качество обнаружения не проверяется."]}),encoding="utf-8")
        else:
            from .video import validate_input
            validate_input(folder/'input.mov')
            engine=os.environ.get('CASH_ENGINE','baseline')
            if engine=='xclip_experimental':
                if os.environ.get('CASH_MODE')!='xclip_experimental':raise ValueError('Research engine requires isolated experimental mode')
                from xclip_candidate.experimental import ExperimentalEngine
                deadline=float(os.environ['CASH_WORKER_DEADLINE_MONOTONIC'])
                result=ExperimentalEngine(deadline=deadline).analyze(folder/'input.mov',job_id)
            elif engine=='budget':
                from budget_candidate.engine import BudgetEngine
                result=BudgetEngine(os.environ.get('CASH_PRECISION','bf16')).analyze(folder/'input.mov',job_id,folder)
            elif engine=='baseline':
                from .engine import LocalEngine
                result=LocalEngine().analyze(folder/"input.mov",job_id,folder,os.environ.get("CASH_STRATEGY"))
            else:raise ValueError('Unknown local engine configuration')
        name='experimental-result.json' if os.environ.get('CASH_MODE')=='xclip_experimental' else 'result.json'
        temp=folder/(name+'.tmp');temp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');temp.replace(folder/name)
    except Exception:
        # Deliberately omit paths and model outputs from errors.
        (folder/"failed").write_text("local_processing_failed",encoding="ascii")
        sys.exit(1)

if __name__=="__main__": main()
