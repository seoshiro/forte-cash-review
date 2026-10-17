"""Benchmark on real TRAIN only, outputs ONLY aggregate technical metrics."""
from pathlib import Path
import os, sys, json, time, hashlib, statistics
from collections import Counter
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch, psutil
from cashreview.engine import LocalEngine
from cashreview.video import sample,Sample
from PIL import Image
from cashreview.observations import ObservationError
from cashreview.offline import deny_network
deny_network()

root=Path('.private');manifest=json.loads((root/'dataset/manifest.json').read_text(encoding='utf-8'));out=root/'benchmark';out.mkdir(parents=True,exist_ok=True)
rows=[r for r in manifest if r['split']=='train' and not r['error']][:3]
torch.cuda.reset_peak_memory_stats();start=time.monotonic();engine=LocalEngine();load=time.monotonic()-start
start=time.monotonic();warmup_valid=True
try:engine.observe([Sample(float(i),Image.new('RGB',(224,224),(25,65,40))) for i in range(6)])
except ValueError:warmup_valid=False
warmup=time.monotonic()-start;torch.cuda.reset_peak_memory_stats()
(out/'frozen-config.json').write_text(json.dumps(engine.config,indent=2),encoding='utf-8')
elapsed=[];success=0;failures=Counter()
for i,r in enumerate(rows):
    start=time.monotonic()
    frames=sample(Path(r['path']),[r['duration_sec']*q for q in [.1,.25,.4,.55,.7,.85]],engine.config['max_side'])
    try:
        observation=engine.observe(frames,research_candidates=True)
        (out/f'private-{i}.json').write_text(json.dumps(observation,ensure_ascii=False),encoding='utf-8');success+=1
    except Exception as e:
        failures[e.code if isinstance(e,ObservationError) else type(e).__name__]+=1
        (out/f'private-{i}-error.txt').write_text(type(e).__name__,encoding='ascii')
    elapsed.append(time.monotonic()-start)
peak6=torch.cuda.max_memory_allocated()/2**20;reserved6=torch.cuda.max_memory_reserved()/2**20
# Probe the actual uniform baseline input size before committing to a tuning run.
longest=max((r for r in manifest if r['split']=='train' and not r['error']),key=lambda r:r['duration_sec'])
torch.cuda.reset_peak_memory_stats();start=time.monotonic();uniform_valid=True
try:
    fs=sample(Path(longest['path']),[longest['duration_sec']*i/12 for i in range(12)],engine.config['max_side'])
    observation=engine.observe(fs)
    (out/'private-uniform-probe.json').write_text(json.dumps(observation,ensure_ascii=False),encoding='utf-8')
except Exception as e:
    failures[e.code if isinstance(e,ObservationError) else type(e).__name__]+=1
    uniform_valid=False;(out/'uniform-probe-error.txt').write_text(type(e).__name__,encoding='ascii')
uniform_time=time.monotonic()-start;peak12=torch.cuda.max_memory_allocated()/2**20;reserved12=torch.cuda.max_memory_reserved()/2**20
summary={'sample_count':len(rows),'json_success_count':success,'model_load_sec':load,'synthetic_warmup_sec':warmup,'synthetic_warmup_json_valid':warmup_valid,'inference_sec_mean':statistics.mean(elapsed),'inference_sec_max':max(elapsed),'peak_vram_mib':max(peak6,peak12),'peak_vram_reserved_mib':max(reserved6,reserved12),'uniform_probe_frames':12,'uniform_probe_sample_count':1,'uniform_probe_json_valid':uniform_valid,'uniform_probe_sec':uniform_time,'uniform_probe_vram_mib':peak12,'process_rss_mib':psutil.Process().memory_info().rss/2**20,'system_ram_gib':psutil.virtual_memory().total/2**30,'cpu_logical':psutil.cpu_count(),'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'sample_frames':6,'model_outputs_private':True,'latency_scope':'six-frame TRAIN observations after synthetic warmup plus separate twelve-frame longest TRAIN probe, including decode; not full API latency'}
summary['technical_failure_categories']=dict(failures)
(out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
sys.exit(not uniform_valid)
