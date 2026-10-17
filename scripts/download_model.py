"""Public weights/code download only; never reads video or user credentials."""
from pathlib import Path
import os, json
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
from huggingface_hub import HfApi, snapshot_download

ROOT=Path(__file__).resolve().parents[1]
repo='Qwen/Qwen3-VL-2B-Instruct'
info=HfApi(token=False).model_info(repo)
target=ROOT/'models/qwen3-vl-2b'
snapshot_download(repo,revision=info.sha,local_dir=str(target),token=False,allow_patterns=['*.json','*.safetensors','*.txt','*.jinja','LICENSE','README.md','*.model'],max_workers=2)
card=(target/'README.md').read_text(encoding='utf-8')
if 'license: apache-2.0' not in card.lower(): raise RuntimeError('Weights license missing from official model card')
record={'repo':repo,'revision':info.sha,'weights_license':'Apache-2.0','code_license':'Apache-2.0 (Transformers and official Qwen3-VL)','bytes':sum(f.stat().st_size for f in target.rglob('*') if f.is_file())}
(ROOT/'models/provenance.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
