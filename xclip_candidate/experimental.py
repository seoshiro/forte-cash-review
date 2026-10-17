"""Explicit binary research integration. No semantic type/rule inference."""
from pathlib import Path
from typing import Literal
import json,hashlib,time,importlib.metadata as metadata,psutil
import numpy as np
from pydantic import BaseModel,ConfigDict,Field,model_validator
from cashreview.schemas import Evidence
from .evaluate import score_video
ROOT=Path(__file__).resolve().parents[1]
FROZEN_INPUTS=['config/xclip-protocol.json','config/xclip-artifacts.json','xclip_candidate/features.py',
    'xclip_candidate/evaluate.py','cashreview/video.py','xclip_candidate/experimental.py']
MODEL_DIRECTORY='models/xclip-base-patch32'
MODEL_FILES=['config.json','preprocessor_config.json','provenance.json','model.safetensors','README.md']
PACK_DIRECTORY='.private/xclip-experimental-v2'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def encoder_artifacts():
    """Reject alternate configs/code as well as changes to the registered inputs."""
    directory=ROOT/MODEL_DIRECTORY;entries=list(directory.iterdir())
    if {p.name for p in entries}!=set(MODEL_FILES) or any(not p.is_file() or p.is_symlink() for p in entries):raise ValueError('Unexpected local encoder artifact inventory')
    return {MODEL_DIRECTORY+'/'+name:sha(directory/name) for name in MODEL_FILES}


class BinaryResearchResult(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    job_id:str
    status:Literal['done']='done'
    mode:Literal['xclip_experimental']='xclip_experimental'
    binary_decision:Literal['violation','no_violation']
    decision_margin:float
    threshold:Literal[0.0]=0.0
    event_type_status:Literal['unverified']='unverified'
    rule_application_status:Literal['not_assessed']='not_assessed'
    candidate_timecode_sec:float|None=Field(default=None,ge=0)
    candidate_frames:list[Evidence]=Field(default_factory=list,max_length=3)
    duration_sec:float=Field(gt=0)
    elapsed_engine_sec:float=Field(ge=0)
    release_eligible:Literal[False]=False
    limitation:Literal['Binary research candidate only; type, physical explanation and legal rule are unverified. No complete multi-event detection claim.']='Binary research candidate only; type, physical explanation and legal rule are unverified. No complete multi-event detection claim.'

    @model_validator(mode='after')
    def consistent(self):
        positive=self.binary_decision=='violation'
        if positive!=(self.decision_margin>=0):raise ValueError('Binary decision does not match frozen threshold')
        if positive!=(self.candidate_timecode_sec is not None) or positive!=bool(self.candidate_frames):raise ValueError('Candidate support missing or unexpected')
        if self.candidate_timecode_sec is not None:
            if self.candidate_timecode_sec>self.duration_sec or not any(abs(f.timestamp_sec-self.candidate_timecode_sec)<1e-6 for f in self.candidate_frames):raise ValueError('Candidate point must be an actual supplied frame')
        if any(f.timestamp_sec>self.duration_sec for f in self.candidate_frames):raise ValueError('Frame outside source')
        return self


def load_prototypes(directory):
    directory=Path(directory);record=json.loads((directory/'prototypes.json').read_text())
    if record.get('schema_version')!=2:raise ValueError('Prototype schema must pin complete encoder artifacts')
    if record['arm']!='ordered' or record['pooling']!='max' or type(record['threshold']) is not float or record['threshold']!=0.0 or record['release_eligible'] is not False:raise ValueError('Unexpected experimental prototype contract')
    if set(record['frozen_code_sha256'])!=set(FROZEN_INPUTS):raise ValueError('Prototype input inventory mismatch')
    if any(sha(ROOT/name)!=digest for name,digest in record['frozen_code_sha256'].items()):raise ValueError('Prototype encoder/scorer changed')
    if encoder_artifacts()!=record['encoder_artifact_sha256']:raise ValueError('Prototype encoder artifacts changed')
    if set(record['versions'])!={'torch','transformers','numpy','av'} or {name:metadata.version(name) for name in record['versions']}!=record['versions']:raise ValueError('Prototype runtime versions changed')
    path=directory/'prototypes.npz'
    if sha(path)!=record['prototype_sha256']:raise ValueError('Prototype artifact changed')
    with np.load(path,allow_pickle=False) as data:
        if set(data.files)!={'positive','negative'}:raise ValueError('Only two fixed prototypes allowed')
        positive=np.array(data['positive']);negative=np.array(data['negative'])
    for vector in [positive,negative]:
        if vector.shape!=(512,) or not np.isfinite(vector).all() or abs(np.linalg.norm(vector)-1)>.001:raise ValueError('Invalid prototype')
    return positive,negative


class ExperimentalEngine:
    def __init__(self,directory=None,deadline=None):
        self.started=time.monotonic();self.deadline=self.started+295 if deadline is None else float(deadline)
        self.positive,self.negative=load_prototypes(directory or ROOT/PACK_DIRECTORY)
        self.cfg=json.loads((ROOT/'config/xclip-protocol.json').read_text())
        self.check()
        from .features import Encoder
        self.encoder=Encoder(ROOT,self.cfg,self.check)

    def check(self):
        if time.monotonic()>=self.deadline:raise TimeoutError('Experimental engine deadline exceeded')
        peak=getattr(psutil.Process().memory_info(),'peak_wset',None)
        if peak is None or peak/2**20>self.cfg['budget']['max_process_rss_mib']:raise RuntimeError('Experimental process memory budget exceeded')
        if hasattr(self,'encoder') and self.encoder.torch.cuda.max_memory_reserved()/2**20>self.cfg['budget']['max_torch_reserved_mib']:raise RuntimeError('Experimental GPU memory budget exceeded')

    def analyze(self,path,job_id):
        from .features import extract
        from cashreview.video import validate_input,sample
        from io import BytesIO
        import base64
        self.check();path=Path(path);info=validate_input(path)
        features=extract(self.encoder,path,self.cfg);self.check()
        margin,center=score_video(features['ordered'],features['times'],self.positive,self.negative,'max')
        frames=[];sec=None
        if margin>=0:
            targets=[max(0.,center-1),center,min(info['duration_sec']-.05,center+1)]
            values=sample(path,sorted(set(targets)),max_side=768)
            if not values:raise ValueError('Candidate frames unavailable')
            sec=min(values,key=lambda f:abs(f.sec-center)).sec
            for value in values:
                buffer=BytesIO();value.image.save(buffer,'JPEG',quality=90)
                frames.append({'timestamp_sec':float(value.sec),'image_base64':base64.b64encode(buffer.getvalue()).decode('ascii')})
        self.check()
        return BinaryResearchResult(job_id=job_id,binary_decision='violation' if margin>=0 else 'no_violation',decision_margin=margin,
            candidate_timecode_sec=sec,candidate_frames=frames,duration_sec=float(info['duration_sec']),elapsed_engine_sec=time.monotonic()-self.started).model_dump()
