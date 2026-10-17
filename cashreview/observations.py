"""Validate local model output without exposing its content in exceptions."""
import json,re
from pydantic import BaseModel,Field,ConfigDict,ValidationError


class ObservationError(ValueError):
    def __init__(self,code):
        self.code=code
        super().__init__('Local model output rejected: '+code)


class Event(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    rule_id:str
    timestamp_sec:float=Field(ge=0)
    confidence:float=Field(ge=0,le=1)
    all_conditions_visible:bool
    observation:str=Field(min_length=1,max_length=1200)
    limitation:str=Field(default='',max_length=1200)


class Observation(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    events:list[Event]=Field(max_length=4)
    limitation:str=Field(default='',max_length=1600)


def parse_observation(text,rule_ids,low,high):
    match=re.search(r'\{.*\}',text,re.S)
    if not match:raise ObservationError('invalid_json')
    try:result=Observation.model_validate(json.loads(match[0])).model_dump()
    except (ValueError,ValidationError,TypeError):raise ObservationError('invalid_structure') from None
    if any(e['rule_id'] not in rule_ids for e in result['events']):raise ObservationError('unverified_rule')
    if any(not low<=e['timestamp_sec']<=high for e in result['events']):raise ObservationError('time_outside_window')
    return result
