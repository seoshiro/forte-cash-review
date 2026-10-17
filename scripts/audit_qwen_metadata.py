"""Static public GGUF-header audit only; no inference, template execution or media."""
from pathlib import Path
import struct,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from xclip_candidate.experimental import sha
FORMATS={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
KEYS={'general.type','general.architecture','general.name','general.finetune','general.basename','general.size_label','general.license',
    'general.base_model.0.name','general.base_model.0.repo_url','clip.projector_type','clip.has_vision_encoder',
    'clip.has_text_encoder','clip.vision.image_size','clip.vision.patch_size','tokenizer.chat_template'}


def header(path):
    with Path(path).open('rb') as stream:
        file_bytes=Path(path).stat().st_size
        def skip(size):
            if stream.tell()+size>file_bytes:raise ValueError('Truncated public GGUF payload')
            if stream.tell()+size>256*1024*1024:raise ValueError('GGUF header byte bound')
            stream.seek(size,1)
        def scalar(fmt):
            size=struct.calcsize('<'+fmt);value=stream.read(size)
            if len(value)!=size:raise ValueError('Truncated public GGUF header')
            return struct.unpack('<'+fmt,value)[0]
        def string(capture):
            size=scalar('Q')
            if size>32*1024*1024:raise ValueError('GGUF string bound exceeded')
            if capture:
                value=stream.read(size)
                if len(value)!=size:raise ValueError('Truncated public GGUF string')
                return value.decode('utf-8')
            skip(size)
        def value(kind,capture=False,depth=0):
            if depth>2:raise ValueError('GGUF array nesting bound')
            if kind==8:return string(capture)
            if kind==9:
                item=scalar('I');count=scalar('Q')
                if count>2_000_000:raise ValueError('GGUF array count bound')
                if item in FORMATS:skip(struct.calcsize('<'+FORMATS[item])*count)
                else:
                    for _ in range(count):value(item,False,depth+1)
                return None
            if kind not in FORMATS:raise ValueError('Unsupported GGUF value type')
            result=scalar(FORMATS[kind]);return result if capture else None
        if stream.read(4)!=b'GGUF' or scalar('I')!=3:raise ValueError('Expected public GGUFv3')
        tensors=scalar('Q');count=scalar('Q')
        if count>10000:raise ValueError('GGUF metadata count bound')
        selected={}
        for _ in range(count):
            key=string(True);kind=scalar('I');result=value(kind,key in KEYS)
            if key in KEYS:selected[key]=result
            if stream.tell()>256*1024*1024:raise ValueError('GGUF header byte bound')
        return {'tensor_count':tensors,'metadata_count':count,'header_bytes_read':stream.tell(),'metadata':selected}


def main():
    cfg=json.loads((ROOT/'config/gguf-artifacts.json').read_text());records={}
    for row in cfg['artifacts']:
        if row['kind']!='model':continue
        path=ROOT/'models/qwen3vl-4b-gguf'/row['filename']
        if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:raise ValueError('Official public artifact mismatch')
        record=header(path);template=record['metadata'].pop('tokenizer.chat_template',None)
        record['template_present']=isinstance(template,str)
        if isinstance(template,str):
            record['template_chars']=len(template);record['template_sha256']=hashlib.sha256(template.encode()).hexdigest()
            record['template_markers']={name:token in template for name,token in {
                'chatml_start':'<|im_start|>','assistant_role':'assistant','user_role':'user','generation_prompt':'add_generation_prompt',
                'image_marker':'<|image_pad|>','vision_start':'<|vision_start|>','thinking_tag':'<think>',
                'thinking_switch':'enable_thinking'}.items()}
        records['projector' if row['filename'].startswith('mmproj') else 'language']=record
    result={'status':'completed','split':'technical','official_artifact_sha_and_size_match':True,'records':records,
        'model_or_server_started':False,'bank_data_or_private_answers_read':False,'template_rendered_by_actual_runtime':False,
        'causal_mismatch_found':False,'limitation':'Static metadata and marker presence do not prove correct runtime rendering or explain model errors.'}
    out=ROOT/'.private/qwen-static-audit';out.mkdir(exist_ok=True)
    (out/'safe-summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
