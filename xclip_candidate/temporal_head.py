"""Small supervised temporal learner. Inference accepts feature sequences/PTS only."""
import time
import numpy as np
import torch
from torch import nn
from .linear_head import validate_items,report
from .evaluate import unit,centroids,score_video


class TemporalHead(nn.Module):
    def __init__(self,components=8,channels=8,dropout=.5):
        super().__init__()
        self.network=nn.Sequential(nn.Conv1d(components,channels,3,padding=1,padding_mode='replicate'),
            nn.GELU(),nn.Dropout(dropout),nn.Conv1d(channels,1,1))

    def forward(self,x):return self.network(x).squeeze(1)


def fit_projection(train,components):
    features=np.concatenate([unit(np.asarray(i['ordered'],dtype=np.float64)) for i in train])
    weights=np.concatenate([np.full(len(i['times']),1/(len(train)*len(i['times']))) for i in train])
    mean=np.sum(features*weights[:,None],axis=0);centered=features-mean
    covariance=(centered*weights[:,None]).T@centered
    eigenvalues,eigenvectors=np.linalg.eigh(covariance);order=np.argsort(eigenvalues)[::-1][:components]
    if len(order)!=components or np.min(eigenvalues[order])<=1e-12:raise ValueError('Degenerate train-fold projection')
    basis=eigenvectors[:,order]
    for column in range(components):
        if basis[np.argmax(abs(basis[:,column])),column]<0:basis[:,column]*=-1
    return mean,basis


def transform(projection,features):
    mean,basis=projection;value=unit(np.asarray(features,dtype=np.float64))
    if value.ndim!=2 or value.shape[1]!=len(mean) or not np.isfinite(value).all():raise ValueError('Invalid inference features')
    return ((value-mean)@basis).astype(np.float32)


def padded_batch(projection,sequences):
    arrays=[transform(projection,x) for x in sequences];lengths=np.array([len(a) for a in arrays])
    if not len(arrays) or np.min(lengths)<2:raise ValueError('Invalid sequence length')
    longest=int(max(lengths));batch=np.empty((len(arrays),arrays[0].shape[1],longest),dtype=np.float32)
    for index,a in enumerate(arrays):batch[index]=np.pad(a.T,((0,0),(0,longest-len(a))),mode='edge')
    valid=torch.arange(longest)[None,:]<torch.as_tensor(lengths)[:,None]
    return torch.from_numpy(batch),valid


def supervised_loss(logits,valid,positive,points,negative):
    p=logits[positive,points];n=logits[negative].masked_fill(~valid[negative],-torch.inf).max(dim=1).values
    criterion=nn.BCEWithLogitsLoss()
    return .5*criterion(p,torch.ones_like(p))+.5*criterion(n,torch.zeros_like(n))


def fit_head(train,cfg,check=lambda:None):
    projection=fit_projection(train,cfg['projection']['components']);h=cfg['head']
    torch.manual_seed(h['seed']);model=TemporalHead(cfg['projection']['components'],h['channels'],h['dropout'])
    if sum(p.numel() for p in model.parameters())!=h['trainable_parameters']:raise ValueError('Parameter count mismatch')
    x,valid=padded_batch(projection,[i['ordered'] for i in train]);positive=[n for n,i in enumerate(train) if i['target']]
    negative=[n for n,i in enumerate(train) if not i['target']]
    if not positive or not negative:raise ValueError('Train fold needs both classes')
    points=[int(np.argmin(abs(train[n]['times']-train[n]['label_sec']))) for n in positive]
    optimizer=torch.optim.AdamW(model.parameters(),lr=h['learning_rate'],weight_decay=h['weight_decay'])
    model.train();last_loss=None
    for _ in range(h['steps']):
        check();optimizer.zero_grad(set_to_none=True);logits=model(x)
        loss=supervised_loss(logits,valid,positive,points,negative)
        if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
        loss.backward();optimizer.step();last_loss=float(loss.detach())
    model.eval();check()
    return (projection,model),last_loss


def predict(head,features,times,threshold=0.):
    # No label, source ID, filename, group or official point is accepted here.
    projection,model=head;model.eval();x,valid=padded_batch(projection,[features])
    times=np.asarray(times)
    if times.ndim!=1 or len(times)!=x.shape[-1] or not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('Invalid inference PTS')
    with torch.inference_mode():scores=model(x)[0].numpy()
    if not np.isfinite(scores).all():raise ValueError('Nonfinite prediction')
    index=int(np.argmax(scores))
    return {'prediction':int(scores[index]>=threshold),'score':float(scores[index]),'time_sec':float(times[index])}


def evaluate(items,cfg,check=lambda:None,progress=lambda n:None):
    validate_items(items);groups=sorted({i['group'] for i in items})
    if len(groups)!=cfg['evaluation']['folds'] or len(items)!=cfg['inputs']['unique_videos']:raise ValueError('Fixed TRAIN scope mismatch')
    if any(len(i['times'])>cfg['budget']['max_windows_per_video'] for i in items):raise ValueError('Sequence resource bound')
    records={'baseline':[],'temporal_head':[]};fits=[];scores=[];losses=[]
    for index,group in enumerate(groups):
        check();train=[i for i in items if i['group']!=group];test=[i for i in items if i['group']==group]
        if {i['sha256'] for i in train}&{i['sha256'] for i in test}:raise ValueError('Group leakage')
        p,n=centroids(train,'ordered');tick=time.perf_counter();head,loss=fit_head(train,cfg,check)
        fits.append(time.perf_counter()-tick);losses.append(loss)
        for item in test:
            score,sec=score_video(item['ordered'],item['times'],p,n,'max')
            baseline={'prediction':int(score>=0),'score':score,'time_sec':sec}
            tick=time.perf_counter();candidate=predict(head,item['ordered'],item['times'],cfg['evaluation']['threshold_logit']);scores.append(time.perf_counter()-tick)
            for name,row in [('baseline',baseline),('temporal_head',candidate)]:
                row.update(truth=item['target'],source_sha256=item['sha256'],group=group,
                    error_sec=abs(row['time_sec']-item['label_sec']) if item['target'] else None)
                records[name].append(row)
            check()
        progress(index+1)
    results={name:report(rows) for name,rows in records.items()};a=results['baseline'];b=results['temporal_head']
    if a['confusion_matrix_tn_fp_fn_tp']!=cfg['evaluation']['baseline_reproduction_cm'] or abs(a['f1']-cfg['evaluation']['baseline_f1'])>1e-12:raise ValueError('Baseline reproduction failed')
    ar={r['source_sha256']:r for r in records['baseline']};br={r['source_sha256']:r for r in records['temporal_head']}
    common=[key for key in ar if ar[key]['truth'] and ar[key]['prediction'] and br[key]['prediction']]
    paired={'common_true_positive_count':len(common),
        'baseline_candidate_point_mae_sec':float(np.mean([ar[k]['error_sec'] for k in common])) if common else None,
        'temporal_candidate_point_mae_sec':float(np.mean([br[k]['error_sec'] for k in common])) if common else None}
    gate=cfg['binary_gate'];cm=b['confusion_matrix_tn_fp_fn_tp']
    binary=cm[1][0]<=gate['fn_max'] and cm[0][1]<=gate['fp_max'] and b['f1']>=gate['f1_min']
    point=bool(common and b['all_positive_candidate_point_mae_sec']<=a['all_positive_candidate_point_mae_sec']
        and paired['temporal_candidate_point_mae_sec']<=paired['baseline_candidate_point_mae_sec'])
    return {'results':results,'paired_point_diagnostic':paired,'binary_gate_passed':bool(binary),
        'point_non_regression_gate_passed':point,'joint_useful_gate_passed':bool(binary and point),
        'fold_fit_sec_sum':sum(fits),'fold_fit_sec_mean':float(np.mean(fits)),'fold_fit_sec_max':max(fits),
        'head_video_score_sec_mean':float(np.mean(scores)),'head_video_score_sec_max':max(scores),
        'last_training_loss_mean':float(np.mean(losses)),'last_training_loss_min':min(losses),'last_training_loss_max':max(losses)},records
