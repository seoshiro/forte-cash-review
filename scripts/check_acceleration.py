"""Synthetic CUDA/operator/processor check; no dataset read or model inference."""
from pathlib import Path
import os,sys,json,time
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.offline import deny_network
deny_network()
import torch,torchvision
from PIL import Image
from transformers import AutoProcessor

result={'torch':torch.__version__,'torchvision':torchvision.__version__,'cuda_available':torch.cuda.is_available(),'model_loaded':False,'real_video_read':False}
if result['cuda_available']:
    result.update(cuda_runtime=torch.version.cuda,gpu=torch.cuda.get_device_name(),bf16_supported=torch.cuda.is_bf16_supported())
    torch.cuda.reset_peak_memory_stats();x=torch.randn(1024,1024,device='cuda',dtype=torch.bfloat16)
    with torch.inference_mode():
        for _ in range(3):y=x@x
        torch.cuda.synchronize();start=time.monotonic()
        for _ in range(20):y=x@x
        torch.cuda.synchronize()
    result.update(synthetic_matmul_iterations=20,synthetic_matmul_total_sec=time.monotonic()-start,synthetic_vram_peak_mib=torch.cuda.max_memory_allocated()/2**20)
    processor=AutoProcessor.from_pretrained(str(ROOT/'models/qwen3-vl-2b'),local_files_only=True,min_pixels=64*32*32,max_pixels=196*32*32)
    content=[{'type':'image','image':Image.new('RGB',(224,224),(20,65,40))} for _ in range(6)]+[{'type':'text','text':'Return an empty JSON object.'}]
    start=time.monotonic();inputs=processor.apply_chat_template([{'role':'user','content':content}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt')
    result.update(synthetic_processor_sec=time.monotonic()-start,synthetic_processor_shapes={k:list(v.shape) for k,v in inputs.items() if hasattr(v,'shape')},processor_class=type(processor).__name__)
out=ROOT/'.private/acceleration-safe-summary.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
