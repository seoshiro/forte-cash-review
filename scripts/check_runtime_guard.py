"""Actual installed-runtime loader-denial test; synthetic bytes, no CUDA init."""
from pathlib import Path
import sys,json,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from budget_candidate.runtime_guard import disable_artifact_loaders
class UnreadableSynthetic:
    reads=0
    def read(self,*args,**kwargs):
        self.reads+=1
        raise AssertionError('Synthetic stream must not be read')
report=disable_artifact_loaders(torch);stream=UnreadableSynthetic();denied=0
for loader in [torch.load,torch.serialization.load,torch.jit.load,torch.export.load]:
    try:loader(stream)
    except RuntimeError as error:
        if str(error)=='Executable model artifact loading is disabled in this inference process':denied+=1
record={'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'torch':torch.__version__,'loaders_denied':denied,'attempted_stream_reads':stream.reads,
        'cuda_initialized':torch.cuda.is_initialized(),'scope':report['scope'],
        'guard_active_in_running_baseline':False,'bank_data_read':False}
(ROOT/'.private/runtime-guard-safe-summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record));sys.exit(denied!=4 or stream.reads!=0 or torch.cuda.is_initialized())
