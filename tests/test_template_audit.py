import pytest,json
from pathlib import Path
from hybrid_candidate.template_audit import compile_expected,normalize_server_messages,compare_prompt,cases
from scripts.audit_runtime_template import RestrictedClient


def test_strict_expected_renderer_rejects_missing_variables():
    renderer=compile_expected('{{ absent }}')
    with pytest.raises(Exception):renderer.render()


def test_media_normalization_preserves_marker_and_text_order():
    original=[{'role':'user','content':[{'type':'text','text':'F0:'},{'type':'image_url','image_url':{'url':'generated'}},
        {'type':'text','text':'F1:'},{'type':'image_url','image_url':{'url':'generated'}},{'type':'text','text':'end'}]}]
    assert normalize_server_messages(original,'MARK')[0]['content']=='F0:MARKF1:MARKend'
    assert original[0]['content'][1]['type']=='image_url'


def test_generation_http_paths_are_unreachable_through_audit_client():
    class Client:
        def request(self,*args,**kwargs):raise AssertionError('Unexpected network')
    restricted=RestrictedClient(Client(),'http://127.0.0.1:1')
    for url in ['http://127.0.0.1:1/v1/chat/completions','https://example.invalid/props','http://127.0.0.1:10/props']:
        with pytest.raises(ValueError):restricted.call('POST',url)


def test_prompt_checks_detect_lost_image_or_wrong_generation_suffix():
    case={'messages':[{'role':'user'}],'generation':True,'images':1,'sentinels':['SYNTH']}
    prompt='<|im_start|>user\nSYNTHMARK<|im_end|>\n<|im_start|>assistant\n'
    assert compare_prompt(prompt,prompt,case,'MARK')['all_checks_passed']
    assert not compare_prompt(prompt.replace('MARK',''),prompt,case,'MARK')['all_checks_passed']


def test_text_fixture_uses_same_single_typed_part_as_actual_action_probe():
    cfg=json.loads((Path(__file__).resolve().parents[1]/'config/qwen-action-probe.json').read_text())
    case=next(c for c in cases(cfg) if c['id']=='user_typed_text')
    content=case['messages'][0]['content']
    assert len(content)==1 and content[0]['type']=='text' and content[0]['text'].startswith('Fictional coordinate control.')
