import json
from types import SimpleNamespace
import pytest
from cashreview.structured import parser_for,decode_observation


def synthetic_event():
    return {'rule_id':'R22','frame_id':'F1','confidence':.9,
            'all_conditions_visible':True,'observation':'Тестовая схема.',
            'limitation':''}


def accepted(text):
    parser=parser_for({'R22'},2)
    for char in text:
        if char not in parser.get_allowed_characters():return False
        parser=parser.add_character(char)
    return parser.can_end()


def test_grammar_allows_russian_and_restricts_ids_and_structure():
    data={'events':[synthetic_event()],'limitation':''}
    assert accepted(json.dumps(data,ensure_ascii=False))
    data['events'][0]['frame_id']='F9'
    assert not accepted(json.dumps(data))
    data['events'][0]['frame_id']='F1';data['events'][0]['rule_id']='INVENTED'
    assert not accepted(json.dumps(data))
    assert not accepted('{"events":[],"limitation":""')


def test_frame_id_maps_exactly_to_supplied_pts_and_never_rounds():
    frames=[SimpleNamespace(sec=.033333333),SimpleNamespace(sec=7.016666667)]
    data={'events':[synthetic_event()],'limitation':''}
    assert decode_observation(json.dumps(data),{'R22'},frames)['events'][0]['timestamp_sec']==frames[1].sec
    data['events'][0]['frame_id']='F99'
    with pytest.raises(ValueError,match='invalid_constrained_structure'):
        decode_observation(json.dumps(data),{'R22'},frames)


def test_grammar_caps_text_events_and_preserves_strict_numeric_validator():
    data={'events':[synthetic_event()],'limitation':''}
    data['events'][0]['observation']='a'*101
    assert not accepted(json.dumps(data))
    data['events']=[synthetic_event() for _ in range(5)]
    assert not accepted(json.dumps(data))
    data['events']=[synthetic_event()];data['events'][0]['confidence']=2.0
    with pytest.raises(ValueError,match='invalid_structure'):
        decode_observation(json.dumps(data),{'R22'},[SimpleNamespace(sec=0.),SimpleNamespace(sec=1.)])
