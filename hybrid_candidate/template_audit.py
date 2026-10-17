"""Strict expected rendering and synthetic-only message fixtures; no inference."""
import copy,hashlib,base64,re
from io import BytesIO
from jinja2 import StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment


def digest_text(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()


def compile_expected(template):
    env=ImmutableSandboxedEnvironment(undefined=StrictUndefined,trim_blocks=True,lstrip_blocks=True,extensions=['jinja2.ext.loopcontrols'])
    def fail(*args):raise ValueError('Expected public template rejected synthetic input')
    env.globals['raise_exception']=fail
    return env.from_string(template)


def normalize_server_messages(messages,marker):
    """Pinned common/chat.cpp: media parts concatenate without adjacent newline."""
    result=copy.deepcopy(messages)
    for message in result:
        # llama.cpp's optional message fields have empty/false semantics.
        # Supply these explicitly so StrictUndefined never silently guesses.
        message.setdefault('tool_calls',[])
        message.setdefault('reasoning_content','')
        parts=message['content']
        if not isinstance(parts,list) or not any(p['type']=='image_url' for p in parts):continue
        text='';last_media=False
        for part in parts:
            if part['type']=='image_url':value=marker;newline=False;last_media=True
            elif part['type']=='text':value=part['text'];newline=not last_media and bool(text);last_media=False
            else:raise ValueError('Unsupported synthetic part')
            if newline:text+='\n'
            text+=value
        message['content']=text
    return result


def expected_prompt(renderer,messages,props,generation=True):
    return renderer.render(messages=normalize_server_messages(messages,props['media_marker']),tools=None,
        bos_token=props['bos_token'],eos_token=props['eos_token'],add_generation_prompt=generation,
        add_vision_id=False,enable_thinking=False)


def cases(cfg):
    from hybrid_candidate.action_controls import frames,montage,text_positions
    images=frames('exit',cfg)
    def content(values):
        parts=[]
        for index,image in enumerate(values):
            stream=BytesIO();image.save(stream,'JPEG',quality=95)
            parts.extend([{'type':'text','text':'SYNTH_F'+str(index)+':'},
                {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode('ascii')}}])
        parts.append({'type':'text','text':'SYNTH_USER_FINAL'});return parts
    user={'role':'user','content':'SYNTH_USER_FINAL'}
    return [
        {'id':'user_typed_text','messages':[{'role':'user','content':[{'type':'text','text':text_positions('exit',cfg)}]}],
            'generation':True,'images':0,'sentinels':['Fictional coordinate control.']},
        {'id':'system_user','messages':[{'role':'system','content':'SYNTH_SYSTEM'},user],'generation':True,'images':0,'sentinels':['SYNTH_SYSTEM','SYNTH_USER_FINAL']},
        {'id':'multi_turn','messages':[{'role':'user','content':'SYNTH_USER_FIRST'},{'role':'assistant','content':'SYNTH_ASSISTANT'},user],
            'generation':True,'images':0,'sentinels':['SYNTH_USER_FIRST','SYNTH_ASSISTANT','SYNTH_USER_FINAL']},
        {'id':'four_images','messages':[{'role':'user','content':content(images)}],'generation':True,'images':4,
            'sentinels':['SYNTH_F0:','SYNTH_F1:','SYNTH_F2:','SYNTH_F3:','SYNTH_USER_FINAL']},
        {'id':'montage','messages':[{'role':'user','content':content([montage(images)])}],'generation':True,'images':1,
            'sentinels':['SYNTH_F0:','SYNTH_USER_FINAL']},
        {'id':'no_generation_suffix','messages':[user],'generation':False,'images':0,'sentinels':['SYNTH_USER_FINAL']}
    ]


def compare_prompt(actual,expected,case,marker):
    if not isinstance(actual,str):raise TypeError('Unsupported apply-template prompt shape')
    roles=re.findall(r'<\|im_start\|>([a-z]+)\n',actual)
    expected_roles=[m['role'] for m in case['messages']]+(['assistant'] if case['generation'] else [])
    indices=[actual.find(value) for value in case['sentinels']]
    suffix=actual.endswith('<|im_start|>assistant\n')
    result={'byte_equal_expected':actual==expected,'actual_prompt_sha256':digest_text(actual),'expected_prompt_sha256':digest_text(expected),
        'role_sequence_matches':roles==expected_roles,'marker_count':actual.count(marker),'expected_image_count':case['images'],
        'marker_count_matches':actual.count(marker)==case['images'],'sentinel_order_matches':all(i>=0 for i in indices) and indices==sorted(indices),
        'sentinels_exactly_once':all(actual.count(value)==1 for value in case['sentinels']),
        'generation_suffix_matches':suffix==case['generation'],'actual_chars':len(actual),'expected_chars':len(expected)}
    result['all_checks_passed']=all(result[k] for k in ['byte_equal_expected','role_sequence_matches','marker_count_matches','sentinel_order_matches','sentinels_exactly_once','generation_suffix_matches'])
    return result
