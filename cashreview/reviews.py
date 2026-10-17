"""Private manual decisions; immutable automatic predictions stay separate."""
from pathlib import Path
from datetime import datetime,timezone
from typing import Literal
import hashlib,json
from pydantic import BaseModel,ConfigDict,Field
from filelock import FileLock

class ReviewDecision(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    decision:Literal['confirmed','rejected','insufficient_data']
    note:str=Field(default='',max_length=800)

class ReviewConflict(ValueError):pass

def context_for(event,detail,duration):
    context=detail.get('context')
    if isinstance(context,dict) and context.get('status') in ['reviewed','limited','pending']:
        return context
    # Existing uniform results have no explicit fine-context confirmation.
    return {'status':'limited','result':'Детальная повторная проверка контекста моделью не подтверждена.',
            'limitation':'Проверьте исходный фрагмент до и после события вручную.',
            'start_sec':max(0,event['timecode_sec']-3),
            'end_sec':min(duration,event['timecode_sec']+3)}

def state(folder,result,detail):
    folder=Path(folder);digest=hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()
    try:saved=json.loads((folder/'reviews.json').read_text(encoding='utf-8'))
    except FileNotFoundError:saved={'prediction_sha256':digest,'reviews':{}}
    if saved['prediction_sha256']!=digest:raise ReviewConflict('Automatic result changed; manual decisions require reconciliation')
    details=detail.get('events') or [];contexts=[]
    for index,event in enumerate(result['violations']):
        item=details[index] if index<len(details) else {}
        contexts.append(context_for(event,item,detail.get('duration_sec',event['timecode_sec']+3)))
    ready=all(c['status']!='pending' for c in contexts)
    unreviewed=sum(str(i) not in saved['reviews'] for i in range(len(result['violations'])))
    return {'job_id':result['job_id'],'ready':ready,'prediction_sha256':digest,
            'reviews':saved['reviews'],'contexts':contexts,
            'notification':{'kind':'review_ready','event_count':len(contexts),'unreviewed_count':unreviewed} if ready and contexts else None}

def save(folder,result,detail,event_index,decision,owner):
    folder=Path(folder)
    with FileLock(str(folder/'reviews.lock'),timeout=2):
        current=state(folder,result,detail)
        if not current['ready']:raise ReviewConflict('Context check is not complete')
        if not 0<=event_index<len(result['violations']):raise IndexError('Unknown event')
        current['reviews'][str(event_index)]={'decision':decision.decision,'note':decision.note,
              'updated_utc':datetime.now(timezone.utc).isoformat(),'reviewer_owner':owner}
        payload={'version':1,'prediction_sha256':current['prediction_sha256'],'reviews':current['reviews'],
                 'training_use':False}
        temporary=folder/'reviews.tmp';temporary.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');temporary.replace(folder/'reviews.json')
        return state(folder,result,detail)
