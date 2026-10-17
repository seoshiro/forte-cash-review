"""Local constrained output. Frame identifiers resolve only to supplied PTS.

The decoder restricts structure, not the truth of observations. The ordinary
strict validator still rejects invalid output; no response is repaired by an
external service or silently converted into a negative verdict.
"""
import json,string
from .observations import ObservationError,parse_observation


def tokenizer_data(tokenizer):
    """Transformers 5 adapter using the documented LMFE tokenizer-data API.

    Adapted from noamgat/lm-format-enforcer integrations/transformers.py,
    copyright (c) 2023 Noam Gat, MIT. See docs/lmfe-license.txt.
    The published 0.11.3 integration imports a removed Transformers symbol.
    """
    from lmformatenforcer.tokenenforcer import TokenEnforcerTokenizerData
    token_zero=tokenizer.encode('0')[-1];special=set(tokenizer.all_special_ids)
    regular=[]
    for index in range(len(tokenizer)):
        if index in special:continue
        after_zero=tokenizer.decode([token_zero,index])[1:]
        direct=tokenizer.decode([index])
        regular.append((index,after_zero,len(after_zero)>len(direct)))
    def decode(ids):
        return tokenizer.decode(ids,clean_up_tokenization_spaces=False).rstrip('\ufffd')
    return TokenEnforcerTokenizerData(regular,decode,tokenizer.eos_token_id,
                                     False,len(tokenizer))


def prefix_function(data,rule_ids,frame_count):
    from lmformatenforcer.tokenenforcer import TokenEnforcer
    enforcer=TokenEnforcer(data,parser_for(rule_ids,frame_count))
    def allowed(_batch_id,ids):
        return enforcer.get_allowed_tokens(ids.tolist()).allowed_tokens
    return allowed


def output_schema(rule_ids,frame_count):
    event={
        'type':'object','additionalProperties':False,
        'properties':{
            'rule_id':{'type':'string','enum':sorted(rule_ids)},
            'frame_id':{'type':'string','enum':[f'F{i}' for i in range(frame_count)]},
            'confidence':{'type':'number','minimum':0,'maximum':1},
            'all_conditions_visible':{'type':'boolean'},
            'observation':{'type':'string','minLength':1,'maxLength':100},
            'limitation':{'type':'string','maxLength':60},
        },
    }
    event['required']=list(event['properties'])
    return {'type':'object','additionalProperties':False,
            'properties':{'events':{'type':'array','maxItems':4,'items':event},
                          'limitation':{'type':'string','maxLength':100}},
            'required':['events','limitation']}


def parser_for(rule_ids,frame_count):
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.characterlevelparser import CharacterLevelParserConfig
    alphabet=string.printable+''.join(chr(i) for i in range(0x400,0x500))
    return JsonSchemaParser(output_schema(rule_ids,frame_count),
                            config=CharacterLevelParserConfig(alphabet=alphabet,
                                      max_consecutive_whitespaces=2))


def decode_observation(text,rule_ids,frames):
    # No regex extraction or correction: constrained generation must finish JSON.
    try:
        data=json.loads(text)
        if not isinstance(data,dict) or set(data)!={'events','limitation'}:
            raise ValueError()
        if not isinstance(data['events'],list):raise ValueError()
        allowed=set(output_schema(rule_ids,len(frames))['properties']['events']['items']['properties'])
        for event in data['events']:
            if not isinstance(event,dict) or set(event)!=allowed:raise ValueError()
            frame_id=event.pop('frame_id')
            if frame_id not in {f'F{i}' for i in range(len(frames))}:raise ValueError()
            event['timestamp_sec']=float(frames[int(frame_id[1:])].sec)
    except (ValueError,TypeError,KeyError,IndexError):
        raise ObservationError('invalid_constrained_structure') from None
    return parse_observation(json.dumps(data),rule_ids,frames[0].sec,frames[-1].sec)
