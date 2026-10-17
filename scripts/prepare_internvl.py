"""Pinned public model artifacts only. Streaming download, no media or inference."""
from pathlib import Path
import hashlib
import json
import sys
import time
import httpx
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_chunks import fetch


def main():
    cfg = json.loads((ROOT / 'config/internvl-artifacts.json').read_text())
    out = ROOT / '.private/internvl-prepare'
    out.mkdir(exist_ok=True)
    if psutil.virtual_memory().available < 4 * 2**30:
        raise MemoryError('Insufficient current RAM reserve before download')
    if cfg['weight_license'] != 'apache-2.0' or cfg['weight_bytes'] > 2600000000:
        raise ValueError('Unexpected selected license/size')
    model = ROOT / 'models/internvl3_5-1b-hf'
    model.mkdir(exist_ok=True)
    started = time.monotonic()
    deadline = started + 480
    digests = {}
    total = sum(row['bytes'] for row in cfg['artifacts'])
    if total > cfg['max_download_bytes']:
        raise ValueError('Artifact budget exceeded')
    with httpx.Client(timeout=25, follow_redirects=True, trust_env=False) as client:
        for row in cfg['artifacts']:
            name = row['filename']
            if Path(name).name != name or Path(name).suffix not in {'.json', '.safetensors', '.jinja', '.txt'}:
                raise ValueError('Unexpected artifact type or path')
            url = f"https://huggingface.co/{cfg['model']}/resolve/{cfg['revision']}/{name}"
            path = model / name
            if row['sha256']:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Download budget exhausted')
                fetch(url, path, row['bytes'], row['sha256'], workers=2, chunk_bytes=4*2**20,
                      budget_sec=remaining, progress=out / 'download-progress.json')
            else:
                if row['bytes'] > 4*2**20 or time.monotonic() >= deadline:
                    raise ValueError('Small artifact budget exceeded')
                response = client.get(url)
                response.raise_for_status()
                if len(response.content) != row['bytes']:
                    raise ValueError('Official small artifact size mismatch')
                path.write_bytes(response.content)
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if row['sha256'] and actual != row['sha256']:
                raise ValueError('Official artifact digest mismatch')
            digests[name] = actual
        response = client.get(f"https://huggingface.co/{cfg['model']}/resolve/{cfg['revision']}/README.md")
        response.raise_for_status()
        if len(response.content) > 100000 or b'apache-2.0' not in response.content.lower():
            raise ValueError('Official model card/license missing')
        (out / 'official-model-card.md').write_bytes(response.content)
        digests['official-model-card.md'] = hashlib.sha256(response.content).hexdigest()
    if time.monotonic() > deadline:
        raise TimeoutError('Download and verification exceeded budget')
    provenance = {'model': cfg['model'], 'revision': cfg['revision'], 'weight_license': cfg['weight_license'],
                  'runtime_license': cfg['runtime_license'], 'artifact_sha256': digests, 'weight_bytes': cfg['weight_bytes']}
    with (model / 'provenance.json').open('x') as stream:
        json.dump(provenance, stream, indent=2)
    result = {'split': 'technical', 'status': 'weights_verified_not_loaded', 'weight_bytes': cfg['weight_bytes'],
              'artifact_count': len(cfg['artifacts']), 'download_and_verification_sec': time.monotonic()-started,
              'sha256_verified': True, 'model_inference_started': False, 'bank_media_or_annotations_read': False,
              'credentials_created': False, 'runtime_environment_modified': False}
    with (out / 'safe-summary.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        result = {'status': 'not_prepared', 'technical_error_type': type(error).__name__, 'private_content_emitted': False}
        (ROOT / '.private/internvl-prepare/failure-safe-summary.json').write_text(json.dumps(result))
        print(json.dumps(result), flush=True)
        sys.exit(1)
