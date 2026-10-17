"""Post-hoc public-header calculation. Preserve the original runtime report."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.audit_qwen_metadata import header
from hybrid_candidate.template_audit import digest_text
from hybrid_candidate.template_source import lexer_source
from xclip_candidate.experimental import sha


def main():
    out=ROOT/'.private/runtime-template-audit'
    original=json.loads((out/'safe-summary.json').read_text())
    terminal=json.loads((out/'run/terminal-safe-summary.json').read_text())
    if original['status']!='completed' or terminal['worker_exit_code']!=0 or not terminal['cleanup_complete']:
        raise ValueError('Incomplete runtime audit')
    template=header(ROOT/'models/qwen3vl-4b-gguf/Qwen3VL-4B-Instruct-Q4_K_M.gguf')['metadata']['tokenizer.chat_template']
    if digest_text(template)!='3636d0f0bd6bef02654cdffdc447b79cb2cef8ab02cc75267345946291a489e4':
        raise ValueError('Unexpected public header')
    normalized=lexer_source(template)
    result={'split':'synthetic','status':'calculated','post_hoc_interpretation':True,
        'original_runtime_report_modified':False,'original_runtime_report_sha256':sha(out/'safe-summary.json'),
        'public_header_chars':len(template),'normalized_header_chars':len(normalized),
        'public_header_sha256':digest_text(template),'normalized_header_sha256':digest_text(normalized),
        'observed_props_sha256':original['checks']['props']['template_sha256'],
        'normalized_hash_matches_observed_props':digest_text(normalized)==original['checks']['props']['template_sha256'],
        'difference_is_single_terminal_lf':template==normalized+'\n',
        'source_reference':'https://github.com/ggml-org/llama.cpp/blob/b11712/common/jinja/lexer.cpp#L29-L53',
        'constructor_reference':'https://github.com/ggml-org/llama.cpp/blob/b11712/common/chat.cpp#L1164-L1169',
        'generation_calls':0,'server_started':False,'bank_data_or_user_notes_read':False,
        'action_quality_or_vision_embeddings_validated':False}
    with (out/'source-normalization-safe-summary.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'not_calculated','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
