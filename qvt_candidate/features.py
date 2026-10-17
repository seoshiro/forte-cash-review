"""Local visual encoder only; no language model or generated descriptions."""
from pathlib import Path
import hashlib,json,time
import numpy as np


def representations(features):
    features=np.asarray(features,dtype=np.float32)
    if features.ndim!=2 or len(features)==0 or not np.isfinite(features).all():
        raise ValueError('Invalid visual feature array')
    previous=np.concatenate([features[:1],features[:-1]],axis=0)
    following=np.concatenate([features[1:],features[-1:]],axis=0)
    return {'static':features,'temporal':np.concatenate([features,previous-features,following-features],axis=1)}


class VisionEncoder:
    def __init__(self,root,cfg):
        import torch
        from safetensors import safe_open
        from transformers import AutoImageProcessor
        from transformers.models.qwen3_vl.configuration_qwen3_vl import Qwen3VLConfig
        from transformers.models.qwen3_vl.modeling_qwen3_vl import Qwen3VLVisionModel
        self.torch=torch;self.cfg=cfg;path=Path(root)/'models/qwen3-vl-2b'
        with (path/'model.safetensors').open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=cfg['weights_sha256']:
                raise ValueError('Encoder digest mismatch')
        config=Qwen3VLConfig.from_pretrained(str(path),local_files_only=True).vision_config
        config._attn_implementation='sdpa'
        # Materialize only the visual model. CPU initialization also constructs
        # non-persistent rotary buffers correctly; no unresolved meta tensors.
        original_dtype=torch.get_default_dtype()
        try:
            torch.set_default_dtype(torch.bfloat16)
            self.model=Qwen3VLVisionModel(config)
        finally:
            torch.set_default_dtype(original_dtype)
        with safe_open(path/'model.safetensors',framework='pt',device='cpu') as weights:
            state={k.removeprefix('model.visual.'):weights.get_tensor(k) for k in weights.keys() if k.startswith('model.visual.')}
        self.model.load_state_dict(state,strict=True,assign=True)
        del state
        self.model=self.model.to(device='cuda:0',dtype=torch.bfloat16).eval()
        self.processor=AutoImageProcessor.from_pretrained(str(path),local_files_only=True,use_fast=False)
        self.parameter_count=sum(p.numel() for p in self.model.parameters())
        self.projection=np.random.default_rng(cfg['features']['projection_seed']).normal(
            size=(config.out_hidden_size,cfg['features']['projection_dim'])).astype(np.float32)/np.sqrt(cfg['features']['projection_dim'])

    def encode(self,images):
        torch=self.torch;result=[];batch=self.cfg['features']['batch_frames']
        with torch.inference_mode():
            for start in range(0,len(images),batch):
                inputs=self.processor(images=images[start:start+batch],return_tensors='pt',
                    min_pixels=self.cfg['features']['min_pixels'],max_pixels=self.cfg['features']['max_pixels'])
                grid=inputs['image_grid_thw'].to('cuda:0')
                output=self.model(hidden_states=inputs['pixel_values'].to(device='cuda:0',dtype=torch.bfloat16),grid_thw=grid)
                lengths=(grid.prod(-1)//self.model.spatial_merge_unit).tolist()
                if output.pooler_output.shape[0]!=sum(lengths):raise ValueError('Visual token layout mismatch')
                offset=0
                for count in lengths:
                    vector=output.pooler_output[offset:offset+count].float().mean(0).cpu().numpy();offset+=count
                    vector/=max(np.linalg.norm(vector),1e-9);vector=vector@self.projection
                    result.append(vector/max(np.linalg.norm(vector),1e-9))
        torch.cuda.synchronize()
        features=np.asarray(result,dtype=np.float32)
        if features.shape!=(len(images),self.cfg['features']['projection_dim']) or not np.isfinite(features).all():
            raise ValueError('Invalid encoder output')
        return features


def extract(encoder,path,cfg):
    from cashreview.video import validate_input,sample
    info=validate_input(Path(path));start=time.monotonic()
    grid=np.arange(0,max(0.01,info['duration_sec']-0.1),cfg['features']['frame_step_sec']).tolist()
    frames=sample(Path(path),grid,max_side=cfg['features']['max_side'])
    features=encoder.encode([frame.image for frame in frames])
    return np.array([frame.sec for frame in frames]),features,time.monotonic()-start
