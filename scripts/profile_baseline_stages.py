"""One TRAIN-only technical profile, after TUNE; never emits video content."""
from pathlib import Path
import os,sys,json,time,functools,statistics
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
from cashreview.offline import deny_network
deny_network()
import cashreview.engine as module
from lmformatenforcer.tokenenforcer import TokenEnforcer
from PIL import Image
stats={};events=[]
def add(name,value):stats[name]=stats.get(name,0.)+value
def timed_sample(*args,**kwargs):
    maximum=kwargs.get('max_side',args[2] if len(args)>2 else 448);start=time.monotonic()
    result=original_sample(*args,**kwargs)
    add('evidence_decode_sec' if maximum==960 else 'candidate_decode_sec',time.monotonic()-start)
    return result
original_sample=module.sample;module.sample=timed_sample
original_filter=TokenEnforcer.get_allowed_tokens
@functools.wraps(original_filter)
def token_filter(self,*args,**kwargs):
    start=time.monotonic()
    try:return original_filter(self,*args,**kwargs)
    finally:add('constrained_filter_cpu_sec',time.monotonic()-start);add('filter_calls',1)
TokenEnforcer.get_allowed_tokens=token_filter
original_prefix=module.prefix_function
def build_prefix(*args,**kwargs):
    start=time.monotonic();function=original_prefix(*args,**kwargs);add('constrained_build_sec',time.monotonic()-start)
    def allowed(*a,**k):
        tick=time.monotonic()
        try:return function(*a,**k)
        finally:add('constrained_callback_wall_sec',time.monotonic()-tick)
    return allowed
module.prefix_function=build_prefix
original_save=Image.Image.save
@functools.wraps(original_save)
def save(image,*args,**kwargs):
    start=time.monotonic()
    try:return original_save(image,*args,**kwargs)
    finally:add('jpeg_encode_sec',time.monotonic()-start)
Image.Image.save=save
out=ROOT/'.private/stage-profile'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());out.mkdir(parents=True)
started=time.monotonic();engine=module.LocalEngine();load=time.monotonic()-started
original_preprocess=engine.processor.apply_chat_template
@functools.wraps(original_preprocess)
def preprocess(*args,**kwargs):
    start=time.monotonic()
    try:return original_preprocess(*args,**kwargs)
    finally:add('preprocess_cpu_wall_sec',time.monotonic()-start)
engine.processor.apply_chat_template=preprocess
original_forward=engine.model.forward
@functools.wraps(original_forward)
def forward(*args,**kwargs):
    first=engine.torch.cuda.Event(enable_timing=True);last=engine.torch.cuda.Event(enable_timing=True)
    first.record();result=original_forward(*args,**kwargs);last.record();events.append((first,last));return result
engine.model.forward=forward
original_generate=engine.model.generate
@functools.wraps(original_generate)
def generate(*args,**kwargs):
    start=time.monotonic();result=original_generate(*args,**kwargs);engine.torch.cuda.synchronize()
    add('generation_total_wall_sec',time.monotonic()-start)
    add('generated_tokens',int(result.shape[1]-kwargs['input_ids'].shape[1]));return result
engine.model.generate=generate
rows=[r for r in json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8')) if r['split']=='train' and not r['error']]
row=max(rows,key=lambda r:r['duration_sec']);start=time.monotonic();success=False;failure=None
try:
    engine.analyze(Path(row['path']),'private-profile',out/'private','uniform');success=True
except Exception as error:failure=getattr(error,'code',type(error).__name__)
elapsed=time.monotonic()-start;engine.torch.cuda.synchronize()
gpu=[first.elapsed_time(last)/1000 for first,last in events]
report={'sample_count':1,'split':'train','selection':'longest TRAIN duration, technical metadata only',
        'analysis_success':success,'technical_failure':failure,'model_load_sec':load,
        'engine_analyze_sec':elapsed,'scope':'instrumented engine only; excludes API/upload/queue',
        'wall_metrics':stats,'gpu_forward_event_count':len(gpu),'gpu_forward_sum_sec':sum(gpu),
        'gpu_prefill_forward_sec':gpu[0] if gpu else None,'gpu_subsequent_forward_sum_sec':sum(gpu[1:]),
        'constrained_callback_excluding_filter_sec':max(0,stats.get('constrained_callback_wall_sec',0)-stats.get('constrained_filter_cpu_sec',0)),
        'vram_allocated_peak_mib':engine.torch.cuda.max_memory_allocated()/2**20,
        'vram_reserved_peak_mib':engine.torch.cuda.max_memory_reserved()/2**20,
        'holdout_read':False,'per_video_outputs_private':True,
        'limitations':'One instrumented TRAIN case, not quality evidence. Callback wall includes GPU synchronization; GPU event and CPU wall measurements can overlap and must not be summed. Timing wrappers add small unmeasured overhead.'}
(out/'safe-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
