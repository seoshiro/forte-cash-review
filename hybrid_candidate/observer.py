"""No labels/names in observation inference. Generated text remains private."""
import json
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal


class Facts(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    area:Literal['clear','unclear']
    motion:Literal['left','stayed','unclear']
    service:Literal['ongoing','completed','unclear']
    context:Literal['sufficient','insufficient']
    f:int=Field(ge=0,le=3)
    e:list[int]=Field(max_length=3)
    o:str=Field(max_length=160)


def schema():return Facts.model_json_schema()


def parse(text):
    try:
        value=Facts.model_validate(json.loads(text)).model_dump()
        if any(type(i) is not int or not 0<=i<=3 for i in value['e']) or len(set(value['e']))!=len(value['e']):raise ValueError()
        return value
    except Exception:raise ValueError('Invalid local observation structure') from None


def apply_rule(value):
    # The source is NB231 p22; rising from a chair is not leaving a workplace,
    # a waiting person alone does not establish unfinished client service.
    matched=(value['area']=='clear' and value['motion']=='left' and value['service']=='ongoing'
        and value['context']=='sufficient' and len(set(value['e']))>=2 and value['f'] in value['e']
        and min(value['e'])<value['f'] and bool(value['o'].strip()))
    return 'R22' if matched else 'no_event'


def prompt():
    return ('Observe only physical facts in the ordered sequence, or in the explicitly fictional text supplied for a diagnostic. '
        'Do not decide whether there is a violation. Do not identify faces or personal identities, use audio, infer intent, hidden records or unseen activity. '
        'area=clear only when the working area boundary and the person operating that station are visually established; otherwise unclear. '
        'motion=left only for a visible departure beyond that working area, not standing up, shifting position or merely leaving a chair; stayed if the operator remains within it, else unclear. '
        'service=ongoing only when client service is visibly still in progress at departure, or throughout the supplied sequence if there is no departure. A person waiting alone does not establish unfinished service. '
        'Use completed for visibly finished service; use unclear when its state cannot be established. '
        'context=sufficient only if the supplied before/after sequence supports these facts; insufficient for ambiguity or missing context. '
        'Return JSON keys area,motion,service,context,f,e,o only. f is the nearest supplied frame index0..3, e is0..3 distinct supporting frame indices (up to3). '
        'o is a short physical observation in English, <=160 characters, no legal conclusion. If unclear, retain unclear/insufficient and avoid inventing facts. '
        'An empty support list and empty observation are permitted. No markdown or extra keys.')


def select_proposals(features,times,positive,negative,top_k,separation):
    import numpy as np
    from xclip_candidate.evaluate import unit
    vectors=unit(features);scores=vectors@positive-vectors@negative;selected=[]
    # No oracle time, target or source ID accepted. All scores are eligible.
    for index in np.argsort(-scores,kind='stable'):
        center=float(times[index])
        if all(abs(center-float(times[old]))>=separation for old in selected):selected.append(int(index))
        if len(selected)==top_k:break
    return selected
