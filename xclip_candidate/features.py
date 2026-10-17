"""Label/name-free fixed windows. No media, frame or description output."""
from pathlib import Path
import time,json,hashlib
import numpy as np


def window_targets(duration,cfg):
    f=cfg['features'];last=max(0.,duration-f['window_duration_sec']-f['end_margin_sec'])
    starts=np.arange(0,last+1e-8,f['window_stride_sec'])
    if last-starts[-1]>f['append_last_window_if_gap_exceeds_sec']:starts=np.append(starts,last)
    offsets=np.linspace(0,f['window_duration_sec'],f['frames_per_window'])
    return starts[:,None]+offsets[None,:]


def probe_order(rows):
    ordered=sorted(rows,key=lambda r:r['duration_sec']);probes=[ordered[0],ordered[len(ordered)//2],ordered[-1]]
    if len({r['sha256'] for r in rows})!=len(rows):raise ValueError('Selection must be exact-unique before probe ordering')
    chosen={r['sha256'] for r in probes}
    result=probes+[r for r in sorted(rows,key=lambda r:r['sha256']) if r['sha256'] not in chosen]
    if len(result)!=len(rows):raise ValueError('Probe ordering changed item count')
    return result


def match_pts(pts,targets,tolerance):
    # Shared sampler may emit up to 1e-4 seconds before a target. Also allow
    # the sub-microsecond target rounding used to deduplicate requests.
    indices=np.searchsorted(pts,np.asarray(targets)-tolerance,side='left').clip(max=len(pts)-1)
    if np.max(abs(pts[indices]-targets))>.10:raise ValueError('PTS target correspondence exceeded budget')
    return indices


class Encoder:
    def __init__(self,root,cfg,check_deadline):
        import torch
        from transformers import AutoImageProcessor,XCLIPModel
        from transformers.utils import logging
        logging.set_verbosity_error();logging.disable_progress_bar()
        self.cfg=cfg;self.torch=torch;self.check=check_deadline;path=Path(root)/'models/xclip-base-patch32'
        provenance=json.loads((path/'provenance.json').read_text());artifacts=json.loads((Path(root)/'config/xclip-artifacts.json').read_text())
        if provenance['revision']!=artifacts['revision']:raise ValueError('Model provenance mismatch')
        with (path/'model.safetensors').open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=artifacts['weight_sha256']:raise ValueError('Weight SHA mismatch')
        self.processor=AutoImageProcessor.from_pretrained(str(path),local_files_only=True,use_fast=False)
        self.model=XCLIPModel.from_pretrained(str(path),local_files_only=True,use_safetensors=True,dtype=torch.float16,
            attn_implementation=cfg['features']['attention']).to('cuda:0').eval()
        if self.model.config.vision_config.num_frames!=8 or self.model.config.vision_config.image_size!=224:raise ValueError('Unexpected video configuration')
        self.parameters=sum(p.numel() for p in self.model.parameters())
        self.check()

    def encode(self,clips):
        torch=self.torch;batch=self.cfg['features']['batch_windows'];result={'ordered':[],'repeated':[]}
        with torch.inference_mode():
            for start in range(0,len(clips),batch):
                self.check();part=clips[start:start+batch]
                values=self.processor(images=part,return_tensors='pt')['pixel_values']
                # VideoMAE's image processor batches nested frame lists once;
                # validate video layout instead of silently reshaping a mismatch.
                if tuple(values.shape)!=(len(part),8,3,224,224):raise ValueError('Processor video layout mismatch')
                values=values.to(device='cuda:0',dtype=torch.float16)
                for arm in ['ordered','repeated']:
                    inputs=values if arm=='ordered' else values[:,4:5].expand(-1,8,-1,-1,-1).contiguous()
                    vector=self.model.get_video_features(pixel_values=inputs).pooler_output.float()
                    vector=vector/vector.norm(dim=-1,keepdim=True).clamp_min(1e-9)
                    result[arm].append(vector.cpu().numpy())
                torch.cuda.synchronize();self.check()
        arrays={key:np.concatenate(value) for key,value in result.items()}
        if any(value.shape!=(len(clips),512) or not np.isfinite(value).all() for value in arrays.values()):raise ValueError('Invalid temporal features')
        return arrays


def extract(encoder,path,cfg):
    from cashreview.video import validate_input,sample
    start=time.monotonic();info=validate_input(Path(path));targets=window_targets(info['duration_sec'],cfg)
    unique=sorted(set(round(float(t),6) for t in targets.flatten()))
    frames=sample(Path(path),unique,max_side=cfg['features']['decode_max_side'])
    pts=np.array([frame.sec for frame in frames]);clips=[];centers=[]
    for times in targets:
        indices=match_pts(pts,times,cfg['features']['pts_match_tolerance_sec'])
        clips.append([frames[int(i)].image for i in indices]);centers.append(float((pts[indices[0]]+pts[indices[-1]])/2))
    result=encoder.encode(clips);result.update(times=np.array(centers),frames=len(frames),windows=len(clips),elapsed_sec=time.monotonic()-start)
    return result
