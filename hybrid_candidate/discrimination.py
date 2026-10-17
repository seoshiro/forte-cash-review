"""Fixed synthetic cases and strict independent-label scoring; no private input."""
import json,re,copy,base64
from io import BytesIO
from hybrid_candidate.action_controls import frames


def positions(action,cfg):
    values=cfg['geometry']['stay_x'] if action=='stay' else cfg['geometry']['exit_x']
    if action not in cfg['actions']:raise ValueError('Unapproved synthetic action')
    return list(reversed(values)) if action=='enter' else list(values)


def prompt(action,cell,cfg):
    mapping=cfg['maps'][cell['map']]
    labels=list(cfg['labels']);actions=list(cfg['actions'])
    if cell.get('reorder_prompt'):labels=labels[1:]+labels[:1];actions=actions[1:]+actions[:1]
    allowed=', '.join(labels)
    if cell['family']=='readback':
        task='Synthetic token-copy task. selected_token='+mapping[action]+'. Copy the selected_token exactly. '
    else:
        definitions={'exit':'starts fully inside and ends fully outside','enter':'starts fully outside and ends fully inside','stay':'all supplied positions fully inside'}
        rules=' '.join(mapping[a]+': '+definitions[a]+'.' for a in actions)
        task='Synthetic red-disk region motion. '+rules+' '
        if cell['family']=='geometry':
            g=cfg['geometry']
            task+='Rectangle [left,top,right,bottom]='+json.dumps(g['boundary_xyxy'])+'; disk radius='+str(g['disk_radius'])+'; center y='+str(g['y'])+'; ordered center x='+json.dumps(positions(action,cfg))+'. '
        elif cell['family']=='images':task+='Use four supplied images in chronological order F0, F1, F2, F3. '
        else:raise ValueError('Unapproved synthetic task family')
    if cell['mode']=='bare':return task+'Allowed label tokens: '+allowed+'. Return exactly one allowed label token, without explanation.'
    return task+'Allowed label tokens: '+allowed+'. Return only a JSON object with exactly one string field named label, whose value is one allowed token. No explanation.'


def schema(cell,cfg):
    labels=list(cfg['labels'])
    if cell.get('rotate_enum'):labels=labels[1:]+labels[:1]
    return {'type':'object','additionalProperties':False,'properties':{'label':{'type':'string','enum':labels}},'required':['label']}


def messages(action,cell,cfg):
    content=[]
    if cell['family']=='images':
        for index,image in enumerate(frames(action,cfg)):
            stream=BytesIO();image.save(stream,'JPEG',quality=cfg['inference']['jpeg_quality'])
            content.extend([{'type':'text','text':'F'+str(index)+':'},
                {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode('ascii')}}])
    content.append({'type':'text','text':prompt(action,cell,cfg)})
    return [{'role':'user','content':content}]


def request_body(action,cell,cfg):
    c=cfg['inference']
    body={'messages':messages(action,cell,cfg),'temperature':c['temperature'],'seed':c['seed'],
        'max_tokens':c['max_tokens'],'cache_prompt':False,'stream':False,'n':1}
    if cell['mode']=='schema':body['response_format']={'type':'json_schema','json_schema':{'schema':schema(cell,cfg)}}
    return body


def image_cells(cfg):
    return [{'id':'image'+str(mapping)+'_'+mode,'family':'images','map':mapping,'mode':mode} for mapping in range(len(cfg['maps'])) for mode in ['bare','json','schema']]


def no_duplicate_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate response field')
        result[key]=value
    return result


def score(text,finish,action,cell,cfg):
    if not isinstance(text,str):raise ValueError('Missing synthetic response string')
    label=None;valid=False
    if cell['mode']=='bare':
        label=text.strip();valid=label in cfg['labels']
    else:
        try:
            value=json.loads(text,object_pairs_hook=no_duplicate_keys)
            valid=isinstance(value,dict) and set(value)=={'label'} and isinstance(value['label'],str) and value['label'] in cfg['labels']
            if valid:label=value['label']
        except (ValueError,TypeError):pass
    # Secondary diagnostic only. It never rescues the strict primary gate.
    present=set(re.findall(r'\b(?:ALPHA|BETA|GAMMA)\b',text))
    recognized=next(iter(present)) if len(present)==1 else None
    inverse={label:semantic for semantic,label in cfg['maps'][cell['map']].items()}
    expected=cfg['maps'][cell['map']][action]
    return {'valid_format':valid,'label':label if valid else None,'semantic':inverse.get(label) if valid else None,
        'correct':bool(valid and label==expected and finish=='stop'),'recognized_correct':recognized==expected and finish=='stop',
        'stop':finish=='stop','truncated':finish=='length'}


def extract_response(value):
    choices=value.get('choices')
    if not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict):raise ValueError('Expected exactly one choice')
    choice=choices[0];message=choice.get('message')
    if not isinstance(message,dict) or not isinstance(message.get('content'),str):raise ValueError('Missing content')
    if choice.get('finish_reason') not in ['stop','length']:raise ValueError('Unexpected finish reason')
    usage=value.get('usage',{})
    return message['content'],choice['finish_reason'],{k:usage.get(k) for k in ['prompt_tokens','completion_tokens']}


def assert_input_present(actual,messages,marker):
    if not isinstance(actual,str) or not isinstance(marker,str) or not marker:raise ValueError('Unexpected rendered input')
    sequence=[];images=0
    for message in messages:
        for part in message['content']:
            if part['type']=='text':
                text=part['text']
                if not text or actual.count(text)!=1:raise ValueError('Missing or duplicated synthetic text')
                sequence.append(text)
            elif part['type']=='image_url':images+=1;sequence.append(marker)
            else:raise ValueError('Unexpected synthetic content type')
    if actual.count(marker)!=images:raise ValueError('Image count mismatch')
    cursor=0
    for value in sequence:
        found=actual.find(value,cursor)
        if found<0:raise ValueError('Rendered content order mismatch')
        cursor=found+len(value)


def paired(results,pairs):
    total={'pairs':0,'assessed_pairs':0,'unassessed_pairs':0,'invalid_format_pairs':0,'truncated_pairs':0,
        'both_correct':0,'only_one_correct':0,'neither_correct':0,'label_changed':0,'semantic_changed':0}
    for left,right in pairs:
        for action in ['exit','enter','stay']:
            a=results[(left,action)];b=results[(right,action)];total['pairs']+=1
            valid=a['valid_format'] and b['valid_format'];stopped=a['stop'] and b['stop']
            total['invalid_format_pairs']+=int(not valid);total['truncated_pairs']+=int(a['truncated'] or b['truncated'])
            if not valid or not stopped:total['unassessed_pairs']+=1;continue
            total['assessed_pairs']+=1
            total['both_correct']+=int(a['correct'] and b['correct']);total['only_one_correct']+=int(a['correct']!=b['correct'])
            total['neither_correct']+=int(not a['correct'] and not b['correct']);total['label_changed']+=int(a['label']!=b['label'])
            total['semantic_changed']+=int(a['semantic']!=b['semantic'])
    return total
