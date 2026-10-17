from pathlib import Path
import json,copy,re
import pytest
from hybrid_candidate.discrimination import prompt,request_body,score,extract_response,image_cells,paired,assert_input_present

CFG=json.loads((Path(__file__).resolve().parents[1]/'config/qwen-text-discrimination.json').read_text())
LABELS=[{'exit':'ALPHA','enter':'BETA','stay':'GAMMA'},{'exit':'GAMMA','enter':'ALPHA','stay':'BETA'}]


def cell(name):return next(c for c in CFG['text_cells'] if c['id']==name)


def test_frozen_matrix_is_balanced_and_geometry_matches_independent_old_fixture():
    assert CFG['maps']==LABELS and CFG['actions']==['exit','enter','stay']
    assert len(CFG['text_cells'])*len(CFG['actions'])==36
    assert len(image_cells(CFG))*len(CFG['actions'])==18
    old=json.loads((Path(__file__).resolve().parents[1]/'config/qwen-action-probe.json').read_text())['geometry']
    assert CFG['geometry']=={key:value for key,value in old.items() if key!='montage'}
    for case in CFG['text_cells']:
        assert set(LABELS[case['map']].values())==set(CFG['labels'])


@pytest.mark.parametrize('mapping',[0,1])
@pytest.mark.parametrize('action',['exit','enter','stay'])
@pytest.mark.parametrize('mode',['bare','json','schema'])
def test_known_mock_answers_score_independent_label_mapping(mapping,action,mode):
    case={'id':'mock','family':'geometry','map':mapping,'mode':mode}
    answer=LABELS[mapping][action]
    output=answer if mode=='bare' else json.dumps({'label':answer})
    result=score(output,'stop',action,case,CFG)
    assert result['correct'] and result['valid_format'] and result['semantic']==action
    other=next(x for x in ['exit','enter','stay'] if x!=action)
    assert not score(output,'stop',other,case,CFG)['correct']
    assert not score(output,'length',action,case,CFG)['correct']


@pytest.mark.parametrize('prefix',['read','geom0','geom1'])
@pytest.mark.parametrize('action',['exit','enter','stay'])
def test_json_schema_comparison_changes_only_response_format(prefix,action):
    plain=request_body(action,cell(prefix+'_json'),CFG)
    constrained=request_body(action,cell(prefix+'_schema'),CFG)
    del constrained['response_format']
    assert plain==constrained
    assert not {'expected','action','case_id'}&set(plain)


@pytest.mark.parametrize('action',['exit','enter','stay'])
def test_enum_order_contrast_changes_only_enum_order(action):
    a=request_body(action,cell('geom0_schema'),CFG)
    b=request_body(action,cell('geom0_schema_rotated'),CFG)
    assert a['messages']==b['messages']
    enum=b['response_format']['json_schema']['schema']['properties']['label']['enum']
    assert enum==['BETA','GAMMA','ALPHA']
    b['response_format']['json_schema']['schema']['properties']['label']['enum']=CFG['labels']
    assert a==b


@pytest.mark.parametrize('action',['exit','enter','stay'])
def test_direct_readback_has_literal_selected_token_and_reorder_keeps_geometry(action):
    value=prompt(action,cell('read_bare'),CFG)
    assert 'selected_token='+LABELS[0][action]+'.' in value
    a=prompt(action,cell('geom0_json'),CFG);b=prompt(action,cell('geom0_json_reordered'),CFG)
    assert a!=b
    for fragment in ['Rectangle [left,top,right,bottom]=[24, 24, 180, 232]','disk radius=9','center y=120',
        'ALPHA: starts fully inside and ends fully outside.','BETA: starts fully outside and ends fully inside.','GAMMA: all supplied positions fully inside.']:
        assert fragment in a and fragment in b
    xs=json.loads(re.search(r'ordered center x=(\[[^]]+\])',a)[1])
    assert xs=={'exit':[70,110,165,220],'enter':[220,165,110,70],'stay':[70,95,125,150]}[action]
    first_inside=24<xs[0]-9 and xs[0]+9<180
    last_inside=24<xs[-1]-9 and xs[-1]+9<180
    expected='exit' if first_inside and not last_inside else 'enter' if not first_inside and last_inside else 'stay'
    assert expected==action


@pytest.mark.parametrize('text',['{"label":"ALPHA","label":"BETA"}','{"label":"ALPHA","extra":1}','{"label":null}','{"label":["ALPHA"]}','ALPHA'])
def test_json_format_errors_never_pass_primary_gate(text):
    assert not score(text,'stop','exit',cell('geom0_json'),CFG)['correct']


@pytest.mark.parametrize('choices',[None,[],[{},{}],[None],[{'message':{}}],[{'message':{'content':'ALPHA'},'finish_reason':None}]])
def test_malformed_or_multiple_choices_fail_closed(choices):
    with pytest.raises(ValueError):extract_response({'choices':choices})


def test_truncation_is_explicit_and_cannot_pass_semantic_gate():
    text,finish,_=extract_response({'choices':[{'message':{'content':'ALPHA'},'finish_reason':'length'}]})
    result=score(text,finish,'exit',cell('geom0_bare'),CFG)
    assert result['truncated'] and not result['stop'] and not result['correct']


def test_pair_counts_are_aggregate_and_mapping_comparison_uses_semantics():
    values={}
    for action,label in LABELS[0].items():
        values[('left',action)]={'correct':True,'valid_format':True,'label':label,'semantic':action,'stop':True,'truncated':False}
        values[('right',action)]={'correct':True,'valid_format':True,'label':LABELS[1][action],'semantic':action,'stop':True,'truncated':False}
    result=paired(values,[('left','right')])
    assert result=={'pairs':3,'assessed_pairs':3,'unassessed_pairs':0,'invalid_format_pairs':0,'truncated_pairs':0,
        'both_correct':3,'only_one_correct':0,'neither_correct':0,'label_changed':3,'semantic_changed':0}
    values[('right','exit')].update(stop=False,truncated=True,correct=False)
    result=paired(values,[('left','right')])
    assert result['truncated_pairs']==result['unassessed_pairs']==1
    assert result['assessed_pairs']==result['label_changed']==result['both_correct']==2 and result['only_one_correct']==0


def test_rendered_input_presence_is_checked_independently_of_expected_renderer():
    messages=[{'role':'user','content':[{'type':'text','text':'SYNTH_FIRST'},
        {'type':'image_url','image_url':{'url':'generated'}},{'type':'text','text':'SYNTH_LAST'}]}]
    assert_input_present('SYNTH_FIRSTMARKSYNTH_LAST',messages,'MARK')
    for invalid in ['MARKSYNTH_LAST','SYNTH_FIRSTMARKMARKSYNTH_LAST','SYNTH_LASTMARKSYNTH_FIRST','SYNTH_FIRSTSYNTH_LASTMARK']:
        with pytest.raises(ValueError):assert_input_present(invalid,messages,'MARK')


def test_cleanup_failure_revokes_all_previous_semantic_success_fields():
    from scripts.qwen_text_discrimination import mark_technical_failure
    result={'status':'completed','compound_quality_assertion_passed':True,'text_gate_passed':True,'image_gate_passed':True}
    mark_technical_failure(result,'NativeCleanupError')
    assert result['status']=='failed' and result['semantic_assertion']=='NOT_ASSESSED'
    assert not result['compound_quality_assertion_passed'] and result['text_gate_passed'] is None and result['image_gate_passed'] is None
