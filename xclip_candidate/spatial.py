"""Fixed full-field versus central view; no media or prediction stdout."""
import math
import numpy as np
from PIL import Image
from .evaluate import centroids,score_video
from qvt_candidate.evaluate import metrics
from sklearn.metrics import roc_auc_score


def prepare_view(image,geometry,crop=False):
    if crop:
        w,h=image.size;x1,y1,x2,y2=geometry['crop_xyxy_normalized']
        box=(max(0,math.floor(x1*w)),max(0,math.floor(y1*h)),min(w,math.ceil(x2*w)),min(h,math.ceil(y2*h)))
        if box[2]<=box[0] or box[3]<=box[1]:raise ValueError('Invalid fixed crop')
        image=image.crop(box)
    side=geometry['output_side'];w,h=image.size;scale=side/max(w,h)
    resized=image.resize((max(1,round(w*scale)),max(1,round(h*scale))),Image.Resampling.LANCZOS)
    output=Image.new('RGB',(side,side),tuple(geometry['padding_rgb']))
    output.paste(resized,((side-resized.width)//2,(side-resized.height)//2));return output


def encode_views(encoder,clips,geometry):
    torch=encoder.torch;results={'full_field':[],'central_crop':[]};batch=encoder.cfg['features']['batch_windows']
    with torch.inference_mode():
        for start in range(0,len(clips),batch):
            for name in results:
                encoder.check();part=[[prepare_view(image,geometry,name=='central_crop') for image in clip] for clip in clips[start:start+batch]]
                values=encoder.processor(images=part,return_tensors='pt')['pixel_values']
                if tuple(values.shape)!=(len(part),8,3,224,224):raise ValueError('Spatial processor shape changed')
                vectors=encoder.model.get_video_features(pixel_values=values.to(device='cuda:0',dtype=torch.float16)).pooler_output.float()
                vectors=vectors/vectors.norm(dim=-1,keepdim=True).clamp_min(1e-9)
                results[name].append(vectors.cpu().numpy());torch.cuda.synchronize();encoder.check()
    result={name:np.concatenate(values) for name,values in results.items()}
    if any(v.shape!=(len(clips),512) or not np.isfinite(v).all() for v in result.values()):raise ValueError('Invalid spatial vectors')
    return result


def extract(encoder,path,original_cfg,cfg):
    from cashreview.video import validate_input,sample
    from .features import window_targets,match_pts
    info=validate_input(path);targets=window_targets(info['duration_sec'],original_cfg)
    unique=sorted(set(round(float(t),6) for t in targets.flatten()))
    frames=sample(path,unique,max_side=cfg['geometry']['decode_max_side']);pts=np.array([f.sec for f in frames])
    clips=[];centers=[]
    for times in targets:
        indices=match_pts(pts,times,original_cfg['features']['pts_match_tolerance_sec'])
        clips.append([frames[int(i)].image for i in indices]);centers.append(float((pts[indices[0]]+pts[indices[-1]])/2))
    result=encode_views(encoder,clips,cfg['geometry']);result.update(times=np.array(centers),frames=len(frames),windows=len(clips))
    return result


def select_fallback(full,crop):
    chosen=crop if crop[0]>=0 else full
    return max(full[0],crop[0]),chosen[1]


def evaluate(items):
    records={name:[] for name in ['full_field','central_crop','central_with_full_fallback']}
    for group in sorted({i['group'] for i in items}):
        train=[i for i in items if i['group']!=group]
        prototypes={arm:centroids(train,arm) for arm in ['full_field','central_crop']}
        for item in items:
            if item['group']!=group:continue
            values={arm:score_video(item[arm],item['times'],*prototypes[arm],'max') for arm in prototypes}
            values['central_with_full_fallback']=select_fallback(values['full_field'],values['central_crop'])
            for arm,(margin,sec) in values.items():
                records[arm].append({'truth':item['target'],'prediction':int(margin>=0),'score':margin,'time_sec':sec,
                    'error_sec':abs(sec-item['label_sec']) if item['target'] else None,'source_sha256':item['sha256']})
    aggregate={}
    for arm,rows in records.items():
        aggregate[arm]=metrics(rows);aggregate[arm]['video_roc_auc']=float(roc_auc_score([r['truth'] for r in rows],[r['score'] for r in rows]))
    return aggregate,records


def accepted(results,cfg):
    base=results['full_field'];variant=results['central_with_full_fallback'];gate=cfg['acceptance']
    b=base['confusion_matrix_tn_fp_fn_tp'];v=variant['confusion_matrix_tn_fp_fn_tp']
    return bool(variant['f1']>=gate['fallback_f1_min'] and variant['f1']>=base['f1']+gate['f1_gain_over_full_min']
        and v[1][1]>=gate['fallback_tp_min'] and v[0][1]<=gate['fallback_fp_max'] and v[0][1]<=b[0][1] and v[1][0]<=b[1][0])
