"""Controlled existing-head train-fit checks; no semantic or per-video output."""
import time,math
import numpy as np
import torch
from .temporal_head import TemporalHead,fit_projection,padded_batch,supervised_loss,predict


def subset(items):
    chosen=[];groups=set()
    for target in (0,1):
        count=0
        for item in sorted(items,key=lambda i:i['sha256']):
            if item['target']==target and item['group'] not in groups:
                chosen.append(item);groups.add(item['group']);count+=1
                if count==2:break
        if count!=2:raise ValueError('Four distinct TRAIN groups required')
    return chosen


def indices(items):
    positive=[i for i,item in enumerate(items) if item['target']]
    negative=[i for i,item in enumerate(items) if not item['target']]
    points=[int(np.argmin(abs(items[i]['times']-items[i]['label_sec']))) for i in positive]
    if not positive or not negative:raise ValueError('Both classes required')
    return positive,points,negative


def zero_logit_check(valid,positive,points,negative):
    logits=torch.zeros(valid.shape,requires_grad=True)
    loss=supervised_loss(logits,valid,positive,points,negative);loss.backward();grad=logits.grad
    p=float(grad[positive].sum());n=float(grad[negative].sum())
    if abs(float(loss.detach())-math.log(2))>1e-6 or abs(p+.25)>1e-6 or abs(n-.25)>1e-6:raise ValueError('Loss/class/sign gradient check failed')
    expected=torch.zeros_like(grad)
    for i,j in zip(positive,points):expected[i,j]=-.25/len(positive)
    for i in negative:expected[i,int(torch.where(valid[i])[0][0])]=.25/len(negative)
    if not torch.allclose(grad,expected,atol=1e-7):raise ValueError('Unexpected supervision or padding gradient')
    return {'loss':float(loss.detach()),'positive_gradient_sum':p,'negative_gradient_sum':n,
        'other_positive_positions_have_zero_direct_loss_gradient':True,'invalid_padding_has_zero_gradient':True}


def training_fit(head,items):
    projection,model=head;model.eval();x,valid=padded_batch(projection,[item['ordered'] for item in items]);positive,points,negative=indices(items)
    with torch.inference_mode():
        logits=model(x);loss=supervised_loss(logits,valid,positive,points,negative)
        maxima=logits.masked_fill(~valid,-torch.inf).max(dim=1).values
        decisions=maxima>=0;truth=torch.tensor([bool(i['target']) for i in items])
        point_logits=logits[positive,points];negative_max=maxima[negative]
        result={'training_videos':len(items),'point_negative_max_eval_loss':float(loss),
            'confusion_matrix_tn_fp_fn_tp':[[int((~truth&~decisions).sum()),int((~truth&decisions).sum())],
                [int((truth&~decisions).sum()),int((truth&decisions).sum())]],
            'positive_point_logit_mean':float(point_logits.mean()),'negative_video_max_logit_mean':float(negative_max.mean()),
            'positive_point_logits_above_threshold_count':int((point_logits>=0).sum()),
            'negative_video_max_logits_below_threshold_count':int((negative_max<0).sum()),
            'threshold_logit':0.0,'train_fit_only_not_validation':True}
        if not torch.equal(decisions,torch.sigmoid(maxima.double())>=.5):raise ValueError('Threshold/sign mismatch')
    # Exercise the actual label/name-free predictor and its fixed score sign.
    prediction=[predict(head,item['ordered'],item['times'])['prediction'] for item in items]
    if prediction!=decisions.int().tolist():raise ValueError('Predictor differs from training aggregation')
    return result


def arm(items,projection,cfg,recipe,check=lambda:None):
    torch.manual_seed(cfg['shared']['seed']);model=TemporalHead(dropout=recipe['dropout']);head=(projection,model)
    x,valid=padded_batch(projection,[i['ordered'] for i in items]);positive,points,negative=indices(items)
    probe=zero_logit_check(valid,positive,points,negative);before=training_fit(head,items)
    initial=[p.detach().clone() for p in model.parameters()]
    optimizer=torch.optim.AdamW(model.parameters(),lr=recipe['learning_rate'],weight_decay=recipe['weight_decay'])
    curve=[{'step':0,'eval_loss':before['point_negative_max_eval_loss']}];first=None;last=None;minimum=float('inf');steps=0;start=time.monotonic()
    for step in range(1,recipe['steps']+1):
        check();model.train();optimizer.zero_grad(set_to_none=True)
        loss=supervised_loss(model(x),valid,positive,points,negative)
        if not torch.isfinite(loss):raise ValueError('Nonfinite train loss')
        loss.backward();norm=0.
        for p in model.parameters():
            if p.grad is not None:
                if not torch.isfinite(p.grad).all():raise ValueError('Nonfinite data gradients')
                norm+=float(p.grad.detach().square().sum())
        norm=math.sqrt(norm);minimum=min(minimum,norm);first=norm if first is None else first;last=norm
        optimizer.step();steps+=1
        if not all(torch.isfinite(p).all() for p in model.parameters()):raise ValueError('Nonfinite parameters')
        if step in cfg['shared']['eval_steps']:curve.append({'step':step,'eval_loss':training_fit(head,items)['point_negative_max_eval_loss']})
    after=training_fit(head,items);delta=math.sqrt(sum(float((p.detach()-old).square().sum()) for p,old in zip(model.parameters(),initial)))
    state_steps=[int(state['step']) for state in optimizer.state.values()]
    if not state_steps or set(state_steps)!={recipe['steps']}:raise ValueError('AdamW internal step mismatch')
    if steps!=recipe['steps'] or first<=0 or delta<=0:raise ValueError('Optimizer/update path failed')
    return {'before':before,'after':after,'eval_loss_checkpoints':curve,'zero_logit_gradient_check':probe,
        'optimizer_steps_applied':steps,'adamw_state_step_min':min(state_steps),'adamw_state_step_max':max(state_steps),
        'gradient_l2_first':first,'gradient_l2_last':last,'minimum_gradient_l2':minimum,
        'parameter_delta_l2':delta,'finite_gradient_and_parameter_checks_passed':True,
        'elapsed_sec':time.monotonic()-start,'scope':'Diagnostic train-fit only; not CV, quality or causal factor attribution'}
