"""Owned offline native child. Loopback only, no OS grants or persistent keys."""
from pathlib import Path
from io import BytesIO
import os,json,time,socket,subprocess,threading,base64,hashlib
import httpx
from cashreview.processes import kill_tree
ROOT=Path(__file__).resolve().parents[1]
TEST_KEY='temporary-local-native-test-only'

def gpu_used_mib():
    try:
        r=subprocess.run(['nvidia-smi','--id=0','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,creationflags=subprocess.CREATE_NO_WINDOW)
        return float(r.stdout.strip()) if r.returncode==0 else None
    except (OSError,ValueError,subprocess.TimeoutExpired):return None

class DeviceMeter:
    def __init__(self):self.stop_event=threading.Event();self.values=[];self.thread=None
    def start(self):
        self.values=[];self.stop_event.clear()
        def loop():
            while not self.stop_event.is_set():
                value=gpu_used_mib()
                if value is not None:self.values.append(value)
                self.stop_event.wait(.5)
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(3)
        return {'gpu_device_used_peak_observed_mib':max(self.values) if self.values else None,
                'gpu_memory_samples':len(self.values),'gpu_memory_scope':'Device-wide sampled usage; includes other processes; not per-process allocation'}

class NativeServer:
    def __init__(self,private):
        self.private=Path(private);self.private.mkdir(parents=True,exist_ok=True);self.process=None
        cfg=json.loads((ROOT/'config/gguf-artifacts.json').read_text());ready=ROOT/'.private/gguf-preflight/safe-summary.json'
        if not ready.is_file() or json.loads(ready.read_text()).get('status')!='artifacts_verified_not_benchmarked':raise RuntimeError('Verified native artifacts are not ready')
        self.exe=Path(json.loads(ready.read_text())['server_path']).resolve()
        if not self.exe.is_relative_to((ROOT/'.private/llama-cuda124-b11712').resolve()):raise RuntimeError('Unexpected native runtime path')
        self.models={}
        for row in cfg['artifacts']:
            if row['kind']!='model':continue
            path=ROOT/'models/qwen3vl-4b-gguf'/row['filename']
            if path.stat().st_size!=row['bytes']:raise RuntimeError('Incomplete native model artifact')
            with path.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=row['sha256']:raise RuntimeError('Native model hash mismatch')
            self.models['projector' if row['filename'].startswith('mmproj') else 'text']=path
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));self.port=probe.getsockname()[1]
        self.base=f'http://127.0.0.1:{self.port}';self.client=httpx.Client(trust_env=False,follow_redirects=False,timeout=5,headers={'Authorization':'Bearer '+TEST_KEY})
    def start(self):
        args=[str(self.exe),'--offline','--model',str(self.models['text']),'--mmproj',str(self.models['projector']),
              '--device','CUDA0','--mmproj-device','CUDA0','--gpu-layers','all','--fit','off',
              '--ctx-size','4096','--parallel','1','--threads','4','--batch-size','512','--ubatch-size','128',
              '--image-min-tokens','64','--image-max-tokens','256','--mtmd-batch-max-tokens','512',
              '--host','127.0.0.1','--port',str(self.port),'--no-webui','--no-agent','--no-ui-mcp-proxy',
              '--cors-origins','http://127.0.0.1','--no-cors-credentials','--api-key',TEST_KEY,'--log-disable']
        env={k:v for k,v in os.environ.items() if not k.startswith(('LLAMA_','MTMD_','HF_'))}
        env['PATH']=str(self.exe.parent)+os.pathsep+env.get('PATH','')
        self.started=time.monotonic()
        with (self.private/'native.stdout.log').open('w') as stdout,(self.private/'native.stderr.log').open('w') as stderr:
            self.process=subprocess.Popen(args,cwd=self.exe.parent,env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        (self.private/'native.pid').write_text(str(self.process.pid))
        deadline=self.started+120
        try:
            while time.monotonic()<deadline:
                if self.process.poll() is not None:raise RuntimeError('Native model startup failed')
                try:
                    if self.client.get(self.base+'/health').status_code==200:
                        self.load_sec=time.monotonic()-self.started;return
                except httpx.HTTPError:pass
                time.sleep(.2)
            raise TimeoutError('Native startup deadline exceeded')
        except BaseException:self.close();raise
    def complete(self,frames,prompt,schema,max_tokens,deadline):
        content=[]
        for i,frame in enumerate(frames):
            buffer=BytesIO();frame.image.save(buffer,'JPEG',quality=95)
            content.extend([{'type':'text','text':f'F{i}: {frame.sec:.6f} seconds:'},
                            {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')}}])
        content.append({'type':'text','text':prompt})
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Native analysis deadline exhausted')
        body={'messages':[{'role':'user','content':content}],'max_tokens':max_tokens,'temperature':0,'seed':26101731,
              'cache_prompt':False,'stream':False,'n':1}
        if schema:body['response_format']={'type':'json_schema','schema':schema}
        tick=time.monotonic();response=self.client.post(self.base+'/v1/chat/completions',json=body,timeout=remaining)
        if response.status_code!=200:raise RuntimeError('Native inference HTTP failure')
        data=response.json();choices=data.get('choices')
        if not isinstance(choices,list) or len(choices)!=1:raise RuntimeError('Unexpected native sequence count')
        text=choices[0].get('message',{}).get('content')
        if not isinstance(text,str):raise RuntimeError('Native text content missing')
        # Do not forward server errors or response text to developer stdout.
        usage=data.get('usage',{})
        metrics={'frames':len(frames),'generation_sec':time.monotonic()-tick,
                 'input_tokens':usage.get('prompt_tokens'),'generated_tokens':usage.get('completion_tokens')}
        return text,metrics
    def close(self):
        self.client.close()
        if self.process and self.process.poll() is None:kill_tree(self.process.pid)
