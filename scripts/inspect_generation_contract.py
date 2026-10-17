"""Read only technical runtime/template capabilities; no dataset/model forward."""
from pathlib import Path
import inspect,json,importlib.metadata as metadata
from transformers.generation.utils import GenerationMixin
ROOT=Path(__file__).resolve().parents[1]
template=(ROOT/'models/qwen3-vl-2b/chat_template.json').read_text(encoding='utf-8')
record={'model_variant':'Qwen3-VL-2B-Instruct',
        'template_contains_enable_thinking':'enable_thinking' in template,
        'template_contains_think_tag':'<think>' in template,
        'generate_prefix_allowed_tokens_fn_supported':'prefix_allowed_tokens_fn' in inspect.signature(GenerationMixin.generate).parameters,
        'transformers':metadata.version('transformers'),
        'lm_format_enforcer':metadata.version('lm-format-enforcer'),
        'published_integration_compatible':False,
        'adapter':'cashreview/structured.py uses TokenEnforcerTokenizerData and TokenEnforcer',
        'decoder_proves_semantics':False,'bank_data_read':False}
(ROOT/'.private/generation-contract-safe-summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
