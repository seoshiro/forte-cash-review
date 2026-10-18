"""Atomic complete-fit checkpoints. No pickle and no mid-optimizer resume."""
from pathlib import Path
import hashlib,json,os,uuid
import numpy as np
import torch
from safetensors.torch import save_file,load_file
from cashreview.supervision import atomic_json
from .last_layer import Head,Adapter


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def identity(items,cfg,enabled):
    # IDs/labels are only checkpoint-training provenance, never prediction input.
    values={'items':[{k:item[k] for k in ['sha256','group','target','label_sec']} for item in items],
            'recipe':cfg,'adapter_enabled':enabled}
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class CompletedFits:
    def __init__(self,directory,registration,original_fit,on_commit=lambda count:None,maximum=50):
        self.directory=Path(directory).resolve();self.directory.mkdir(parents=True,exist_ok=True)
        self.registration=registration;self.original_fit=original_fit;self.on_commit=on_commit;self.calls=0;self.maximum=maximum;self.active_index=None
    def safe_child(self,name):
        value=(self.directory/name).resolve()
        if value.parent!=self.directory or value.is_symlink():raise ValueError('Checkpoint path escaped owned directory')
        return value
    def count(self):
        count=0
        for number in range(1,self.maximum+1):
            folder=self.safe_child(f'{number:04d}')
            if not folder.exists():break
            self.validate_commit(folder);count+=1
        if any(p.name.isdigit() and int(p.name)>count for p in self.directory.iterdir()):raise ValueError('Noncontiguous committed fits')
        return count
    def validate_commit(self,folder):
        record=json.loads((folder/'commit.json').read_text())
        if record['registration_sha256']!=self.registration or record['complete_optimizer_fit'] is not True:raise ValueError('Checkpoint identity mismatch')
        if set(p.name for p in folder.iterdir())!={'projection.npz','state.safetensors','commit.json'}:raise ValueError('Checkpoint inventory mismatch')
        if sha(folder/'projection.npz')!=record['projection_sha256'] or sha(folder/'state.safetensors')!=record['state_sha256']:raise ValueError('Checkpoint bytes changed')
        return record
    def save(self,number,fit_id,cfg,enabled,fitted,cost):
        if cost['optimizer_steps']!=cfg['head']['steps']:raise ValueError('Incomplete fit cannot commit')
        pending=self.safe_child('.pending-'+uuid.uuid4().hex);destination=self.safe_child(f'{number:04d}')
        if destination.exists():raise ValueError('No completed-fit overwrite')
        pending.mkdir()
        np.savez_compressed(pending/'projection.npz',mean=fitted[0][0],basis=fitted[0][1])
        state={'head.'+k:v.detach().cpu().contiguous() for k,v in fitted[1].state_dict().items()}
        if enabled:state.update({'adapter.'+k:v.detach().cpu().contiguous() for k,v in fitted[2].state_dict().items()})
        state['rng.cpu']=torch.get_rng_state().cpu()
        if next(fitted[1].parameters()).is_cuda:state['rng.cuda']=torch.cuda.get_rng_state().cpu()
        save_file(state,str(pending/'state.safetensors'))
        # Flush both payloads before publishing the final commit marker/directory.
        for name in ['projection.npz','state.safetensors']:
            with (pending/name).open('r+b') as stream:stream.flush();os.fsync(stream.fileno())
        record={'registration_sha256':self.registration,'fit_identity_sha256':fit_id,'ordinal':number,
                'complete_optimizer_fit':True,'optimizer_steps':cost['optimizer_steps'],'adapter_enabled':enabled,
                'optimizer_resume_scope':'Completed fit only; unfinished fit restarts at the original seed/step zero',
                'projection_sha256':sha(pending/'projection.npz'),'state_sha256':sha(pending/'state.safetensors'),'cost':cost}
        atomic_json(pending/'commit.json',record)
        # Both absolute paths were checked as immediate children of the owned directory.
        pending.replace(destination)
    def load(self,folder,record,cfg,enabled,device):
        if record['adapter_enabled']!=enabled or record['optimizer_steps']!=cfg['head']['steps']:raise ValueError('Saved recipe differs')
        with np.load(folder/'projection.npz',allow_pickle=False) as values:
            if set(values.files)!={'mean','basis'}:raise ValueError('Projection keys changed')
            projection=(np.array(values['mean']),np.array(values['basis']))
        if projection[0].shape!=(512,) or projection[1].shape!=(512,8) or not all(np.isfinite(v).all() for v in projection):raise ValueError('Projection invalid')
        values=load_file(str(folder/'state.safetensors'),device='cpu');head=Head(cfg['head']).to(device);adapter=Adapter(cfg['model']).to(device) if enabled else None
        expected={'head.'+k for k in head.state_dict()}|({'adapter.'+k for k in adapter.state_dict()} if enabled else set())|{'rng.cpu'}
        if str(device).startswith('cuda'):expected.add('rng.cuda')
        if set(values)!=expected or any(not torch.isfinite(v).all() for k,v in values.items() if not k.startswith('rng.')):raise ValueError('Saved tensors invalid')
        head.load_state_dict({k:values['head.'+k] for k in head.state_dict()},strict=True);head.eval()
        if adapter is not None:adapter.load_state_dict({k:values['adapter.'+k] for k in adapter.state_dict()},strict=True);adapter.eval()
        torch.set_rng_state(values['rng.cpu'])
        if 'rng.cuda' in values:torch.cuda.set_rng_state(values['rng.cuda'])
        return (projection,head,adapter),record['cost']
    def __call__(self,items,cfg,enabled,check=lambda:None,device='cuda:0'):
        self.calls+=1;number=self.calls;self.active_index=number
        if number>self.maximum:raise ValueError('Fixed fit count exceeded')
        fit_id=identity(items,cfg,enabled);folder=self.safe_child(f'{number:04d}')
        if folder.exists():
            record=self.validate_commit(folder)
            if record['fit_identity_sha256']!=fit_id or record['ordinal']!=number:raise ValueError('Wrong fold/arm/provenance checkpoint')
            fitted,cost=self.load(folder,record,cfg,enabled,device)
        else:
            if self.count()!=number-1:raise ValueError('Missing preceding fit checkpoint')
            fitted,cost=self.original_fit(items,cfg,enabled,check,device=device)
            self.save(number,fit_id,cfg,enabled,fitted,cost)
        self.on_commit(number);self.active_index=None
        return fitted,cost
