"""Actual native processor check on generated images only; no model forward."""
from pathlib import Path
import json
import os
import sys
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from cashreview.offline import deny_network
    deny_network()
    from transformers import AutoProcessor
    from internvl_candidate.fixtures import frames, prompt
    cfg = json.loads((ROOT / 'config/internvl-protocol.json').read_text())
    model = ROOT / 'models/internvl3_5-1b-hf'
    processor = AutoProcessor.from_pretrained(model, local_files_only=True, trust_remote_code=False)
    image_token = json.loads((model / 'config.json').read_text())['image_token_id']
    results = []
    for count in [0, 4, 8]:
        supplied = (frames('EXIT', 0, cfg) * 2)[:count]
        content = []
        for index, image in enumerate(supplied):
            content.extend([{'type': 'text', 'text': 'F'+str(index)+':'}, {'type': 'image', 'image': image}])
        content.append({'type': 'text', 'text': prompt(0)})
        batch = processor.apply_chat_template([{'role': 'user', 'content': content}], add_generation_prompt=True,
                                              tokenize=True, return_dict=True, return_tensors='pt',
                                              processor_kwargs={'crop_to_patches': False, 'min_patches': 1, 'max_patches': 1})
        observed = int((batch['input_ids'] == image_token).sum().item())
        shape = list(batch['pixel_values'].shape) if 'pixel_values' in batch else None
        if observed != count * 256 or (count and shape != [count, 3, 448, 448]):
            raise ValueError('Native processor correspondence mismatch')
        tokens = batch['input_ids'].shape[-1]
        if tokens > cfg['inference']['max_input_tokens']:
            raise ValueError('Native processor context budget exceeded')
        results.append({'generated_images': count, 'observed_image_tokens': observed, 'input_tokens': tokens, 'pixel_values_shape': shape})
    summary = {'split': 'synthetic', 'status': 'processor_verified_no_model_forward', 'conditions': results,
               'network_guard_enabled': True, 'trust_remote_code': False, 'gpu_or_bank_data_used': False}
    path = ROOT / '.private/internvl-prepare/processor-native-kwargs-safe-summary.json'
    with path.open('x') as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'not_verified', 'technical_error_type': type(error).__name__, 'private_content_emitted': False}))
        sys.exit(1)
