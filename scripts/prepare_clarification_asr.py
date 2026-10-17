"""Prepare isolated official CPU Whisper; never reads or transcribes video."""
from pathlib import Path
import os,sys,json,subprocess,urllib.request,urllib.parse,time,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.download_chunks import fetch
def main():
    out=ROOT/'.private/clarifications';out.mkdir(exist_ok=True)
    if not (out/'source-registration.json').is_file():raise RuntimeError('Explicit clarification source registration is required')
    target=(ROOT/'.venv-asr').resolve()
    if target.parent!=ROOT or target.name!='.venv-asr':raise RuntimeError('Invalid isolated ASR target')
    uv=Path(r'C:\Users\gokusen\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe')
    env=os.environ.copy();env.update(UV_CACHE_DIR=str(ROOT/'.cache'),UV_HTTP_TIMEOUT='600')
    def stage(name):
        (out/'asr-stage-safe-summary.json').write_text(json.dumps({'stage':name,'video_read':False,'gpu_workload':False,'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}))
    with (out/'asr-install.log').open('w') as log:
        stage('isolated_cpu_environment')
        if not target.exists():subprocess.run([str(uv),'venv','--python',sys._base_executable,str(target)],env=env,stdout=log,stderr=log,check=True)
        python=target/'Scripts/python.exe'
        subprocess.run([str(uv),'pip','install','--python',str(python),'torch==2.14.1+cpu','--index-url','https://download.pytorch.org/whl/cpu','--no-progress'],env=env,stdout=log,stderr=log,check=True)
        subprocess.run([str(uv),'pip','install','--python',str(python),'openai-whisper==20250625','av==19.0.1','setuptools==83.0.0','packaging','--no-progress'],env=env,stdout=log,stderr=log,check=True)
    stage('dependency_audit')
    with (out/'asr-audit.stdout.log').open('w') as stdout,(out/'asr-audit.stderr.log').open('w') as stderr:
        subprocess.run([str(python),str(ROOT/'scripts/audit_installed.py'),'--output-directory','.private/clarifications/asr-audit'],cwd=ROOT,stdout=stdout,stderr=stderr,check=True)
    stage('official_small_weight_download')
    code="import whisper,torch,json;print(json.dumps({'url':whisper._MODELS['small'],'torch':str(torch.__version__),'cuda_initialized':torch.cuda.is_initialized()}))"
    metadata=json.loads(subprocess.check_output([str(python),'-c',code],text=True))
    if not metadata['torch'].endswith('+cpu') or metadata['cuda_initialized']:raise RuntimeError('ASR must use CPU-only Torch')
    url=metadata['url'];parts=urllib.parse.urlsplit(url)
    if parts.hostname not in {'openaipublic.azureedge.net','openaipublic.blob.core.windows.net'}:raise RuntimeError('Unexpected Whisper model host')
    sha=parts.path.split('/')[-2]
    if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise RuntimeError('Whisper official SHA is missing')
    with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:size=int(response.headers['Content-Length'])
    model=ROOT/'models/whisper-small/small.pt';model.parent.mkdir(exist_ok=True)
    fetch(url,model,size,sha,progress=out/'asr-weight.progress.json')
    provenance={'name':'OpenAI Whisper small','url':url,'bytes':size,'sha256':sha,'code_version':'openai-whisper 20250625','license':'MIT code and weights','device':'cpu','torch':metadata['torch'],'path':str(model)}
    (out/'asr-model-provenance.json').write_text(json.dumps(provenance,indent=2))
    report={'status':'ready_for_local_cpu_transcription','device':'cpu','code_license':'MIT','weights_license':'MIT','model_bytes':size,'weight_sha_verified':True,'video_read':False,'source_modified':False,'gpu_workload':False}
    (out/'asr-preparation-safe-summary.json').write_text(json.dumps(report,indent=2));stage('ready');print(json.dumps(report))
if __name__=='__main__':
    try:main()
    except Exception as error:
        out=ROOT/'.private/clarifications';out.mkdir(exist_ok=True)
        r={'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],'video_read':False,'raw_content_emitted':False}
        (out/'asr-preparation-safe-summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));sys.exit(1)
