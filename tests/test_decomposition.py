from pathlib import Path
import json,copy,re
import pytest
from hybrid_candidate.decomposition import expected_facts,body,score,expected,KEYS
from hybrid_candidate.discrimination import prompt as old_prompt

CFG=json.loads((Path(__file__).resolve().parents[1]/'config/qwen-decomposition-protocol.json').read_text())
OLD=json.loads((Path(__file__).resolve().parents[1]/'config/qwen-text-discrimination.json').read_text())
TRUTH={'exit':{'first_inside':True,'last_inside':False,'all_inside':False},
    'enter':{'first_inside':False,'last_inside':True,'all_inside':False},
    'stay':{'first_inside':True,'last_inside':True,'all_inside':True}}
LABEL={'exit':'ALPHA','enter':'BETA','stay':'GAMMA'}


@pytest.mark.parametrize('action',list(TRUTH))
def test_numeric_and_boolean_ground_truth_matches_independent_literal_table(action):
    assert expected_facts(action,CFG)==TRUTH[action]
    for case in CFG['cells']:
        request=body(action,case,CFG)
        assert set(request)=={'messages','temperature','seed','max_tokens','cache_prompt','stream','n'}
        assert len(request['messages'])==len(request['messages'][0]['content'])==1
        text=request['messages'][0]['content'][0]['text']
        if case['family']=='binding':
            facts=json.loads(re.search(r'Facts=(\{[^}]+\})',text)[1]);assert facts==TRUTH[action]
            answer={'label':LABEL[action]}
        else:
            xs=json.loads(re.search(r'ordered center x=(\[[^]]+\])',text)[1])
            assert xs=={'exit':[70,110,165,220],'enter':[220,165,110,70],'stay':[70,95,125,150]}[action]
            assert '[24, 24, 180, 232]' in text and 'disk radius=9' in text
            answer=TRUTH[action] if case['family']=='facts' else {'label':LABEL[action]}
        assert expected(action,case,CFG)==answer and score(json.dumps(answer),'stop',action,case,CFG)['correct']
        assert not score(json.dumps(answer),'length',action,case,CFG)['correct']


def test_bool_parser_rejects_numeric_truth_alias_and_duplicate_or_extra_fields():
    case=CFG['cells'][0]
    for text in ['{"first_inside":1,"last_inside":false,"all_inside":false}',
        '{"first_inside":true,"first_inside":false,"last_inside":false,"all_inside":false}',
        '{"first_inside":true,"last_inside":false,"all_inside":false,"label":"ALPHA"}']:
        assert not score(text,'stop','exit',case,CFG)['valid_format']


@pytest.mark.parametrize('action',list(TRUTH))
def test_direct_diagonal_anchors_exactly_repeat_prior_prompt_and_orthogonal_factors_are_isolated(action):
    cases={(c['definition_order'],c['allowed_order']):c for c in CFG['cells'] if c['family']=='direct'}
    texts={pair:body(action,c,CFG)['messages'][0]['content'][0]['text'] for pair,c in cases.items()}
    old={c['id']:c for c in OLD['text_cells']}
    assert texts[0,0]==old_prompt(action,old['geom0_json'],OLD)
    assert texts[1,1]==old_prompt(action,old['geom0_json_reordered'],OLD)
    def pieces(text):
        start=text.index('Rectangle ');allowed=text.index('Allowed label tokens:')
        return text[:start],text[start:allowed],text[allowed:]
    for left in [0,1]:
        a,b=pieces(texts[0,left]),pieces(texts[1,left]);assert a[0]!=b[0] and a[1:]==b[1:]
        a,b=pieces(texts[left,0]),pieces(texts[left,1]);assert a[:2]==b[:2] and a[2]!=b[2]


def test_all_wrong_numeric_fields_have_zero_field_score_and_binding_is_ground_truth():
    case=CFG['cells'][0];wrong={k:not v for k,v in TRUTH['exit'].items()}
    assert score(json.dumps(wrong),'stop','exit',case,CFG)['field_correct']==0
    before=body('exit',CFG['cells'][1],CFG)
    # No model-answer argument exists in the binding builder.
    assert json.loads(re.search(r'Facts=(\{[^}]+\})',before['messages'][0]['content'][0]['text'])[1])==TRUTH['exit']


@pytest.mark.parametrize('case_index',[0,1,2])
def test_real_driver_transports_exact_frozen_body_without_schema_or_rendering_calls(case_index):
    import time
    from scripts.qwen_decomposition import execute,record_cell
    case=CFG['cells'][case_index];captured=[]
    class Response:
        status_code=200;content=b'{}'
        def json(self):return {'choices':[{'message':{'content':json.dumps(expected('enter',case,CFG))},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1}}
    class Client:
        def request(self,method,path,**kwargs):captured.append((method,path,kwargs));return Response()
    class Server:client=Client()
    row=record_cell();result=execute(Server(),'enter',case,CFG,time.monotonic()+60,row,set())
    assert result['correct'] and row['completed']==1
    assert len(captured)==1 and captured[0][:2]==('POST','/v1/chat/completions')
    assert captured[0][2]['json']==body('enter',case,CFG)


def test_decomposition_wrapper_rejects_rendering_audit_and_extra_generation():
    from scripts.qwen_decomposition import TextOnlyClient
    class Client:
        def request(self,*args,**kwargs):return None
    client=TextOnlyClient(Client(),'http://127.0.0.1:1')
    for path in ['/apply-template','/props','/api/v1/analyze']:
        with pytest.raises(ValueError):client.request('POST',path)
    for _ in range(18):client.request('POST','/v1/chat/completions')
    with pytest.raises(ValueError):client.request('POST','/v1/chat/completions')


def test_technical_failure_revokes_global_and_cell_semantic_success():
    from scripts.qwen_decomposition import revoke
    result={'compound_quality_assertion_passed':True,'cell_semantic_status':{'facts':'assessed_synthetic_only'}}
    revoke(result,'NativeCleanupError')
    assert not result['compound_quality_assertion_passed'] and result['status']=='failed'
    assert set(result['cell_semantic_status'].values())=={'NOT_ASSESSED_TECHNICAL_FAILURE'}
