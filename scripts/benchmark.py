"""Benchmark on real TRAIN only, outputs ONLY aggregate technical metrics."""
from pathlib import Path
import os, sys, json, time, hashlib, statistics
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch, psutil
from cashreview.engine import LocalEngine
from cashreview.video import sample
from cashreview.offline import deny_network
deny_network()

root=Path('.private');manifest=json.loads((root/'dataset/manifest.json').read_text(encoding='utf-8'));out=root/'benchmark';out.mkdir(parents=True,exist_ok=True)
rows=[r for r in manifest if r['split']=='train' and not r['error']][:3]
torch.cuda.reset_peak_memory_stats();start=time.monotonic();engine=LocalEngine();load=time.monotonic()-start
elapsed=[];success=0
for i,r in enumerate(rows):
    start=time.monotonic()
    frames=sample(Path(r['path']),[r['duration_sec']*q for q in [.1,.25,.4,.55,.7,.85]],engine.config['max_side'])
    try:
        observation=engine.observe(frames,research_candidates=True)
        (out/f'private-{i}.json').write_text(json.dumps(observation,ensure_ascii=False),encoding='utf-8');success+=1
    except Exception as e:
        (out/f'private-{i}-error.txt').write_text(type(e).__name__,encoding='ascii')
    elapsed.append(time.monotonic()-start)
summary={'sample_count':len(rows),'json_success_count':success,'model_load_sec':load,'inference_sec_mean':statistics.mean(elapsed),'inference_sec_max':max(elapsed),'peak_vram_mib':torch.cuda.max_memory_allocated()/2**20,'system_ram_gib':psutil.virtual_memory().total/2**30,'cpu_logical':psutil.cpu_count(),'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'sample_frames':6,'model_outputs_private':True}
(out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
