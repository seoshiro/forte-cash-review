import copy,json,os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
import numpy as np
import pytest,torch
from xclip_candidate.fit_checkpoints import CompletedFits
from xclip_candidate.last_layer import fit,replay


def setup():
    cfg=json.loads((Path(__file__).resolve().parents[1]/'config/xclip-last-layer-protocol.json').read_text());cfg['head']['steps']=3
    torch.set_num_threads(1);rng=np.random.default_rng(1212);items=[]
    for i in range(6):
        prefix={k:rng.normal(size=(2,4,8,2048 if k=='h' else 512)).astype(np.float16) for k in ['h','fc2','residual','outer']}
        ordered=replay({k:torch.from_numpy(v[0]) for k,v in prefix.items()}).numpy()
        items.append({'sha256':str(i),'group':str(i),'target':i%2,'label_sec':1. if i%2 else None,'prefix':prefix,'ordered':ordered,'times':np.arange(4,dtype=float)})
    return cfg,items


def states(fitted):return {arm+'.'+key:value.clone() for arm,model in [('head',fitted[1]),('adapter',fitted[2])] if model is not None for key,value in model.state_dict().items()}


@pytest.mark.parametrize('device',['cpu','cuda:0'])
def test_completed_fit_resume_matches_parameters_rng_and_next_fresh_fit(tmp_path,device):
    if device.startswith('cuda') and not torch.cuda.is_available():pytest.skip('CUDA unavailable')
    cfg,items=setup();cache=CompletedFits(tmp_path/'fits','registered',fit,maximum=2)
    first,cost=cache(items,cfg,True,device=device);expected=states(first);rng=torch.get_rng_state().clone()
    cuda_rng=torch.cuda.get_rng_state().clone() if device.startswith('cuda') else None
    next_original,_=cache(items,cfg,False,device=device);next_expected=states(next_original)
    calls=[]
    def forbidden(*args,**kwargs):calls.append(True);raise AssertionError('Completed fit must not retrain')
    resumed=CompletedFits(tmp_path/'fits','registered',forbidden,maximum=2)
    restored,restored_cost=resumed(items,cfg,True,device=device)
    assert not calls and restored_cost==cost and torch.equal(torch.get_rng_state(),rng)
    if cuda_rng is not None:assert torch.equal(torch.cuda.get_rng_state(),cuda_rng)
    assert all(torch.equal(expected[k],v) for k,v in states(restored).items())
    fresh_after_resume,_=fit(items,cfg,False,device=device)
    assert all(torch.equal(next_expected[k],v) for k,v in states(fresh_after_resume).items())
    second,_=resumed(items,cfg,False,device=device);assert all(torch.equal(next_expected[k],v) for k,v in states(second).items())
    assert resumed.count()==2


def test_partial_write_does_not_publish_and_completed_prefix_survives_failure(tmp_path):
    cfg,items=setup();cache=CompletedFits(tmp_path/'fits','registered',fit,maximum=2);cache(items,cfg,False,device='cpu')
    def fail(*args,**kwargs):raise RuntimeError('Synthetic interrupted optimizer')
    cache.original_fit=fail
    with pytest.raises(RuntimeError):cache(items,cfg,True,device='cpu')
    assert cache.count()==1 and not (tmp_path/'fits/0002').exists()
    resumed=CompletedFits(tmp_path/'fits','registered',fit,maximum=2);resumed(items,cfg,False,device='cpu');resumed(items,cfg,True,device='cpu')
    assert resumed.count()==2


def test_wrong_fold_or_tampered_checkpoint_is_rejected(tmp_path):
    cfg,items=setup();cache=CompletedFits(tmp_path/'fits','registered',fit);cache(items,cfg,True,device='cpu')
    wrong=copy.copy(items);wrong=list(reversed(wrong));resumed=CompletedFits(tmp_path/'fits','registered',fit)
    with pytest.raises(ValueError,match='Wrong fold'):resumed(wrong,cfg,True,device='cpu')
    file=tmp_path/'fits/0001/state.safetensors';file.write_bytes(file.read_bytes()+b'bad')
    with pytest.raises(ValueError,match='bytes'):CompletedFits(tmp_path/'fits','registered',fit).count()
