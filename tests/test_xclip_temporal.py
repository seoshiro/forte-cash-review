import copy,inspect,json
from pathlib import Path
import numpy as np
import torch
from xclip_candidate.temporal_head import TemporalHead,fit_projection,padded_batch,supervised_loss,fit_head,predict
from xclip_candidate.evaluate import unit


def fixtures():
    rng=np.random.default_rng(9041)
    return [{'ordered':unit(rng.normal(size=(8+i,16))),'times':np.arange(8+i,dtype=float),
        'target':i%2,'label_sec':3. if i%2 else None,'group':f'g{i//2}','sha256':str(i)*64} for i in range(6)]


def config():return json.loads((Path(__file__).resolve().parents[1]/'config/xclip-temporal-protocol.json').read_text())


def test_pca_uses_equal_video_mass_and_train_only_without_mutation():
    rows=fixtures();original=copy.deepcopy(rows);mean,basis=fit_projection(rows[:4],8)
    assert np.allclose(mean,np.mean([unit(i['ordered']).mean(0) for i in rows[:4]],axis=0))
    rows[4]['ordered']*=1000
    new_mean,new_basis=fit_projection(rows[:4],8)
    assert np.array_equal(mean,new_mean) and np.array_equal(basis,new_basis)
    assert np.allclose(basis.T@basis,np.eye(8))
    assert all(np.array_equal(rows[i]['ordered'],original[i]['ordered']) for i in range(4))


def test_positive_other_positions_have_no_target_and_invalid_negative_padding_is_ignored():
    logits=torch.tensor([[9.,-1.,8.,20.],[1.,2.,3.,100.]],requires_grad=True)
    valid=torch.tensor([[True,True,True,True],[True,True,True,False]])
    loss=supervised_loss(logits,valid,[0],[1],[1]);loss.backward()
    assert logits.grad[0,1]<0 and torch.count_nonzero(logits.grad[0])==1
    assert logits.grad[1,2]>0 and torch.count_nonzero(logits.grad[1])==1


def test_padding_never_mixes_video_boundaries_and_eval_is_batch_independent():
    rows=fixtures();projection=fit_projection(rows,8);model=TemporalHead().eval()
    single,_=padded_batch(projection,[rows[0]['ordered']]);batch,valid=padded_batch(projection,[rows[0]['ordered'],rows[-1]['ordered']])
    with torch.inference_mode():a=model(single)[0];b=model(batch)[0,:len(a)]
    assert torch.allclose(a,b,atol=1e-6)
    assert int(valid[0].sum())==len(rows[0]['times'])
    assert torch.equal(batch[0,:,-1],single[0,:,-1])


def test_temporal_context_changes_neighbor_outputs_and_parameter_count_is_fixed():
    model=TemporalHead(dropout=0).eval()
    assert sum(p.numel() for p in model.parameters())==209
    with torch.no_grad():
        for p in model.parameters():p.fill_(.1)
        first=torch.zeros(1,8,5);second=first.clone();second[:,:,1]=1
        a=model(first);b=model(second)
    assert b[0,2]!=a[0,2] and b[0,4]==a[0,4]


def test_fixed_fit_is_deterministic_and_predict_has_no_identity_or_supervision_interface():
    cfg=config();cfg['head']['steps']=2;rows=fixtures()
    torch.set_num_threads(1)
    first,_=fit_head(rows,cfg);second,_=fit_head(rows,cfg)
    a=predict(first,rows[0]['ordered'],rows[0]['times']);b=predict(second,rows[0]['ordered'],rows[0]['times'])
    assert a==b
    assert list(inspect.signature(predict).parameters)==['head','features','times','threshold']


def test_actual_worker_learning_path_calls_network_guard_as_a_function(monkeypatch):
    from scripts.xclip_temporal import execute_learning
    from cashreview import offline
    from xclip_candidate import temporal_head
    events=[]
    monkeypatch.setattr(offline,'deny_network',lambda:events.append('network_denied'))
    def fake_evaluate(items,cfg,check,progress):
        assert events==['network_denied'];events.append('cv');return {'aggregate':True},{'private':'local'}
    def fake_fit(items,cfg,check):
        assert events==['network_denied','cv'];events.append('full_train');return 'head',.5
    monkeypatch.setattr(temporal_head,'evaluate',fake_evaluate);monkeypatch.setattr(temporal_head,'fit_head',fake_fit)
    summary,private,head,elapsed=execute_learning([],{},lambda:None,lambda n:None)
    assert summary=={'aggregate':True} and head=='head' and elapsed>=0
    assert events==['network_denied','cv','full_train']
