"""Local loopback entrypoint. Synthetic mode accepts only generated fixtures."""
from pathlib import Path
import os,sys,argparse,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
p=argparse.ArgumentParser();p.add_argument('--synthetic-test',action='store_true');p.add_argument('--port',type=int,default=8765)
p.add_argument('--engine',choices=['baseline','budget'],default=os.environ.get('CASH_ENGINE','baseline'))
p.add_argument('--precision',choices=['bf16','nf4'],default=os.environ.get('CASH_PRECISION','bf16'));a=p.parse_args()
os.environ.update(CASH_ENGINE=a.engine,CASH_PRECISION=a.precision)
if not os.environ.get('CASH_API_KEY'):raise RuntimeError('Set a process-local API key; permanent key needs explicit confirmation')
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
temp=ROOT/'.private/tmp';temp.mkdir(parents=True,exist_ok=True);os.environ['TMP']=os.environ['TEMP']=str(temp)
if a.synthetic_test:
    from scripts.synthetic import generate
    files=[generate(ROOT/'.private/synthetic/safe.mov'),generate(ROOT/'.private/synthetic/positive.mov',positive=True)]
    os.environ['CASH_MODE']='synthetic_test';os.environ['CASH_TEST_HASHES']=','.join(hashlib.file_digest(f.open('rb'),'sha256').hexdigest() for f in files)
else:
    if not (ROOT/'models/qwen3-vl-2b/model.safetensors').exists():raise RuntimeError('Complete local weights missing')
    os.environ['CASH_MODE']='model'
import uvicorn
uvicorn.run('cashreview.api:create_app',factory=True,host='127.0.0.1',port=a.port,access_log=False,log_level='warning',limit_concurrency=64,timeout_keep_alive=5,timeout_graceful_shutdown=10)
