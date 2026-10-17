"""Prospective independent numeric/fact/binding synthetic controls."""
import json
from hybrid_candidate.discrimination import positions,no_duplicate_keys

KEYS=['first_inside','last_inside','all_inside']


def expected_facts(action,cfg):
    left,top,right,bottom=cfg['geometry']['boundary_xyxy'];r=cfg['geometry']['disk_radius'];y=cfg['geometry']['y']
    flags=[left<x-r and x+r<right and top<y-r and y+r<bottom for x in positions(action,cfg)]
    return dict(zip(KEYS,[flags[0],flags[-1],all(flags)]))


def coordinate_text(action,cfg):
    g=cfg['geometry']
    return 'Rectangle [left,top,right,bottom]='+json.dumps(g['boundary_xyxy'])+'; disk radius='+str(g['disk_radius'])+'; center y='+str(g['y'])+'; ordered center x='+json.dumps(positions(action,cfg))+'. '


def prompt(action,case,cfg):
    if case['family']=='facts':
        return ('Compute facts for a synthetic disk. Fully inside means x-radius>left AND x+radius<right AND y-radius>top AND y+radius<bottom. '
            +coordinate_text(action,cfg)+'Return only a JSON object with exactly three Boolean fields: first_inside for the first supplied position, '
            'last_inside for the last supplied position, all_inside for whether every supplied position is fully inside. No explanation.')
    if case['family']=='binding':
        return ('Classify supplied Boolean facts. ALPHA if first_inside=true and last_inside=false; BETA if first_inside=false and last_inside=true; '
            'GAMMA if all_inside=true. Select the matching condition. Facts='+json.dumps(expected_facts(action,cfg),sort_keys=True)+'. '
            'Allowed label tokens: ALPHA, BETA, GAMMA. Return only a JSON object with exactly one string field named label, whose value is one allowed token. No explanation.')
    if case['family']!='direct':raise ValueError('Unknown synthetic family')
    mapping=cfg['maps'][0];actions=list(cfg['actions']);labels=list(cfg['labels'])
    if case['definition_order']:actions=actions[1:]+actions[:1]
    if case['allowed_order']:labels=labels[1:]+labels[:1]
    definitions={'exit':'starts fully inside and ends fully outside','enter':'starts fully outside and ends fully inside','stay':'all supplied positions fully inside'}
    return ('Synthetic red-disk region motion. '+' '.join(mapping[a]+': '+definitions[a]+'.' for a in actions)+' '+coordinate_text(action,cfg)
        +'Allowed label tokens: '+', '.join(labels)+'. Return only a JSON object with exactly one string field named label, whose value is one allowed token. No explanation.')


def body(action,case,cfg):
    c=cfg['inference']
    return {'messages':[{'role':'user','content':[{'type':'text','text':prompt(action,case,cfg)}]}],
        'temperature':c['temperature'],'seed':c['seed'],'max_tokens':c['max_tokens'],'cache_prompt':False,'stream':False,'n':1}


def expected(action,case,cfg):return expected_facts(action,cfg) if case['family']=='facts' else {'label':cfg['maps'][0][action]}


def score(text,finish,action,case,cfg):
    value=None;valid=False;field_correct=0;label=None;fact_code=None
    try:
        value=json.loads(text,object_pairs_hook=no_duplicate_keys)
        if case['family']=='facts':
            valid=isinstance(value,dict) and set(value)==set(KEYS) and all(type(value[k]) is bool for k in KEYS)
            if valid:
                field_correct=sum(value[k]==expected_facts(action,cfg)[k] for k in KEYS)
                fact_code=''.join('1' if value[k] else '0' for k in KEYS)
        else:
            valid=isinstance(value,dict) and set(value)=={'label'} and type(value['label']) is str and value['label'] in cfg['labels']
            if valid:label=value['label']
    except (ValueError,TypeError):pass
    field_matches={k:int(valid and finish=='stop' and value[k]==expected_facts(action,cfg)[k]) for k in KEYS} if case['family']=='facts' else {}
    return {'valid_format':valid,'correct':bool(valid and value==expected(action,case,cfg) and finish=='stop'),
        'field_correct':field_correct if finish=='stop' else 0,'field_matches':field_matches,
        'label':label,'semantic':{'ALPHA':'exit','BETA':'enter','GAMMA':'stay'}.get(label),
        'fact_code':fact_code,'stop':finish=='stop','truncated':finish=='length'}
